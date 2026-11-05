"""Qualify HTTP behavior of a disposable Battery-created CaseAPI application.

Run inside battery-web after provisioning BatteryRestFixtureUser in disposable IRIS.
Uses a separate loopback web process/ledger; does not reconfigure the operator UI,
submit native cases, or call a model. Saves evidence and always attempts cleanup.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from battery.task_slice import IrisTaskAdapter, engine_from_environment
from battery.ship_native_cases import NativeCases


def main():
    parsed = urlsplit(os.environ['BATTERY_NATIVE_URL'])
    native = parsed.scheme + '://' + parsed.netloc
    password = os.environ['BATTERY_NATIVE_PASSWORD']
    access = os.environ['BATTERY_ACCESS_KEY']
    run = uuid.uuid4().hex[:12]
    name = '/battery-functional-' + run
    report = {'scope': 'HTTP behavior of a temporary REST application created through Battery on real IRIS', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'application': name, 'dispatch_class': 'Battery.Interop.CaseAPI', 'checks': [], 'model_calls': 0, 'baseline_commit': '83d17afa658ed316cfd118795e43080ff0b4c7f1'}
    client = build_opener(HTTPCookieProcessor(CookieJar()))
    adapter = IrisTaskAdapter(native + '/api/admin', 'Basic ' + base64.b64encode(('BatteryRestFixtureUser:' + password).encode()).decode())
    port = int(os.getenv('BATTERY_FUNCTIONAL_PORT', '18081'))
    local = 'http://127.0.0.1:' + str(port)
    output = ROOT / 'var/rest-functional-result.json'
    child = None
    log = None
    created = False
    def basic(user, secret):
        return 'Basic ' + base64.b64encode((user + ':' + secret).encode()).decode()
    def request(url, body=None, headers=None, method=None):
        hdr = {'Accept': 'application/json', **(headers or {})}
        data = None
        if body is not None:
            hdr['Content-Type'] = 'application/json'
            data = body if isinstance(body, bytes) else json.dumps(body,sort_keys=True,separators=(',',':')).encode()
        req = Request(url, data=data, headers=hdr, method=method)
        try:
            response = client.open(req, timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000: raise RuntimeError('Response too large')
            try: value = json.loads(raw)
            except (ValueError, UnicodeDecodeError): value = None
            return response.status, response.headers.get('Content-Type',''), value
    def call(path, body=None, key=None):
        status, content, value = request(local + path, body, {'Idempotency-Key':key} if key else {})
        if status != 200: raise RuntimeError('Battery endpoint rejected request: '+path.split('/')[2]+' HTTP '+str(status))
        return value
    def check(label, condition, **observed):
        report['checks'].append({'name':label, 'passed':bool(condition), **observed})
    native_auth = {'Authorization': basic('BatteryAdapterUser',password)}
    try:
        env = dict(os.environ, BATTERY_IRIS_URL=native+'/api/admin', BATTERY_IRIS_USER='BatteryRestFixtureUser', BATTERY_IRIS_PASSWORD=password, BATTERY_ALLOW_CHANGES='true', BATTERY_RULE_VALIDATION='LIVE_OBSERVED', BATTERY_OPERATOR_NAME='rest-functional-operator', BATTERY_LEDGER_PATH=str(ROOT/'var'/('rest-functional-'+run+'.jsonl')))
        env.pop('BATTERY_OPERATORS_FILE',None)
        env.pop('BATTERY_NATIVE_URL',None)
        log = (ROOT/'var'/('rest-functional-'+run+'.log')).open('w')
        child = subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log)
        for attempt in range(30):
            if child.poll() is not None: raise RuntimeError('Qualification web process exited during startup')
            try:
                if request(local+'/api/health')[0]==200: break
            except (URLError,TimeoutError): pass
            time.sleep(0.5)
        else: raise RuntimeError('Qualification web process was not ready')
        call('/api/session',{'access_key':access})
        if call('/api/state')['mode'] != 'iris': raise RuntimeError('Real IRIS adapter required')
        if any(a.get('Name')==name for a in adapter.list_web_apps()): raise RuntimeError('Fixture name already exists')
        plan=call('/api/intents/web-app/create',{'name':name,'namespace':'BATTERY','dispatch_class':'Battery.Interop.CaseAPI','resource':''})
        if not plan.get('certificate'): raise RuntimeError('Fixture plan was not authorized')
        token=plan['certificate']['token'];key=str(uuid.uuid4())
        created=True  # Cleanup also handles an uncertain dispatch.
        receipt=call('/api/actions/admin/'+token+'/execute',{},key)
        check('battery_creation_receipt',receipt['status']=='VERIFIED_SUCCESS',status=receipt['status'])
        if receipt['status']!='VERIFIED_SUCCESS': raise RuntimeError('Creation was not verified')
        again=call('/api/actions/admin/'+token+'/execute',{},key)
        check('execution_key_reuses_receipt',again['id']==receipt['id'])
        config=adapter.get_web_app(name)
        check('configuration_readback',config.get('NameSpace')=='BATTERY' and config.get('DispatchClass')=='Battery.Interop.CaseAPI' and str(config.get('AutheEnabled'))=='32',namespace=config.get('NameSpace'),dispatch_class=config.get('DispatchClass'),authentication_mask=config.get('AutheEnabled'))
        service=native+name
        status,ct,data=request(service+'/cases')
        check('anonymous_denied',status in {401,403},status=status)
        status,ct,data=request(service+'/cases',headers={'Authorization':basic('BatteryRestFixtureUser','deliberately-wrong')})
        check('wrong_password_denied',status in {401,403},status=status)
        direct_status,_,direct=request(native+'/api/battery/cases',headers=native_auth)
        status,ct,listed=request(service+'/cases',headers=native_auth)
        check('authenticated_list_json',status==200 and 'application/json' in ct and isinstance(listed,dict) and isinstance(listed.get('items'),list),status=status,content_type=ct,diagnostic=listed if status!=200 else None,direct_status=direct_status,direct_diagnostic=direct if direct_status!=200 else None)
        if status!=200 or direct_status!=200: raise RuntimeError('Authenticated service list unavailable')
        check('routed_list_matches_native_api',{x['id'] for x in listed['items']}=={x['id'] for x in direct['items']},items=len(listed['items']))
        contexts=NativeCases(engine_from_environment())._contexts()
        terminal=next((r for r in listed['items'] if r['id'] in contexts and r['state'] not in {'RUNNING','QUEUED','ADMISSION_UNCERTAIN'}),None)
        if terminal is None: raise RuntimeError('A retained terminal case is needed for the service readback check')
        case_id=terminal['id']
        direct_status,_,expected=request(native+'/api/battery/cases/'+case_id,headers=native_auth)
        status,ct,actual=request(service+'/cases/'+case_id,headers=native_auth)
        check('case_detail_matches_native_api',status==direct_status==200 and actual==expected,status=status,state=actual.get('state') if isinstance(actual,dict) else None)
        context=contexts[case_id]
        status,ct,replayed=request(service+'/cases',context['envelope'],{**native_auth,'X-Battery-Operator':context['operator']})
        check('valid_post_replays_existing_case',status==200 and replayed==expected,status=status)
        status,ct,data=request(service+'/cases/'+case_id,headers={'Authorization':basic('BatteryRestFixtureUser',password)})
        check('foreign_native_owner_denied',status==404,status=status)
        status,ct,data=request(service+'/cases/'+case_id,headers={**native_auth,'X-Battery-Operator':'not-the-case-operator'})
        check('foreign_operator_denied',status==404,status=status)
        status,ct,data=request(service+'/cases/missing-'+run,headers=native_auth)
        check('missing_case_404',status==404,status=status)
        status,ct,data=request(service+'/not-a-route',headers=native_auth)
        check('missing_route_404',status==404,status=status)
        status,ct,data=request(service+'/cases',{},native_auth)
        check('invalid_case_400',status==400 and data.get('detail')=='Invalid case',status=status)
        status,ct,data=request(service+'/cases',b'{broken-json',native_auth)
        check('malformed_json_400',status==400,status=status)
        for label,body in [('array',b'[]'),('null',b'null'),('string',b'"not an object"')]:
            status,ct,data=request(service+'/cases',body,native_auth)
            check('json_'+label+'_400',status==400,status=status)
        status,ct,data=request(service+'/cases',headers=native_auth)
        check('rejected_posts_add_no_cases',status==200 and {x['id'] for x in data['items']}=={x['id'] for x in listed['items']})
        check('rejected_posts_spend_no_review_budget',data['budget']==listed['budget'])
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if created:
            try:
                if any(a.get('Name')==name for a in adapter.list_web_apps()): adapter._request('DELETE','/v1/web-app',query={'name':name})
                absent=not any(a.get('Name')==name for a in adapter.list_web_apps())
                check('configuration_removed',absent)
                status,ct,data=request(native+name+'/cases',headers=native_auth)
                check('removed_route_unavailable',status==404,status=status)
            except Exception as exc: report['cleanup_error']=type(exc).__name__+': '+str(exc)
        if child:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        if log:log.close()
        report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'app.py',ROOT/'battery/admin_slice.py',ROOT/'battery/task_slice.py',Path(__file__)]}
        report['passed']=sum(c['passed'] for c in report['checks']);report['total']=len(report['checks'])
        report['ok']=not report.get('error') and not report.get('cleanup_error') and report['total']>=22 and report['passed']==report['total']
        output.write_text(json.dumps(report,indent=2)+'\n')
        print('REST_FUNCTIONAL_RESULT='+json.dumps(report),flush=True)
    if not report['ok']:raise SystemExit(1)
    print('REST_FUNCTIONAL_OK',flush=True)

if __name__=='__main__':main()
