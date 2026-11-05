"""Disposable IRIS configuration operation -> uncertain delivery -> native AI Hub review."""
import http.client
import json
import os
import time
import uuid
import sys
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import URLError, HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from battery.task_slice import IrisTaskAdapter
from battery.ledger import sanitize

jar = CookieJar()
client = build_opener(HTTPCookieProcessor(jar))
def call(path, body=None, key=None):
    headers = {'Content-Type': 'application/json'}
    if key: headers['Idempotency-Key'] = key
    with client.open(Request('http://127.0.0.1:8080' + path, data=None if body is None else json.dumps(body).encode(), headers=headers), timeout=20) as response:
        return json.load(response)

report = {'scope': 'real IRIS REST application configuration and native AI Hub review', 'checks': {}}
name = '/battery-qualification-' + uuid.uuid4().hex[:12]
adapter = IrisTaskAdapter.from_environment()
try:
    deadline = time.monotonic() + 30
    while True:
        try: call('/api/health'); break
        except (URLError, TimeoutError):
            if time.monotonic() >= deadline: raise
            time.sleep(1)
    call('/api/session', {'access_key': os.environ['BATTERY_ACCESS_KEY']})
    assert call('/api/state')['mode'] == 'iris'
    try:
        adapter.list_web_apps()
    except Exception:
        request = Request(adapter.base_url + '/v1/web-app/', headers={'Authorization': adapter.authorization})
        try:
            client.open(request, timeout=15).close()
        except HTTPError as exc:
            report['upstream_diagnostic'] = sanitize(exc.read(8192).decode('utf-8', errors='replace'))
        raise
    plan = call('/api/intents/web-app/create', {'name': name, 'namespace': 'BATTERY', 'dispatch_class': 'Battery.Interop.CaseAPI', 'resource': ''})
    assert plan['certificate'], plan
    token, key = plan['certificate']['token'], str(uuid.uuid4())
    # Send once and close before reading the response. Reconcile by the same key.
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=10)
    connection.request('POST', '/api/actions/admin/' + token + '/execute', body='{}', headers={'Content-Type': 'application/json', 'Idempotency-Key': key, 'Cookie': '; '.join(c.name + '=' + c.value for c in jar)})
    connection.close()
    receipt = None
    for _ in range(20):
        rows = call('/api/receipts?execution_key=' + key)['receipts']
        if rows and rows[0]['status'] == 'VERIFIED_SUCCESS': receipt = rows[0]; break
        time.sleep(1)
    report["observed_receipts"] = rows
    assert receipt, rows
    report['receipt'] = receipt
    report['checks']['lost_response_recovered'] = True
    repeated = call('/api/actions/admin/' + token + '/execute', {}, key)
    assert repeated['id'] == receipt['id']
    report['checks']['execution_key_reused_receipt'] = True
    assert len([a for a in adapter.list_web_apps() if a.get('Name') == name]) == 1
    report['checks']['one_named_configuration'] = True
    case_key = str(uuid.uuid4())
    admitted = call('/api/cases', {'receipt_id': receipt['id']}, case_key)
    assert call('/api/cases', {'receipt_id': receipt['id']}, case_key)['id'] == admitted['id']
    started = time.monotonic()
    while time.monotonic() - started < 420:
        case = call('/api/cases/' + admitted['id'])
        if case['state'] not in {'QUEUED', 'RUNNING'}: break
        time.sleep(2)
    report['case'] = case
    report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    assert case['state'] == 'VERIFIED_MATCH', case
    assert case['source_scope'] == 'iris'
    report['checks']['native_review_completed'] = True
except Exception as exc:
    report["error"] = type(exc).__name__ + ": " + str(exc)
    raise
finally:
    try:
        if any(a.get('Name') == name for a in adapter.list_web_apps()):
            adapter._request('DELETE', '/v1/web-app', query={'name': name})
        report['checks']['fixture_removed'] = not any(a.get('Name') == name for a in adapter.list_web_apps())
    except Exception as cleanup_error:
        report['cleanup_error'] = str(cleanup_error)
    Path('/app/var/native-live-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('NATIVE_LIVE_RESULT=' + json.dumps(report), flush=True)
assert report['checks'].get('fixture_removed'), report
print('NATIVE_LIVE_OK', flush=True)
