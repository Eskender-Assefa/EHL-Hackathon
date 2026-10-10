import json
import os
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from fastapi.testclient import TestClient
from openpyxl import Workbook
import bmwdb
from backend import database
from backend.app import create_app
from backend.ingest import HEADERS,import_feedback,import_catalogue,import_pipeline

ROOT=Path(__file__).resolve().parents[1]

def workbook(path,rows):
    book=Workbook();sheet=book.active;sheet.title='Feedback_Explorer';sheet.append(HEADERS)
    for row in rows:sheet.append(row)
    book.save(path);book.close()

def feedback_row(id='ONE',text='The seats are uncomfortable',country='US',tag='Seats'):
    return [id,'supplied','BMW','unknown',country,'G60','unknown','Dislike',text,tag,None,None]


@unittest.skipUnless(os.environ.get('BMW_TEST_DATABASE_URL'),'PostgreSQL test target required')
class APITests(unittest.TestCase):
    def setUp(self):
        self.dsn=os.environ['BMW_TEST_DATABASE_URL'];self.schema='api_'+uuid.uuid4().hex
        self.conn=psycopg.connect(self.dsn,autocommit=True)
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
        bmwdb.migrate(self.conn)
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'feedback.xlsx'
        workbook(self.path,[feedback_row(),feedback_row(tag='Climate')])
        self.imported=import_feedback(self.conn,self.path,'G60')
        self.environ=patch.dict(os.environ,{'BMW_DEV_PM':'1','BMW_APP_ORIGIN':'http://127.0.0.1:8765'})
        self.environ.start()
        @contextmanager
        def connection():
            with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
                conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
                yield conn
        self.dbpatch=patch.object(database,'connection',connection);self.dbpatch.start()
        self.app=create_app(testing=True);self.client=TestClient(self.app)
        self.headers={'Origin':self.app.state.origin,'X-BMW-CSRF':self.app.state.csrf}
        self.eid=self.client.get('/api/v1/feedback?model_code=G60').json()['items'][0]['id']

    def tearDown(self):
        self.client.close();self.dbpatch.stop();self.environ.stop();self.temp.cleanup()
        self.conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)));self.conn.close()

    def draft(self,**overrides):
        payload={'title':'Improve seating support','statement':'Meet the specified seat comfort target',
                 'model_code':'G60','market_code':'US','category_id':'C05','evidence_ids':[self.eid],
                 'rationale':'Customer statement warrants review','target_value':3,'unit':'points',
                 'conditions':'Agreed controlled seating study','acceptance_test':'Mean score meets target','owner':'PM'}
        payload.update(overrides)
        return self.client.post('/api/v1/requirements',json=payload,headers=self.headers)

    def action(self,id,action='approve',revision=1,**overrides):
        payload={'action':action,'expected_revision':revision,'rationale':'Reviewed available source evidence'}
        payload.update(overrides)
        return self.client.post(f'/api/v1/requirements/{id}/actions',json=payload,headers=self.headers)

    def test_parent_tag_idempotency_and_provenance(self):
        self.assertEqual(self.imported['feedback_records'],1);self.assertEqual(self.imported['tag_rows'],2)
        again=import_feedback(self.conn,self.path,'G60');self.assertTrue(again['reimport'])
        item=self.client.get('/api/v1/feedback/'+self.eid).json()
        self.assertEqual(item['data_origin'],'unknown');self.assertIsNone(item['publication_date'])
        self.assertEqual(len(item['tags']),2);self.assertEqual(item['source_locations'][0]['row_number'],2)
        self.assertIsInstance(item['id'],str)
        self.assertNotIn(str(ROOT),json.dumps(item))

    def test_version_filters_and_latest_snapshot(self):
        workbook(self.path,[feedback_row(id='NEW',text='Positive seat feedback')])
        new=import_feedback(self.conn,self.path,'G60')
        latest=self.client.get('/api/v1/feedback?model_code=G60').json()
        self.assertEqual(latest['total'],1);self.assertEqual(latest['items'][0]['version_id'],new['version_id'])
        previous=self.client.get('/api/v1/feedback?model_code=G60&version_id='+self.imported['version_id']).json()
        self.assertEqual(previous['items'][0]['id'],self.eid)
        self.assertEqual(self.client.get('/api/v1/feedback?version_id=999999').status_code,422)

    def test_market_variant_and_catalogue_context(self):
        result=import_catalogue(self.conn,ROOT/'material/G60_OptionList.PDF','G60')
        self.assertEqual(result['pages'],28)
        self.assertEqual(self.client.get('/api/v1/catalogue-facts?model_code=G60&market_code=US').json()['total'],0)
        catalogue=self.client.get('/api/v1/catalogue-facts?model_code=G60&unknown_market_only=true').json()
        self.assertEqual(catalogue['total'],28);self.assertIsNone(catalogue['items'][0]['variant_id'])
        self.assertEqual(catalogue['items'][0]['review_status'],'unreviewed')
        self.assertEqual(self.draft(market_code='DE').status_code,422)

    def test_metrics_zero_denominator_and_zero_success(self):
        imported=bmwdb.import_csv(self.conn,ROOT/'generated/bmw_synthetic_configurator_logs (1).csv')
        metrics=self.client.get('/api/v1/configurator/metrics?model_code=F70').json()
        self.assertEqual(metrics['completion']['denominator'],112);self.assertEqual(metrics['data_origin'],'synthetic')
        empty=self.client.get('/api/v1/configurator/metrics?model_code=G60&market_code=EU').json()
        self.assertIsNone(empty['completion']['percentage'])
        self.conn.execute("UPDATE configurator_sessions SET final_stage='Engine_Selection' WHERE model_code='G60'")
        zero=self.client.get('/api/v1/configurator/metrics?model_code=G60').json()
        self.assertEqual(zero['completion']['percentage'],0)
        self.assertEqual(self.client.get('/api/v1/configurator/metrics?start=2026-10-01T00:00:00').status_code,422)

    def test_persistent_decision_audit_and_stale_revision(self):
        draft=self.draft();self.assertEqual(draft.status_code,201,draft.text);id=draft.json()['id']
        approved=self.action(id);self.assertEqual(approved.status_code,200,approved.text)
        self.assertEqual(approved.json()['status'],'approved');self.assertEqual(approved.json()['current_revision'],2)
        self.assertEqual(self.action(id,action='reject').status_code,409)
        # New app/client simulates a backend restart with fresh connection/token.
        app=create_app(testing=True)
        with TestClient(app) as fresh:
            stored=fresh.get('/api/v1/requirements/'+id).json();self.assertEqual(stored['status'],'approved')
            events=fresh.get(f'/api/v1/requirements/{id}/audit').json()['items'];self.assertEqual(len(events),2)
            self.assertEqual(events[-1]['actor'],'Development PM (non-production)')
            export=fresh.get(f'/api/v1/requirements/{id}/export').json();self.assertEqual(export['requirement']['priority_score'],None)
        with self.assertRaises(psycopg.errors.RaiseException):self.conn.execute('DELETE FROM audit_events')

    def test_edit_reject_postpone_and_missing_specification(self):
        draft=self.draft(target_value=None).json();id=draft['id']
        self.assertEqual(draft['specification_status'],'needs_specification')
        self.assertEqual(self.action(id).status_code,422)
        postponed=self.action(id,action='postpone',unscheduled=True);self.assertEqual(postponed.status_code,200,postponed.text)
        self.assertEqual(postponed.json()['current_revision'],2)
        content={k:postponed.json()[k] for k in ['title','statement','baseline_value','target_value','unit','conditions','acceptance_test','owner']}
        content['title']='Edited requirement'
        edit=self.action(id,action='edit',revision=2,content=content);self.assertEqual(edit.status_code,200,edit.text)
        self.assertEqual(edit.json()['status'],'draft');self.assertEqual(edit.json()['current_revision'],3)
        rejected=self.action(id,action='reject',revision=3);self.assertEqual(rejected.status_code,200)
        self.assertEqual(self.action(id,action='approve',revision=4).status_code,422)
        self.assertEqual(self.client.get('/api/v1/requirements?model_code=G60&priority=unscored').json()['total'],1)

    def test_validation_permissions_csrf_and_safe_paths(self):
        self.assertEqual(self.draft(actor='Fake PM').status_code,422)
        with patch.dict(os.environ,{'BMW_DEV_PM':'0'}):self.assertEqual(self.draft().status_code,403)
        self.assertEqual(self.client.post('/api/v1/requirements',json={},headers={}).status_code,403)
        self.assertEqual(self.draft(category_id='C99').status_code,422)
        self.assertEqual(self.client.get('/api/v1/feedback?page_size=1000').status_code,422)
        for path in ['/api.txt','/.env','/data/assets/anything','/../api.txt','/BMW_database_package.zip']:
            self.assertIn(self.client.get(path).status_code,[400,404])
        self.assertEqual(self.client.get('/api/v1/health').json()['capabilities']['research'],False)
        self.assertEqual(self.client.post('/api/v1/research/jobs',json={},headers=self.headers).status_code,503)

    def test_atomic_workflow_failure(self):
        self.conn.execute("CREATE FUNCTION fail_audit() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RAISE EXCEPTION ''fixture failure''; END'")
        self.conn.execute('CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events FOR EACH ROW EXECUTE FUNCTION fail_audit()')
        response=self.draft();self.assertEqual(response.status_code,503)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM requirements').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM problem_proposals').fetchone()[0],0)

    def test_pipeline_adapter_context_and_short_reports(self):
        url='https://example.com/source';text='Brakes failed.'
        raw={'source_platform':'Reddit','source_url':url,'thread_title':'Safety report','post_body':text,'timestamp':None,'target_platform':'G60','collected_at':'2026-10-10T12:00:00Z'}
        signals=[{'signal_id':'abc','source_platform':'Reddit','source_url':url,'timestamp':'2026-10-10T12:00:00Z','target_platform':'G60','taxonomy_category':'C04','cleaned_verbatim_text':text}]
        bundle={'namespace':'fixture','data_origin':'synthetic','raw':[raw,{**raw,'target_platform':'F70'}],'signals':signals,
                'run':{'algorithm_version':'fixture-1','model_name':'mock','prompt_version':'mock-1','taxonomy_version':'pipeline-0.1'}}
        path=Path(self.temp.name)/'pipeline.json';path.write_text(json.dumps(bundle))
        report=import_pipeline(self.conn,path);self.assertEqual(report['evidence_records'],2)
        self.assertTrue(import_pipeline(self.conn,path)['reimport'])
        rows=self.conn.execute("SELECT model_code,statement,category_id,safety_review FROM evidence_items WHERE evidence_kind='derived_assessment' ORDER BY id").fetchall()
        self.assertEqual({r[0] for r in rows},{'G60','F70'});self.assertIsNone(rows[0][2]);self.assertTrue(rows[0][3])
        self.assertEqual(rows[0][1],text)
        self.assertEqual(self.client.get('/api/v1/evidence?model_code=G60&evidence_kind=derived_assessment').json()['total'],1)

    def test_migration_checksum_rejects_real_changes(self):
        self.conn.execute("UPDATE schema_migrations SET sha256=%s WHERE name='001_foundation.sql'",('0'*64,))
        with self.assertRaisesRegex(ValueError,'Previously applied migration changed'):bmwdb.migrate(self.conn)


if __name__=='__main__':unittest.main()
