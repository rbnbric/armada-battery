"""Installed service checks. One explicit native explanation; no business action calls."""
import hashlib
import base64
import json
import os
import urllib.request
import urllib.error
import http.cookiejar
from pathlib import Path

report={'checks':[], 'scope':'Installed service, existing synthetic case, one optional native explanation. No business operation submitted.'}
jar=http.cookiejar.CookieJar()
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
base='http://127.0.0.1:8080'
def request(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'})
    try:
        with client.open(req,timeout=110) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def check(name,value):
    report['checks'].append({'name':name,'passed':bool(value)})
    if not value:raise AssertionError(name)
try:
    status,_=request('/api/session',{'access_key':os.environ['BATTERY_ACCESS_KEY']});check('operator sign-in',status==200)
    status,listing=request('/api/cases');check('case list',status==200 and listing['items'])
    selected=next(c for c in listing['items'] if c['state']=='VERIFIED_MATCH' and c.get('source_scope')=='synthetic')
    case_id=selected['id'];path='/api/cases/'+case_id
    status,before=request(path);check('structured decision brief',status==200 and before['brief']['kind']=='COMPLETE')
    check('no gratuitous approval',before['brief']['choices']==[])
    check('synthetic scope preserved',before['brief']['scope']=='synthetic')
    _,receipts_before=request('/api/receipts')
    status,explanation=request(path+'/explain',{'revision':before['brief']['revision']})
    if explanation.get('status')=='unavailable':
        report['prior_explanation']=explanation
        status,explanation=request(path+'/explain',{'revision':before['brief']['revision'],'retry':True})
    report['explanation']=explanation
    check('real native explainer returned validated content',status==200 and explanation.get('status')=='ready')
    text=json.dumps(explanation['content']).lower()
    check('native explanation identifies simulation','simulat' in text or 'synthetic' in text)
    status,repeated=request(path+'/explain',{'revision':before['brief']['revision']})
    check('explicit repeat returns retained explanation',status==200 and repeated==explanation)
    status,_=request(path+'/decision',{'revision':'0'*64,'choice':'defer','reason':'Qualification stale revision'})
    check('stale decision rejected',status==409)
    status,_=request(path+'/decision',{'revision':before['brief']['revision'],'choice':'execute','reason':'Qualification invalid action'})
    check('invented action rejected',status==409)
    status,_=request('/api/cases/nonexistent/explain',{'revision':'0'*64})
    check('unowned missing case hidden',status==404)
    status,after=request(path);check('case result unchanged',status==200 and after['result']==before['result'])
    _,receipts_after=request('/api/receipts');check('operation receipts unchanged',receipts_after==receipts_before)
    report['case']=after
    # Private endpoint rejects malformed inputs and foreign operator before model admission.
    auth=base64.b64encode((os.environ['BATTERY_NATIVE_USER']+':'+os.environ['BATTERY_NATIVE_PASSWORD']).encode()).decode()
    native=os.environ['BATTERY_NATIVE_URL']+'/cases/'+case_id+'/explain'
    for label,payload,operator,expected in [('malformed JSON',b'{',before['brief']['owner'],400),('scalar JSON',b'false',before['brief']['owner'],400),('foreign operator',json.dumps({'revision':before['brief']['revision'],'brief':{'case_id':case_id,'revision':before['brief']['revision']}}).encode(),'unrelated-operator',404)]:
        req=urllib.request.Request(native,data=payload,headers={'Authorization':'Basic '+auth,'Content-Type':'application/json','X-Battery-Operator':operator})
        try:
            with urllib.request.urlopen(req,timeout=10) as r:code=r.status
        except urllib.error.HTTPError as e:code=e.code
        check('native '+label,code==expected)
    report['installed_source_sha256']={name:hashlib.sha256(Path('/app',name).read_bytes()).hexdigest() for name in ['app.py','battery/ship_native_cases.py','battery/ship_decision_brief.py','static/app.js','static/app.css']}
    report['passed']=True
finally:
    Path('/app/var/decision-brief-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'checks':report['checks'],'passed':report.get('passed',False)}))
