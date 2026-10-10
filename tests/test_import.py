import csv
import os
import tempfile
import unittest
import uuid
from pathlib import Path
import bmwdb

SOURCE = Path(__file__).resolve().parents[1] / 'generated/bmw_synthetic_configurator_logs (1).csv'


def fixture(changes=None, duplicate=False):
    with SOURCE.open(newline='',encoding='utf-8') as f:
        row = next(csv.DictReader(f))
    row.update(changes or {})
    folder = tempfile.TemporaryDirectory()
    path = Path(folder.name)/'fixture.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        writer = csv.DictWriter(f,fieldnames=bmwdb.FIELDS)
        writer.writeheader()
        writer.writerow(row)
        if duplicate:
            writer.writerow({**row,'Causality_Score':'99'})
    return folder,path


class ValidationTests(unittest.TestCase):
    def test_supplied_file(self):
        rows,report = bmwdb.validate(SOURCE)
        self.assertEqual(report['sha256'],'c0679f8023efa0487d72d8cbaf6d5c22ca4f4e02cd07cd94721f7adfd4933ce3')
        self.assertEqual((report['valid_sessions'],report['option_views'],report['option_selections']),(240,1534,709))
        self.assertEqual(report['scores_above_30'],180)
        self.assertEqual(report['distinct_option_codes'],12)
        self.assertFalse(report['issues'])

    def test_bad_values_and_empty_selection(self):
        for change,valid in [({'Option_Codes_Viewed':'bad'},False),({'Package_Attach_Success':'yes'},False),
                             ({'Option_Codes_Selected':'["SA999"]'},False),({'Option_Codes_Selected':'[]'},True),
                             ({'Timestamp':'2026-10-10T12:00:00'},False),({'Causality_Score':'NaN'},False)]:
            with self.subTest(change=change):
                folder,path=fixture(change)
                with folder:
                    self.assertEqual(bmwdb.validate(path)[1]['valid_sessions'],int(valid))

    def test_conflicting_duplicate(self):
        folder,path=fixture(duplicate=True)
        with folder:
            self.assertEqual(bmwdb.validate(path)[1]['quarantined_rows'],2)


@unittest.skipUnless(os.environ.get('BMW_TEST_DATABASE_URL'),'Set BMW_TEST_DATABASE_URL for PostgreSQL tests')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from psycopg import sql
        self.conn=psycopg.connect(os.environ['BMW_TEST_DATABASE_URL'],autocommit=True)
        self.schema='test_'+uuid.uuid4().hex
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
        bmwdb.migrate(self.conn)

    def tearDown(self):
        from psycopg import sql
        self.conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.conn.close()

    def count(self,table):
        from psycopg import sql
        return self.conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]

    def test_fresh_migration_and_constraints(self):
        import psycopg
        bmwdb.migrate(self.conn)
        self.assertEqual(self.count('categories'),10)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute("INSERT INTO models VALUES ('bad','missing')")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute("INSERT INTO categories VALUES ('C01','duplicate')")

    def test_import_reimport_and_snapshots(self):
        first=bmwdb.import_csv(self.conn,SOURCE)
        second=bmwdb.import_csv(self.conn,SOURCE)
        self.assertEqual(first['version_id'],second['version_id'])
        self.assertTrue(second['reimport'])
        self.assertEqual(self.count('configurator_sessions'),240)
        self.assertEqual(self.count('configurator_session_options'),1534)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM configurator_session_options WHERE selected').fetchone()[0],709)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM configurator_sessions WHERE variant_id IS NULL AND data_origin='synthetic'").fetchone()[0],240)
        folder,path=fixture({'Option_Codes_Selected':'[]'})
        with folder:
            changed=bmwdb.import_csv(self.conn,path)
        self.assertNotEqual(first['version_id'],changed['version_id'])
        self.assertEqual(self.count('dataset_versions'),2)

    def test_quarantine_preserves_raw_and_duplicates(self):
        for change,duplicate in [({'Option_Codes_Viewed':'bad'},False),({'Package_Attach_Success':'yes'},False),({'Option_Codes_Selected':'["SA999"]'},False),({},True)]:
            folder,path=fixture(change,duplicate)
            with folder:
                report=bmwdb.import_csv(self.conn,path,namespace=str(uuid.uuid4()))
                self.assertGreater(report['quarantined_rows'],0)
        self.assertEqual(self.count('source_records'),5)
        self.assertEqual(self.count('configurator_sessions'),0)
        self.assertEqual(self.count('validation_issues'),5)

    def test_import_rolls_back_on_database_failure(self):
        import psycopg
        self.conn.execute("CREATE FUNCTION reject_option() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RAISE EXCEPTION ''test failure''; END'")
        self.conn.execute('CREATE TRIGGER reject_option BEFORE INSERT ON configurator_session_options FOR EACH ROW EXECUTE FUNCTION reject_option()')
        with self.assertRaises(psycopg.errors.RaiseException):
            bmwdb.import_csv(self.conn,SOURCE)
        for table in ['datasets','source_assets','dataset_versions','source_records','scenarios','ingestion_runs','configurator_sessions','configurator_session_options']:
            self.assertEqual(self.count(table),0,table)


if __name__=='__main__':
    unittest.main()
