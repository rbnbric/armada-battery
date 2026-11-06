"""Installed native AI Hub full-review check on an existing synthetic case.

It does not submit, replay, or modify a business operation.
"""
import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

base = 'http://127.0.0.1:8080'
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
report = {'scope':'Installed web and native AI Hub; existing synthetic case only; no business operation submitted.', 'checks':[]}

def call(path, body=None):
    request = urllib.request.Request(base+path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    try:
        with client.open(request, timeout=110) as response: return response.status, json.load(response)
    except urllib.error.HTTPError as error: return error.code, json.load(error)

def check(name, passed):
    report['checks'].append({'name':name,'passed':bool(passed)})
    if not passed: raise AssertionError(name)

try:
    status, _ = call('/api/session', {'access_key':os.environ['BATTERY_ACCESS_KEY']})
    check('operator sign-in', status == 200)
    status, listing = call('/api/cases')
    check('retained synthetic case', status == 200 and any(c.get('source_scope')=='synthetic' and c.get('state')=='VERIFIED_MATCH' for c in listing.get('items',[])))
    case = next(c for c in listing['items'] if c.get('source_scope')=='synthetic' and c.get('state')=='VERIFIED_MATCH')
    path = '/api/cases/'+case['id']
    status, before = call(path)
    check('case brief available', status == 200 and bool(before.get('brief',{}).get('revision')))
    _, receipts_before = call('/api/receipts')
    request = {'revision':before['brief']['revision']}
    used_retry = False
    status, answer = call(path+'/full-review', request)
    if answer.get('status') == 'unavailable':
        report['first_attempt'] = answer
        used_retry = True
        status, answer = call(path+'/full-review', {**request, 'retry':True})
    report['answer'] = answer
    check('native full review returned validated content', status == 200 and answer.get('status') == 'ready')
    check('no human choice invented', answer['content']['human_choice_assessment']=='NO_DECISION' and answer['content']['human_reason_assessment']=='NO_DECISION')
    check('sources are cited', bool(answer['content']['evidence_ids']))
    status, repeated = call(path+'/full-review', {**request, 'retry':used_retry})
    check('repeat uses saved answer', status == 200 and repeated == answer)
    status, after = call(path)
    check('case result unchanged', status == 200 and after['result'] == before['result'])
    _, receipts_after = call('/api/receipts')
    check('operation receipts unchanged', receipts_after == receipts_before)
    report['case_id'] = case['id']
    report['passed'] = True
finally:
    Path('/app/var/full-review-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'checks':report['checks'],'passed':report.get('passed',False)}))
