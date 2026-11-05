"""Run inside battery-web after configure.script; creates one synthetic task attempt.

Real HTTP, native queues and AI Hub model calls; synthetic business target.
Write the complete receipt to a local evidence file, without credentials.
"""
from __future__ import annotations
import json
import os
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import build_opener, HTTPCookieProcessor, Request
from http.cookiejar import CookieJar


def main():
    client = build_opener(HTTPCookieProcessor(CookieJar()))
    def call(path, body=None, key=None):
        headers = {"Content-Type": "application/json"}
        if key: headers["Idempotency-Key"] = key
        request = Request("http://127.0.0.1:8080" + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        with client.open(request, timeout=12) as response:
            return json.load(response)
    ready_deadline = time.monotonic() + 30
    while True:
        try:
            call('/api/health')
            break
        except (URLError, TimeoutError):
            if time.monotonic() >= ready_deadline: raise
            time.sleep(1)
    call('/api/session', {'access_key': os.environ['BATTERY_ACCESS_KEY']})
    state = call('/api/state')
    assert state['mode'] == 'synthetic', 'This qualification requires the disposable synthetic management adapter'
    plan = call('/api/intents/task/17/run', {'task_definition_reviewed': True})
    token = plan['certificate']['token']
    key = str(uuid.uuid4())
    receipt = call('/api/actions/task-run/' + token + '/execute', {}, key)
    assert receipt['status'] == 'VERIFIED_SUCCESS'
    repeated = call('/api/actions/task-run/' + token + '/execute', {}, key)
    assert repeated['id'] == receipt['id']
    case_key = str(uuid.uuid4())
    admitted = call('/api/cases', {'receipt_id': receipt['id']}, case_key)
    duplicate = call('/api/cases', {'receipt_id': receipt['id']}, case_key)
    assert admitted['id'] == duplicate['id']
    started = time.monotonic()
    transitions = []
    while time.monotonic() - started < 420:
        result = call('/api/cases/' + admitted['id'])
        if not transitions or transitions[-1] != result['state']:
            transitions.append(result['state'])
        if result['state'] not in {'QUEUED', 'RUNNING'}: break
        time.sleep(2)
    report = {'scope': 'real native AI Hub review of a synthetic management operation', 'receipt': receipt, 'case': result, 'state_transitions': transitions, 'elapsed_seconds': round(time.monotonic() - started, 3), 'duplicate_operation_receipt_equal': repeated['id'] == receipt['id'], 'duplicate_case_id_equal': admitted['id'] == duplicate['id']}
    path = Path('/app/var/native-integration-result.json')
    path.write_text(json.dumps(report, indent=2) + '\n')
    print('NATIVE_INTEGRATION_RESULT=' + json.dumps(report), flush=True)
    assert result['state'] == 'VERIFIED_MATCH', result
    assert result['result']['assertion'] == 'YES' and result['result']['output'] == 'PASS'
    assert result['result']['executed_probe'] in {'CHECK_EFFECT_RECEIPT', 'CHECK_TARGET_VERSION', 'CHECK_FRESH_READBACK'}
    assert result['result']['response_id']
    reads = result['result']['ProbeHistoryJSON']
    assert len(reads) >= 2 and any(row.get('tool') for row in reads)
    print('NATIVE_INTEGRATION_OK', flush=True)


if __name__ == '__main__':
    main()
