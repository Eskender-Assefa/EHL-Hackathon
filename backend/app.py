"""Same-origin local HTTP API. Synchronous routes keep psycopg off the event loop."""
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import database,queries,workflow
from .schemas import Action,Draft,Filters,Page,Model,Origin

Id = Annotated[str,ApiPath(pattern=r'^[1-9][0-9]{0,17}$')]


def get_db():
    with database.connection() as conn:
        yield conn


def create_app(*,testing=False):
    app=FastAPI(title='BMW Product Decision Studio',version='1.0.0')
    app.state.testing=testing
    app.state.csrf=secrets.token_urlsafe(32)
    app.state.origin=os.environ.get('BMW_APP_ORIGIN','http://127.0.0.1:8765').rstrip('/')
    parsed=urlsplit(app.state.origin)
    if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost','::1']:
        raise ValueError('This development API requires a loopback HTTP origin')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]']+(['testserver'] if testing else []))

    @app.middleware('http')
    async def security_headers(request,call_next):
        if request.method not in ['GET','HEAD','OPTIONS']:
            try:length=int(request.headers.get('content-length','0'))
            except ValueError:return JSONResponse({'error':{'code':400,'message':'Invalid content length'}},status_code=400)
            if length>65536:return JSONResponse({'error':{'code':413,'message':'Request too large'}},status_code=413)
            if request.headers.get('origin')!=app.state.origin or request.headers.get('x-bmw-csrf')!=app.state.csrf:
                return JSONResponse({'error':{'code':403,'message':'Same-origin request and CSRF token required'}},status_code=403)
            chunks=[];size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>65536:return JSONResponse({'error':{'code':413,'message':'Request too large'}},status_code=413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        return JSONResponse({'error':{'code':exc.status_code,'message':exc.detail}},status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        issues=[{'field':'.'.join(str(x) for x in e['loc']),'message':e['msg']} for e in exc.errors()]
        return JSONResponse({'error':{'code':422,'message':'Validation failed','issues':issues}},status_code=422)

    @app.exception_handler(psycopg.Error)
    async def database_error(request,exc):
        if isinstance(exc,psycopg.IntegrityError):
            return JSONResponse({'error':{'code':422,'message':'Record conflicts with database constraints'}},status_code=422)
        return JSONResponse({'error':{'code':503,'message':'Database unavailable; retry after checking the local service'}},status_code=503)

    def pm(request:Request):
        peers=['127.0.0.1','::1']+(['testclient'] if testing else [])
        if os.environ.get('BMW_DEV_PM')!='1' or not request.client or request.client.host not in peers:
            raise HTTPException(403,'PM decisions require the explicitly enabled loopback development identity')
        return 'Development PM (non-production)'

    @app.get('/api/v1/health')
    def health():
        ready=False
        try:
            with database.connection() as conn:
                ready=database.one(conn,"SELECT count(*) AS n FROM schema_migrations WHERE name='002_evidence_workflow.sql'")['n']==1
        except psycopg.Error:pass
        return JSONResponse({'database':{'ready':ready,'status':'ready' if ready else 'unavailable'},
            'capabilities':{'research':False,'classification':False,'uploads':False},
            'identity':{'enabled':os.environ.get('BMW_DEV_PM')=='1','label':'Development PM (non-production)'},
            'csrf_token':app.state.csrf,'priority':{'status':'unscored','reason':'No approved policy'}},status_code=200 if ready else 503)

    @app.get('/api/v1/models')
    def models(conn=Depends(get_db)):
        return {'items':database.all_rows(conn,"SELECT code AS id,brand_id FROM models WHERE code IN ('F70','G60','G70') ORDER BY code")}

    @app.get('/api/v1/markets')
    def markets(conn=Depends(get_db)):
        return {'items':database.all_rows(conn,'SELECT code AS id,kind FROM markets ORDER BY code'),'unknown_market_supported':True}

    @app.get('/api/v1/categories')
    def categories(conn=Depends(get_db)):
        return {'items':database.all_rows(conn,'SELECT id,label FROM categories ORDER BY id'),'taxonomy_version':'baseline-v2.0','authority':'Project-defined taxonomy'}

    @app.get('/api/v1/datasets')
    def datasets(conn=Depends(get_db)):
        return {'items':database.all_rows(conn,'''SELECT dv.id::text AS id,d.namespace,d.evidence_kind,dv.data_origin,dv.created_at,
            sa.original_filename AS source_filename,sa.sha256,dv.metadata,dv.id=(SELECT max(v.id) FROM dataset_versions v WHERE v.dataset_id=d.id) AS is_current,
            (SELECT count(*) FROM evidence_items e WHERE e.version_id=dv.id) AS evidence_count,
            (SELECT count(*) FROM source_records r WHERE r.version_id=dv.id) AS source_record_count
            FROM dataset_versions dv JOIN datasets d ON d.id=dv.dataset_id JOIN source_assets sa ON sa.id=dv.asset_id ORDER BY dv.id'''),
            'default_policy':'latest snapshot per dataset; no summing repeated snapshots'}

    @app.get('/api/v1/feedback',response_model=Page)
    def feedback(filters:Annotated[Filters,Query()],conn=Depends(get_db)):
        return queries.evidence_list(conn,filters,'customer_statement')

    @app.get('/api/v1/evidence',response_model=Page)
    def evidence(filters:Annotated[Filters,Query()],conn=Depends(get_db)):
        return queries.evidence_list(conn,filters,None)

    @app.get('/api/v1/catalogue-facts',response_model=Page)
    def catalogue(filters:Annotated[Filters,Query()],conn=Depends(get_db)):
        return queries.evidence_list(conn,filters,'published_specification')

    @app.get('/api/v1/feedback/{id}')
    def feedback_detail(id:Id,conn=Depends(get_db)):
        return queries.evidence_detail(conn,id,'customer_statement')

    @app.get('/api/v1/catalogue-facts/{id}')
    def catalogue_detail(id:Id,conn=Depends(get_db)):
        return queries.evidence_detail(conn,id,'published_specification')

    @app.get('/api/v1/evidence/{id}')
    def evidence_detail(id:Id,conn=Depends(get_db)):
        return queries.evidence_detail(conn,id)

    @app.get('/api/v1/problems',response_model=Page)
    def problems(filters:Annotated[Filters,Query()],conn=Depends(get_db)):
        return queries.workflow_list(conn,filters,problems=True)

    @app.get('/api/v1/problems/{id}')
    def problem(id:Id,conn=Depends(get_db)):
        return queries.problem_detail(conn,id)

    @app.get('/api/v1/requirements',response_model=Page)
    def requirements(filters:Annotated[Filters,Query()],conn=Depends(get_db)):
        return queries.workflow_list(conn,filters)

    @app.get('/api/v1/requirements/{id}')
    def requirement(id:Id,conn=Depends(get_db)):
        return queries.requirement_detail(conn,id)

    @app.post('/api/v1/requirements',status_code=201)
    def draft(payload:Draft,actor=Depends(pm),conn=Depends(get_db)):
        return workflow.create(conn,payload,actor)

    @app.post('/api/v1/requirements/{id}/actions')
    def action(id:Id,payload:Action,actor=Depends(pm),conn=Depends(get_db)):
        return workflow.act(conn,id,payload,actor)

    @app.get('/api/v1/requirements/{id}/audit')
    def audit(id:Id,conn=Depends(get_db)):
        return {'items':queries.audit(conn,id)}

    @app.get('/api/v1/requirements/{id}/export')
    def export(id:Id,conn=Depends(get_db)):
        return {'requirement':queries.requirement_detail(conn,id),'audit':queries.audit(conn,id),
            'revisions':database.all_rows(conn,'''SELECT requirement_id::text AS requirement_id,revision,title,statement,baseline_value,target_value,unit,conditions,acceptance_test,owner,specification_status,created_by,created_at
                FROM requirement_versions WHERE requirement_id=%s ORDER BY revision''',(int(id),))}

    @app.get('/api/v1/configurator/metrics')
    def metrics(model_code:Model='G60',market_code:Annotated[str|None,Query(pattern=r'^[A-Z]{2}$')]=None,
                version_id:Annotated[str|None,Query(pattern=r'^[1-9][0-9]{0,17}$')]=None,
                start:datetime|None=None,end:datetime|None=None,data_origin:Origin|None=None,
                unknown_market_only:bool=False,conn=Depends(get_db)):
        if any(t and t.utcoffset() is None for t in [start,end]):raise HTTPException(422,'Dates require timezone offsets')
        if unknown_market_only and market_code:raise HTTPException(422,'Choose a country or unknown market')
        return queries.metrics(conn,model_code,market_code,version_id,start,end,data_origin,unknown_market_only)

    @app.post('/api/v1/research/jobs')
    @app.post('/api/v1/classification/jobs')
    def unavailable(actor=Depends(pm)):
        raise HTTPException(503,'Optional provider disabled; use explicit local pipeline fixture import instead')

    # No repository root, archive, reference HTML or credential path is served.
    app.mount('/',StaticFiles(directory=Path(__file__).resolve().parents[1]/'frontend',html=True),name='frontend')
    return app
