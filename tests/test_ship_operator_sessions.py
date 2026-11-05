from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from battery import ship_operator_sessions as sessions
from test_api import web
from battery.task_slice import engine_from_environment

class SharedOperators(unittest.TestCase):
    def setUp(self):
        factory = patch.object(web, "engine_from_environment", engine_from_environment)
        factory.start(); self.addCleanup(factory.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'operators.json'
        self.keys = {'alice': 'a'*40, 'bob': 'b'*40, 'viewer': 'v'*40}
        self.rows = {n: {'key_sha256': hashlib.sha256(k.encode()).hexdigest(), 'role': 'observer' if n == 'viewer' else 'operator'} for n,k in self.keys.items()}
        self.config.write_text(json.dumps(self.rows))
        self.env = patch.dict(os.environ, {'BATTERY_OPERATORS_FILE': str(self.config), 'BATTERY_OPERATOR_LEDGER_ROOT': str(self.root/'ledgers'), 'BATTERY_SESSION_KEY': 's'*40})
        self.env.start(); self.addCleanup(self.env.stop)
        self.clients = {n: TestClient(web.app) for n in self.keys}
        for n,c in self.clients.items():
            self.assertEqual(c.post('/api/session', json={'access_key':self.keys[n]}).status_code,200)

    def test_independent_identity_and_evidence(self):
        a,b = self.clients['alice'],self.clients['bob']
        plan=a.post('/api/intents/task/17/run',json={'task_definition_reviewed':True}).json()
        response=a.post('/api/actions/task-run/'+plan['certificate']['token']+'/execute',headers={'Idempotency-Key':'shared-test-first'})
        self.assertEqual(response.status_code,200)
        rid=response.json()['id']
        self.assertEqual(a.get('/api/state').json()['operator'],'alice')
        self.assertEqual(b.get('/api/state').json()['operator'],'bob')
        self.assertEqual(b.get('/api/receipts/'+rid).status_code,404)
        self.assertEqual(b.get('/api/receipts').json()['receipts'],[])
        self.assertNotIn(rid,json.dumps(b.get('/api/evidence').json()))
        stolen=b.post('/api/actions/task-run/'+plan['certificate']['token']+'/execute',headers={'Idempotency-Key':'shared-test-stolen'})
        self.assertNotEqual(stolen.status_code,200)
        self.assertNotEqual(sessions.operator_engine('alice', engine_from_environment).ledger.path, sessions.operator_engine('bob', engine_from_environment).ledger.path)

    def test_parallel_requests_keep_their_operator(self):
        from concurrent.futures import ThreadPoolExecutor
        def read(name):
            response=self.clients[name].get('/api/state')
            return name,response.json()['operator']
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(read,['alice','bob']*8))
        self.assertTrue(all(expected==actual for expected,actual in results))

    def test_role_revocation_and_forged_session(self):
        viewer=self.clients['viewer']
        self.assertEqual(viewer.get('/api/catalog').status_code,200)
        self.assertEqual(viewer.post('/api/intents/task/17/run',json={}).status_code,403)
        a=self.clients['alice']
        self.rows['alice']['role']='observer'
        self.config.write_text(json.dumps(self.rows))
        self.assertEqual(a.get('/api/catalog').status_code,401)
        a.cookies.set('battery_session','forged.invalid')
        self.assertEqual(a.get('/api/catalog').status_code,401)
        del self.rows['bob']
        self.config.write_text(json.dumps(self.rows))
        self.assertEqual(self.clients['bob'].get('/api/catalog').status_code,401)

    def test_registry_failure_never_falls_back_to_local(self):
        self.config.write_text('{broken')
        self.assertEqual(self.clients['alice'].get('/api/catalog').status_code,503)
        self.assertEqual(self.clients['alice'].get('/api/health').status_code,503)
        self.assertEqual(self.clients['alice'].post('/api/session',json={'access_key':'a'*40}).status_code,503)

    def test_callback_requires_secret_and_scoped_ledger(self):
        with patch.dict(os.environ, {'BATTERY_ADAPTER_KEY':'k'*40}):
            url='/api/native-evidence/missing?phase=FINAL'
            self.assertEqual(self.clients['alice'].get(url,headers={'X-Battery-Operator':'alice'}).status_code,401)
            headers={'X-Battery-Adapter':'k'*40,'X-Battery-Operator':'../alice'}
            self.assertEqual(self.clients['alice'].get(url,headers=headers).status_code,404)
            headers['X-Battery-Operator']='bob'
            self.assertEqual(self.clients['alice'].get(url,headers=headers).status_code,404)

    def test_logout_clears_cookie_for_read_only_user(self):
        client=self.clients['viewer']
        self.assertEqual(client.post('/api/session/logout').status_code,200)
        self.assertEqual(client.get('/api/catalog').status_code,401)

    def test_duplicate_credentials_rejected_and_missing_signer(self):
        self.rows['bob']['key_sha256']=self.rows['alice']['key_sha256']
        self.config.write_text(json.dumps(self.rows))
        with self.assertRaises(ValueError): sessions.registry()
        with patch.dict(os.environ, {'BATTERY_SESSION_KEY':''}):
            with self.assertRaises(ValueError): sessions.registry()

    def test_malformed_role_fails_closed_with_service_error(self):
        self.rows['alice']['role']=[]
        self.config.write_text(json.dumps(self.rows))
        self.assertEqual(self.clients['alice'].get('/api/catalog').status_code,503)

    def test_context_is_reset_between_requests(self):
        self.assertEqual(self.clients['alice'].get('/api/state').json()['operator'],'alice')
        self.assertIsNone(sessions.identity.get())
        anonymous=TestClient(web.app)
        self.assertEqual(anonymous.get('/api/state').status_code,401)
        self.assertEqual(self.clients['bob'].get('/api/state').json()['operator'],'bob')
