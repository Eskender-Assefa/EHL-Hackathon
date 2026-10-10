from fastapi import HTTPException
from psycopg.types.json import Jsonb
from .database import one,all_rows
from .queries import evidence_detail,requirement_detail
from .schemas import Content

CONTENT_FIELDS=['title','statement','baseline_value','target_value','unit','conditions','acceptance_test','owner']


def add_version(conn,id,rev,content,actor):
    values=[getattr(content,k) for k in CONTENT_FIELDS]
    conn.execute('''INSERT INTO requirement_versions(requirement_id,revision,title,statement,baseline_value,target_value,unit,conditions,acceptance_test,owner,specification_status,created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',[id,rev]+values+[content.specification_status(),actor])


def snapshot(r):
    return {'id':str(r['id']),'revision':r['current_revision'],'status':r['status'],
            **{key:(str(r[key]) if key=='target_value' and r[key] is not None else r[key]) for key in CONTENT_FIELDS},
            'specification_status':r['specification_status'],
            'review_date':str(r['review_date']) if r['review_date'] else None,
            'postponement_unscheduled':r['postponement_unscheduled']}


def event(conn,id,rev,action,actor,reason,before,after):
    conn.execute('''INSERT INTO audit_events(requirement_id,revision,action,actor,rationale,before_state,after_state)
        VALUES (%s,%s,%s,%s,%s,%s,%s)''',(id,rev,action,actor,reason,Jsonb(before) if before else None,Jsonb(after)))


def create(conn,draft,actor):
    with conn.transaction():
        evidence=[evidence_detail(conn,id) for id in draft.evidence_ids]
        if any(e['model_code']!=draft.model_code for e in evidence):
            raise HTTPException(422,'Evidence model does not match requirement')
        if any(e['market_code']!=draft.market_code for e in evidence):
            raise HTTPException(422,'Evidence market must match; use unknown-market scope for unknown applicability')
        if any(e['scope_layer']!=draft.scope_layer for e in evidence):
            raise HTTPException(422,'Evidence scope does not match requirement')
        # A category selected by the PM classifies this proposal, not its sources.
        problem=one(conn,'''INSERT INTO problem_proposals(model_code,market_code,category_id,scope_layer,title,summary,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id''',(draft.model_code,draft.market_code,draft.category_id,draft.scope_layer,draft.title,draft.statement,actor))['id']
        id=one(conn,'''INSERT INTO requirements(problem_id,model_code,market_code,category_id,scope_layer,created_by)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id''',(problem,draft.model_code,draft.market_code,draft.category_id,draft.scope_layer,actor))['id']
        add_version(conn,id,1,draft,actor)
        for eid in draft.evidence_ids:
            conn.execute('INSERT INTO problem_evidence VALUES (%s,%s)',(problem,int(eid)))
            conn.execute('INSERT INTO requirement_evidence VALUES (%s,1,%s)',(id,int(eid)))
        stored=requirement_detail(conn,id)
        event(conn,id,1,'create',actor,draft.rationale,None,snapshot(stored))
        return stored


def act(conn,id,action,actor):
    with conn.transaction():
        locked=one(conn,'SELECT current_revision,status FROM requirements WHERE id=%s FOR UPDATE',(int(id),))
        if not locked:raise HTTPException(404,'Requirement not found')
        if locked['current_revision']!=action.expected_revision:
            raise HTTPException(409,{'message':'Requirement changed; reload the stored revision','current_revision':locked['current_revision']})
        before=requirement_detail(conn,id)
        if action.action=='approve' and before['specification_status']!='specified':
            raise HTTPException(422,'Approval requires target, unit, conditions, acceptance test and owner')
        if action.action!='edit' and before['status'] in ['approved','rejected']:
            raise HTTPException(422,'Edit to reopen a terminal requirement before another decision')
        if action.action=='postpone' and before['status']=='postponed':
            raise HTTPException(422,'Edit a postponed requirement before postponing again')
        rev=before['current_revision']+1
        content=action.content or Content(**{k:before[k] for k in CONTENT_FIELDS})
        add_version(conn,int(id),rev,content,actor)
        conn.execute('''INSERT INTO requirement_evidence SELECT requirement_id,%s,evidence_id FROM requirement_evidence
            WHERE requirement_id=%s AND revision=%s''',(rev,int(id),before['current_revision']))
        status={'approve':'approved','edit':'draft','reject':'rejected','postpone':'postponed'}[action.action]
        conn.execute('UPDATE requirements SET current_revision=%s,status=%s,review_date=%s,postponement_unscheduled=%s,updated_at=now() WHERE id=%s',
                     (rev,status,action.review_date,action.unscheduled,int(id)))
        conn.execute('''INSERT INTO pm_decisions(requirement_id,resulting_revision,action,rationale,actor) VALUES (%s,%s,%s,%s,%s)''',
                     (int(id),rev,action.action,action.rationale,actor))
        stored=requirement_detail(conn,id)
        event(conn,int(id),rev,action.action,actor,action.rationale,snapshot(before),snapshot(stored))
        return stored
