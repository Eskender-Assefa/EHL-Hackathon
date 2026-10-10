from fastapi import HTTPException
from .database import one,all_rows


def versions(conn,version_id=None):
    if version_id:
        if not one(conn,'SELECT id FROM dataset_versions WHERE id=%s',(int(version_id),)):
            raise HTTPException(422,'Unknown dataset version')
        return [int(version_id)]
    return [r['id'] for r in all_rows(conn,'SELECT max(id) AS id FROM dataset_versions GROUP BY dataset_id ORDER BY max(id)')]


def check_market(conn,market):
    if market and not one(conn,'SELECT code FROM markets WHERE code=%s',(market,)):
        raise HTTPException(422,'Unknown market')


def clauses(conn,f,alias='e',include_kind=True):
    check_market(conn,f.market_code)
    selected=versions(conn,f.version_id)
    where=[f'{alias}.model_code=%s',f'{alias}.version_id=ANY(%s)']
    params=[f.model_code,selected]
    for key in ['market_code','category_id','scope_layer','data_origin','review_status']:
        value=getattr(f,key)
        if value is not None:
            where.append(f'{alias}.{key}=%s'); params.append(value)
    if include_kind and f.evidence_kind:
        where.append(f'{alias}.evidence_kind=%s');params.append(f.evidence_kind)
    if f.unknown_market_only:
        where.append(f'{alias}.market_code IS NULL')
    if f.q:
        where.append(f'({alias}.title ILIKE %s OR {alias}.statement ILIKE %s)')
        params.extend(['%'+f.q+'%']*2)
    return where,params,selected


EVIDENCE_SELECT='''SELECT e.*,e.id::text AS id,e.version_id::text AS version_id,
 e.source_record_id::text AS source_record_id,e.feedback_id::text AS feedback_id,e.variant_id::text AS variant_id,
 d.namespace,sa.original_filename AS source_filename,dv.metadata AS dataset_context,
 (SELECT jsonb_agg(jsonb_build_object('page',l.page,'sheet',l.sheet,'cell_range',l.cell_range,'row_number',l.row_number) ORDER BY l.id)
  FROM evidence_locations l WHERE l.record_id=e.source_record_id) AS source_locations,
 (SELECT count(*) FROM feedback_tags ft WHERE ft.feedback_id=e.feedback_id) AS tag_count
 FROM evidence_items e JOIN dataset_versions dv ON dv.id=e.version_id
 JOIN datasets d ON d.id=dv.dataset_id JOIN source_assets sa ON sa.id=dv.asset_id'''


def evidence_list(conn,f,kind):
    where,params,selected=clauses(conn,f)
    if kind:
        where.append('e.evidence_kind=%s');params.append(kind)
    predicate=' AND '.join(where)
    total=one(conn,'SELECT count(*) AS n FROM evidence_items e WHERE '+predicate,params)['n']
    order=f'e.{f.sort} {f.direction}, e.id {f.direction}'
    items=all_rows(conn,EVIDENCE_SELECT+' WHERE '+predicate+' ORDER BY '+order+' LIMIT %s OFFSET %s',params+[f.page_size,(f.page-1)*f.page_size])
    return page(items,total,f,selected)


def evidence_detail(conn,id,kind=None):
    item=one(conn,EVIDENCE_SELECT+' WHERE e.id=%s',(int(id),))
    if not item or (kind and item['evidence_kind']!=kind):
        raise HTTPException(404,'Evidence not found')
    if item['feedback_id']:
        item['tags']=all_rows(conn,'''SELECT ft.id::text AS id,ft.source_record_id::text AS source_record_id,
            ft.original_tags,l.sheet,l.row_number,l.cell_range FROM feedback_tags ft
            JOIN evidence_locations l ON l.record_id=ft.source_record_id
            WHERE ft.feedback_id=%s ORDER BY ft.id''',(int(item['feedback_id']),))
    return item


def page(items,total,f,selected):
    effective=f.model_dump()
    effective['version_ids']=[str(v) for v in selected]
    effective['version_policy']='explicit' if f.version_id else 'latest snapshot per dataset'
    return {'items':items,'total':total,'page':f.page,'page_size':f.page_size,'effective_filters':effective}


def requirement_detail(conn,id):
    r=one(conn,'''SELECT r.*,r.id::text AS id,r.problem_id::text AS problem_id,
        rv.title,rv.statement,rv.baseline_value,rv.target_value,rv.unit,rv.conditions,rv.acceptance_test,rv.owner,rv.specification_status
        FROM requirements r JOIN requirement_versions rv ON rv.requirement_id=r.id AND rv.revision=r.current_revision WHERE r.id=%s''',(int(id),))
    if not r:
        raise HTTPException(404,'Requirement not found')
    ids=all_rows(conn,'SELECT evidence_id FROM requirement_evidence WHERE requirement_id=%s AND revision=%s ORDER BY evidence_id',(int(id),r['current_revision']))
    r['evidence']=[evidence_detail(conn,x['evidence_id']) for x in ids]
    r['data_origins']=sorted({e['data_origin'] for e in r['evidence']})
    r['review_status']='reviewed' if r['status'] in ['approved','rejected','postponed'] else 'unreviewed'
    r.update(priority_status='unscored',priority_score=None,priority_reason='No approved scoring policy and validated inputs',permission_note='Approval is a PM decision, not verification of product facts')
    return r


