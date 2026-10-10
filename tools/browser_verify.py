"""Isolated Playwright tests; external requests blocked, schema cleaned up."""
import csv
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from openpyxl import Workbook
from playwright.sync_api import sync_playwright,expect
import bmwdb
from backend.ingest import HEADERS,import_feedback
from tools.configure_local_role import configure

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/browser'


def main():
    dsn=os.environ.get('BMW_TEST_DATABASE_URL')
    if not dsn:raise SystemExit('BMW_TEST_DATABASE_URL required; no fallback to demo or production')
    OUT.mkdir(parents=True,exist_ok=True)
    schema='browser_'+uuid.uuid4().hex
    conn=psycopg.connect(dsn,autocommit=True)
    conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
    process=None;logs=[];checks=[]
    try:
        bmwdb.migrate(conn)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'feedback.xlsx';book=Workbook();sheet=book.active;sheet.title='Feedback_Explorer';sheet.append(HEADERS)
            for i in range(45):
                text='<img src=x onerror="window.INJECTED=true">Seat fixture' if i==0 else f'Synthetic fixture seat feedback {i:02d}'
                sheet.append([f'FIX{i}','fixture','BMW','unknown','US','G60','unknown','Want',text,'Seats',None,None])
            book.save(path);book.close();import_feedback(conn,path,'G60')
        bmwdb.import_csv(conn,ROOT/'generated/bmw_synthetic_configurator_logs (1).csv')
        configure(conn)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        origin=f'http://127.0.0.1:{port}'
        app_dsn=make_conninfo(dsn,user='bmw_demo_app',options=f'-csearch_path={schema}')
        env={**os.environ,'BMW_DATABASE_URL':app_dsn,'BMW_DEV_PM':'1','BMW_APP_ORIGIN':origin,'BMW_PORT':str(port)}
        def start():
            log=(OUT/'test-api.log').open('a',encoding='utf-8');logs.append(log)
            proc=subprocess.Popen([sys.executable,'-m','backend'],cwd=ROOT,env=env,stdout=log,stderr=log,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:
                    if httpx.get(origin+'/api/v1/health',timeout=1).status_code==200:return proc
                except httpx.HTTPError:pass
                if proc.poll() is not None:raise RuntimeError('Fixture API failed to start; see test-api.log')
                time.sleep(.15)
            proc.terminate();proc.wait(timeout=10);raise RuntimeError('Fixture API readiness timeout')
        process=start()
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000})
            def route(request_route):
                if request_route.request.url.startswith(origin+'/'):request_route.continue_()
                else:request_route.abort()
            context.route('**/*',route)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin);expect(page.locator('#connection')).to_contain_text('PostgreSQL connected')
            expect(page.locator('#k-feedback')).to_have_text('45');expect(page.locator('#k-sessions')).to_have_text('90')
            expect(page.locator('#scope-table-body tr')).to_have_count(20)
            checks.append('connected data and pagination')
            page.locator('#next').click();expect(page.locator('#list-count')).to_contain_text('page 2');page.locator('#previous').click();expect(page.locator('#list-count')).to_contain_text('page 1')
            page.locator('#sort').select_option('title');expect(page.locator('#scope-table-body tr')).to_have_count(20)
            page.locator('#scope-table-body .record-button').first.click();expect(page.locator('#detail')).to_contain_text('<img src=x')
            assert not page.evaluate('Boolean(window.INJECTED)');checks.append('escaped malicious evidence and source detail')
            page.locator('#draft-requirement').click();form=page.locator('#draft-form')
            for name,value in {'title':'Browser fixture requirement','statement':'Meet the test comfort target','target_value':'3','unit':'points','owner':'Fixture PM','conditions':'Synthetic test condition','acceptance_test':'Synthetic test measurement','rationale':'Test-only evidence selection'}.items():form.locator(f'[name="{name}"]').fill(value)
            form.locator('button[type=submit]').click();expect(page.locator('#action-form')).to_be_visible();expect(page.locator('#decision-label')).to_contain_text('revision 1')
            id=page.locator('#scope-table-body .record-button').first.get_attribute('data-record-id')
            # Second window holds stale revision while first window approves.
            stale=context.new_page();stale.goto(origin);expect(stale.locator('#connection')).to_contain_text('PostgreSQL connected');stale.locator('[data-tab=requirements]').click();stale.locator('#scope-table-body .record-button').first.click();expect(stale.locator('#action-form')).to_be_visible()
            page.locator('#action-form [name=rationale]').fill('Fixture approval for persistence test');page.locator('#action-form button[type=submit]').click();expect(page.locator('#decision-label')).to_contain_text('approved · revision 2');expect(page.locator('#audit')).to_contain_text('Fixture approval')
            stale.locator('#pm-action').select_option('reject');stale.locator('#action-form [name=rationale]').fill('Stale fixture decision');stale.locator('#action-form button[type=submit]').click();expect(stale.locator('.form-status')).to_contain_text('changed in another window');stale.get_by_role('button',name='Reload stored revision').click();expect(stale.locator('#decision-label')).to_contain_text('revision 2')
            stale.close();checks.append('decision saved, 409 stale recovery and audit')
            page.reload();expect(page.locator('#connection')).to_contain_text('PostgreSQL connected');page.locator('[data-tab=requirements]').click();page.locator('#scope-table-body .record-button').first.click();expect(page.locator('#decision-label')).to_contain_text('approved')
            process.terminate();process.wait(timeout=10);process=start();page.reload();expect(page.locator('#connection')).to_contain_text('PostgreSQL connected');page.locator('[data-tab=requirements]').click();page.locator('#scope-table-body .record-button').first.click();expect(page.locator('#decision-label')).to_contain_text('approved');checks.append('decision survives backend restart')
            page.locator('#unscored').uncheck();expect(page.locator('#list-status')).to_contain_text('Unscored records are hidden');page.locator('#unscored').check();expect(page.locator('#scope-table-body tr')).to_have_count(1)
            page.locator('[data-tab=feedback]').click();page.locator('#derivative').select_option('F70');expect(page.locator('#k-feedback')).to_have_text('0');expect(page.locator('#k-sessions')).to_have_text('112')
            page.locator('#market').select_option('CN');expect(page.locator('#k-sessions')).to_have_text('27')
            page.locator('#derivative').select_option('G60');page.locator('#market').select_option('US');expect(page.locator('#k-feedback')).to_have_text('45')
            page.locator('#search').fill('absent-fixture-term');expect(page.locator('#list-status')).to_contain_text('No records match');page.locator('#search').fill('');expect(page.locator('#scope-table-body tr')).to_have_count(20)
            checks.append('model, China, search, Unscored and refresh filters')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.screenshot(path=str(OUT/'mobile.png'),full_page=True);checks.append('desktop/mobile no page overflow')
            # Unavailable provider is honest and no automatic job was triggered.
            expect(page.locator('#providers')).to_contain_text('disabled')
            context.route('**/api/v1/feedback?**',lambda r:r.fulfill(status=503,content_type='application/json',body=json.dumps({'error':{'message':'Fixture database unavailable'}})))
            page.locator('#refresh').click();expect(page.locator('#connection')).to_contain_text('unavailable');expect(page.locator('#scope-table-body tr')).to_have_count(0);expect(page.locator('#k-feedback')).to_have_text('—');checks.append('database unavailable with no embedded fallback')
            assert not errors,errors
            browser.close()
        summary={'checks':checks,'page_errors':errors,'external_network':'blocked','data':'isolated synthetic fixtures','schema_cleanup':'completed after run'}
        (OUT/'results.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=10)
        for log in logs:log.close()
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)));conn.close()


if __name__=='__main__':main()