def workflow_list(conn,f,problems=False):
    check_market(conn,f.market_code)
    selected=versions(conn,f.version_id)
    table='problem_proposals' if problems else 'requirements'
    where=['r.model_code=%s'];params=[f.model_code]
    for key in ['market_code','category_id','scope_layer']:
        value=getattr(f,key)
        if value:
            where.append(f'r.{key}=%s');params.append(value)
    if f.unknown_market_only:
        where.append('r.market_code IS NULL')
    if f.q:
        where.append(('r.title' if problems else 'rv.title')+' ILIKE %s');params.append('%'+f.q+'%')
    evidence_where=['e.version_id=ANY(%s)'];eparams=[selected]
    for key in ['data_origin','evidence_kind','review_status']:
        value=getattr(f,key)
        if value:
            evidence_where.append(f'e.{key}=%s');eparams.append(value)
    link='problem_evidence' if problems else 'requirement_evidence'
    parent='problem_id' if problems else 'requirement_id'
    where.append(f"EXISTS(SELECT 1 FROM {link} re JOIN evidence_items e ON e.id=re.evidence_id WHERE re.{parent}=r.id "+('' if problems else 'AND re.revision=r.current_revision ')+"AND "+' AND '.join(evidence_where)+')')
    params.extend(eparams)
    join='' if problems else ' JOIN requirement_versions rv ON rv.requirement_id=r.id AND rv.revision=r.current_revision'
    predicate=' AND '.join(where)
    total=one(conn,f'SELECT count(*) AS n FROM {table} r'+join+' WHERE '+predicate,params)['n']
    sort=('r.title' if problems else 'rv.title') if f.sort=='title' else 'r.id'
    ids=all_rows(conn,f'SELECT r.id FROM {table} r'+join+' WHERE '+predicate+f' ORDER BY {sort} {f.direction},r.id {f.direction} LIMIT %s OFFSET %s',params+[f.page_size,(f.page-1)*f.page_size])
    if problems:
        items=[problem_detail(conn,x['id']) for x in ids]
    else:
        items=[requirement_detail(conn,x['id']) for x in ids]
    return page(items,total,f,selected)


def problem_detail(conn,id):
    r=one(conn,'SELECT p.*,id::text AS id FROM problem_proposals p WHERE id=%s',(int(id),))
    if not r:
        raise HTTPException(404,'Problem not found')
    ids=all_rows(conn,'SELECT evidence_id FROM problem_evidence WHERE problem_id=%s ORDER BY evidence_id',(int(id),))
    r['evidence']=[evidence_detail(conn,x['evidence_id']) for x in ids]
    r['data_origins']=sorted({e['data_origin'] for e in r['evidence']})
    r['priority_score']=None
    return r


def audit(conn,id):
    requirement_detail(conn,id)
    return all_rows(conn,'''SELECT id::text AS id,requirement_id::text AS requirement_id,revision,action,actor,rationale,before_state,after_state,created_at
        FROM audit_events WHERE requirement_id=%s ORDER BY id''',(int(id),))


def metrics(conn,model,market,version_id=None,start=None,end=None,origin=None,unknown_market_only=False):
    check_market(conn,market)
    if start and end and start>=end:
        raise HTTPException(422,'End must follow start; period is [start,end)')
    selected=versions(conn,version_id)
    where=['s.model_code=%s','s.version_id=ANY(%s)'];params=[model,selected]
    if market:where.append('s.market_code=%s');params.append(market)
    if origin:where.append('s.data_origin=%s');params.append(origin)
    if unknown_market_only:where.append('s.market_code IS NULL')
    if start:where.append('s.source_timestamp>=%s');params.append(start)
    if end:where.append('s.source_timestamp<%s');params.append(end)
    predicate=' AND '.join(where)
    totals=one(conn,'''SELECT count(*) AS denominator,count(*) FILTER(WHERE final_stage='Completed') AS numerator,
        min(source_timestamp) AS source_timestamp_min,max(source_timestamp) AS source_timestamp_max FROM configurator_sessions s WHERE '''+predicate,params)
    n,d=totals['numerator'],totals['denominator']
    options=all_rows(conn,'''SELECT o.option_code,count(DISTINCT s.id) AS denominator,count(DISTINCT s.id) FILTER(WHERE o.selected) AS numerator
        FROM configurator_sessions s JOIN configurator_session_options o ON o.session_id=s.id WHERE '''+predicate+' GROUP BY o.option_code ORDER BY o.option_code',params)
    for o in options:
        o['percentage']=round(o['numerator']/o['denominator']*100,2) if o['denominator'] else None
        o['mapping_status']='unresolved'
    stages=all_rows(conn,'SELECT final_stage,count(*) AS count FROM configurator_sessions s WHERE '+predicate+' GROUP BY final_stage ORDER BY final_stage',params)
    actual_versions=all_rows(conn,'SELECT DISTINCT version_id::text AS id FROM configurator_sessions s WHERE '+predicate+' ORDER BY id',params)
    return {'data_origin':'synthetic','label':'Synthetic session measures','version_ids':[r['id'] for r in actual_versions],
        'effective_filters':{'model_code':model,'market_code':market,'version_id':version_id,'version_policy':'explicit' if version_id else 'latest snapshot per dataset','data_origin':origin,'unknown_market_only':unknown_market_only,'start':start,'end':end},
        'period':{'start':start,'end_exclusive':end,'source_timestamp_min':totals['source_timestamp_min'],'source_timestamp_max':totals['source_timestamp_max'],'timestamp_meaning':'unknown'},
        'completion':{'numerator':n,'denominator':d,'percentage':round(n/d*100,2) if d else None,'unavailable_reason':None if d else 'No sessions in selected cohort'},
        'options':options,'final_stages':stages,'limitations':['Sessions are not purchases or unique people','Raw synthetic score excluded','No sequential funnel inferred','Option availability unverified']}
