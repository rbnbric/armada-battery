"""Real engine/ledger and loopback HTTP contract tests; native/model tests are separate."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from battery.ledger import Ledger
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter
from battery.ship_native_cases import NativeCases
from battery.ship_decision_brief import validate_explanation, explanation_input, full_case_review_input, validate_full_case_review, claim_review_packet, claim_review_with_frontload, validate_claim_review, validate_reasoning_frontload

class Peer:
    # seam: native network boundary. Protocol fixtures, not a native AI claim.
    def __init__(self):
        self.cases, self.posts = {}, []
        self.answer = {"summary": "This is a simulated operation.", "meaning": "The recorded review matched its criterion.", "missing": "Downstream effects have not been established.", "evidence_ids": ["review", "scope"]}
        self.explanation_reads = 0
        self.full_review_reads = 0
        self.full_answer = {"what_happened":"The saved operation completed.", "where_judgment_changed":"No change in judgment is recorded.", "human_path":"No human decision is recorded.", "unresolved":"Downstream effects remain untested.", "human_choice_assessment":"NO_DECISION", "human_reason_assessment":"NO_DECISION", "evidence_ids":["receipt","review"]}
        self.on_explain = None
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def reply(self, value):
                raw=json.dumps(value).encode(); self.send_response(200); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self): self.reply(owner.cases[self.path.rsplit('/',1)[-1]])
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.posts.append(body)
                if self.path.endswith('/full-review'):
                    owner.full_review_reads += 1
                    self.reply({'content':json.dumps(owner.full_answer),'usage':'{}','response_id':'fixture-full'})
                elif self.path.endswith('/explain'):
                    owner.explanation_reads += 1
                    if owner.on_explain: owner.on_explain()
                    self.reply({'content':json.dumps(owner.answer),'usage':'{}','response_id':'fixture'})
                else:
                    case={'id':body['case']['id'],'state':'VERIFIED_MATCH','updated_at':'2026-11-05 02:04:00','result':{'assertion':'YES','output':'PASS','reason_code':'COMPLETE','explanation':'Fresh scoped receipt measurement'}}
                    owner.cases.setdefault(case['id'],case);self.reply(owner.cases[case['id']])
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
    def close(self): self.server.shutdown();self.server.server_close()

class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.jsonl'
        self.adapter=SyntheticTaskAdapter()
        self.engine=BatteryEngine(self.adapter,ledger=Ledger(self.path))
        plan=self.engine.prepare_task_run(17,requested_by='owner',task_definition_reviewed=True)
        self.receipt=self.engine.execute_task_run(plan['certificate']['token'],'one-effect',operator='owner')
        self.peer=Peer();self.addCleanup(self.peer.close)
        self.bridge=NativeCases(self.engine,self.peer.url,'adapter','private',operator='owner')
        self.id=self.bridge.submit(self.receipt['id'],'native-review-00001','owner')['id']
    def detail(self): return self.bridge.get(self.id,'owner')
    def change(self): self.adapter.tasks[17]['Name']='Intentionally changed elsewhere'
    def test_completed_case_needs_no_human_approval(self):
        b=self.detail()['brief'];self.assertEqual(b['kind'],'COMPLETE');self.assertEqual(b['choices'],[])
        self.assertEqual(b['scope'],'synthetic');self.assertIn('works in use',b['unknowns'][0])
    def test_current_change_preserves_historical_success(self):
        self.change();c=self.detail();b=c['brief'];self.assertEqual(c['state'],'VERIFIED_MATCH');self.assertEqual(b['kind'],'CONTEXT_DECISION')
        self.assertEqual(b['differences'][0]['field'],'Name');self.assertIn('intentional',b['question']);self.assertIn('not established',b['unknowns'][1])
    def test_rule_and_output_pairs_remain_independent(self):
        for assertion,output in [('YES','PASS'),('YES','FAIL'),('NO','PASS'),('NO','FAIL')]:
            c=self.peer.cases[self.id];c['state']='VERIFIED_MATCH' if (assertion,output)==('YES','PASS') else 'VERIFIED_MISMATCH';c['result'].update(assertion=assertion,output=output)
            f=self.detail()['brief']['facts'][0]['value'];self.assertEqual((f['assertion'],f['output']),(assertion,output))
    def test_technical_recovery_is_not_business_intent(self):
        self.peer.cases[self.id].update(state='RECOVERY_REQUIRED',recovery_reason='Lease expired')
        b=self.detail()['brief'];self.assertEqual(b['kind'],'TECHNICAL_RECOVERY');self.assertNotIn('keep_current',[x['id'] for x in b['choices']])
    def test_missing_target_is_unknown_not_unchanged(self):
        del self.adapter.tasks[17]
        b=self.detail()['brief'];self.assertEqual(b['kind'],'EVIDENCE_NEEDED');self.assertIsNone(b['facts'][2]['value']['changed'])
    def test_stale_answer_rejected(self):
        self.change();b=self.detail()['brief'];self.adapter.tasks[17]['Name']='Another change'
        with self.assertRaisesRegex(ValueError,'Evidence changed'):self.bridge.decide(self.id,'owner',b['revision'],'keep_current','Approved by owner')
        self.assertFalse(any(r['event_type']=='native_human_decision' for r in self.engine.ledger.records))
    def test_durable_scoped_decision_does_not_execute(self):
        self.change();b=self.detail()['brief'];d=self.bridge.decide(self.id,'owner',b['revision'],'keep_current','Current configuration is intended')
        new=NativeCases(BatteryEngine(self.adapter,ledger=Ledger(self.path)),self.peer.url,'adapter','private',operator='owner')
        self.assertEqual(new.get(self.id,'owner')['decisions'][0]['decision_id'],d['decision_id']);self.assertEqual(self.adapter.run_calls,1)
        with self.assertRaises(KeyError):new.get(self.id,'other')
        with self.assertRaises(KeyError):new.decide(self.id,'other',b['revision'],'keep_current','borrowed')
    def test_concurrent_duplicate_answer_records_once(self):
        self.change();b=self.detail()['brief']
        def answer(_):return self.bridge.decide(self.id,'owner',b['revision'],'defer','Ask the operator who changed it')
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(answer,range(2)))
        self.assertEqual(out[0],out[1]);self.assertEqual(len(self.detail()['decisions']),1)
    def test_new_review_never_repeats_effect(self):
        self.change();b=self.detail()['brief'];d=self.bridge.decide(self.id,'owner',b['revision'],'request_evidence','Check current target')
        first=self.bridge.follow_decision(d,'owner');second=self.bridge.follow_decision(d,'owner')
        self.assertEqual(first['child_id'],second['child_id']);self.assertEqual(self.adapter.run_calls,1)
        self.assertEqual(self.detail()['brief']['kind'],'SUPERSEDED');self.assertEqual(self.detail()['brief']['choices'],[])
    def test_server_owned_choices_require_reason(self):
        self.change();b=self.detail()['brief']
        for choice,reason in [('execute','yes'),('defer',''),('defer','x'*2001)]:
            with self.assertRaises(ValueError):self.bridge.decide(self.id,'owner',b['revision'],choice,reason)
    def test_explanation_cached_without_changing_outcome(self):
        b=self.detail()['brief'];one=self.bridge.explain(self.id,'owner',b['revision']);two=self.bridge.explain(self.id,'owner',b['revision'])
        self.assertEqual(one,two);self.assertEqual(self.peer.explanation_reads,1);self.assertEqual(self.detail()['state'],'VERIFIED_MATCH');self.assertEqual(self.adapter.run_calls,1)
    def test_late_explanation_not_attached_to_new_revision(self):
        b=self.detail()['brief'];self.peer.on_explain=self.change
        with self.assertRaisesRegex(ValueError,'Evidence changed'):self.bridge.explain(self.id,'owner',b['revision'])
        self.assertNotIn('explanation',self.detail())
    def test_invalid_citation_falls_back(self):
        b=self.detail()['brief'];self.peer.answer['evidence_ids']=['invented']
        self.assertEqual(self.bridge.explain(self.id,'owner',b['revision'])['status'],'unavailable');self.assertEqual(self.detail()['brief']['summary'],b['summary'])
    def test_explanation_cannot_add_actions_or_verdict(self):
        b=self.detail()['brief']
        for field in ['actions','verdict','command']:
            with self.assertRaises(ValueError):validate_explanation({**self.peer.answer,field:'execute'},b)
        with self.assertRaises(ValueError):validate_explanation({**self.peer.answer,'evidence_ids':[{}]},b)
    def test_packet_excludes_transcripts_and_labels_coverage(self):
        self.peer.cases[self.id]['result']['ReviewHistoryJSON']=[{'content':'untrusted secret transcript'}]
        packet=explanation_input(self.detail()['brief']);self.assertNotIn('untrusted secret transcript',json.dumps(packet));self.assertIn('not included',packet['coverage'])
    def test_secrets_not_exposed_in_difference(self):
        self.adapter.tasks[17]['password']='never-show-me';self.assertNotIn('never-show-me',json.dumps(self.detail()['brief']))
    def test_corrupt_ledger_rejects_decision(self):
        self.change();b=self.detail()['brief'];self.path.write_text(self.path.read_text().replace('native_case_admitted','tampered'))
        with self.assertRaisesRegex(ValueError,'integrity'):self.bridge.decide(self.id,'owner',b['revision'],'defer','context')
    def test_unknown_legacy_hold_not_claimed_as_human_judgment(self):
        c=self.peer.cases[self.id];c['state']='HELD_FOR_REVIEW';c['result'].pop('reason_code');self.assertEqual(self.detail()['brief']['kind'],'REVIEW_REQUIRED')

    def test_explicit_explanation_retry_is_bounded_and_audited(self):
        b=self.detail()['brief'];self.peer.answer['evidence_ids']=['invented']
        first=self.bridge.explain(self.id,'owner',b['revision'])
        self.assertEqual(first['status'],'unavailable');self.assertEqual(self.peer.explanation_reads,1)
        self.assertEqual(self.bridge.explain(self.id,'owner',b['revision']),first)
        self.peer.answer['evidence_ids']=['review']
        second=self.bridge.explain(self.id,'owner',b['revision'],retry=True)
        self.assertEqual(second['status'],'ready');self.assertEqual(second['attempt'],2)
        self.assertEqual(self.bridge.explain(self.id,'owner',b['revision'],retry=True),second)
        self.assertEqual(self.peer.explanation_reads,2)
    def test_interrupted_explanation_never_automatically_replays(self):
        b=self.detail()['brief']
        self.engine.ledger.append('native_explanation_started',{'case_id':self.id,'operator':'owner','revision':b['revision'],'attempt':1})
        self.assertEqual(self.bridge.explain(self.id,'owner',b['revision'],retry=True)['status'],'unconfirmed')
        self.assertEqual(self.peer.explanation_reads,0)
    def test_full_review_is_bounded_cached_and_does_not_repeat_operation(self):
        c=self.detail();packet=full_case_review_input(c,self.receipt)
        self.assertLessEqual(len(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()),6144)
        one=self.bridge.full_review(self.id,'owner',c['brief']['revision'])
        self.assertEqual(one['status'],'ready');self.assertEqual(one,self.bridge.full_review(self.id,'owner',c['brief']['revision']))
        self.assertEqual(self.peer.full_review_reads,1);self.assertEqual(self.adapter.run_calls,1)
        self.assertEqual(self.detail()['full_review']['content']['what_happened'],self.peer.full_answer['what_happened'])
    def test_claim_review_keeps_exact_reason_and_rejects_invented_words(self):
        self.change();brief=self.detail()['brief']
        self.bridge.decide(self.id,'owner',brief['revision'],'defer','The manager approved it by phone.')
        packet=claim_review_packet(full_case_review_input(self.detail(),self.receipt))
        self.assertEqual(packet['human_record']['reason_exact'],'The manager approved it by phone.')
        self.assertEqual(packet['human_record']['selected_choice'],'defer')
        answer={'human_event_id':packet['human_record']['event_id'],'selected_choice':'defer',
                'choice_assessment':'SUPPORTED','reason_assessment':'UNCERTAIN',
                'claims':[{'quote':'The manager approved it by phone.','kind':'approval','assessment':'UNVERIFIED','evidence_ids':['review']}]}
        self.assertEqual(validate_claim_review(answer,packet),answer)
        with self.assertRaisesRegex(ValueError,'invented human words'):
            validate_claim_review({**answer,'claims':[{**answer['claims'][0],'quote':'The manager certainly approved it.'}]},packet)
        with self.assertRaisesRegex(ValueError,'changed the selected choice'):
            validate_claim_review({**answer,'selected_choice':'keep_current'},packet)
        with self.assertRaisesRegex(ValueError,'unsupported evidence'):
            validate_claim_review({**answer,'claims':[{**answer['claims'][0],'evidence_ids':['other-case']}]},packet)
        scan={'human_event_id':packet['human_record']['event_id'],'issues':[]}
        self.assertEqual(validate_reasoning_frontload(scan,packet),scan)
        staged=claim_review_with_frontload(packet,scan)
        self.assertEqual(staged['facts'],packet['facts'])
        self.assertEqual(staged['human_record'],packet['human_record'])
        self.assertEqual(staged['reasoning_hypotheses'],[])
        with self.assertRaisesRegex(ValueError,'invented human words'):
            validate_reasoning_frontload({**scan,'issues':[{'quote':'The boss overrode the check','pattern':'authority_override','missing_link':'No override is recorded.'}]},packet)
        with self.assertRaisesRegex(ValueError,'unknown pattern'):
            validate_reasoning_frontload({**scan,'issues':[{'quote':'The manager approved it by phone.','pattern':'any_authority_mention','missing_link':'No override is recorded.'}]},packet)
        with self.assertRaisesRegex(ValueError,'without an override'):
            validate_reasoning_frontload({**scan,'issues':[{'quote':'The manager approved it by phone.','pattern':'authority_override','missing_link':'No override is stated.'}]},packet)
        with self.assertRaisesRegex(ValueError,'without words grounded'):
            validate_claim_review({**answer,'reason_assessment':'SUPPORTED',
                                   'claims':[{**answer['claims'][0],'assessment':'SUPPORTED','quote':'The manager approved it by phone.'}]},packet)
    def test_full_review_rejects_bad_citation_and_stale_revision(self):
        c=self.detail();packet=full_case_review_input(c,self.receipt)
        with self.assertRaises(ValueError):validate_full_case_review({**self.peer.full_answer,'evidence_ids':[{}]},packet)
        with self.assertRaises(ValueError):validate_full_case_review({**self.peer.full_answer,'human_choice_assessment':'SUPPORTED'},packet)
        packet['sources'].append({'id':'human','value':{'responses':[{'choice':'defer','reason':'Need owner context'}]}})
        with self.assertRaises(ValueError):validate_full_case_review({**self.peer.full_answer,'human_choice_assessment':'SUPPORTED','human_reason_assessment':'SUPPORTED','evidence_ids':['receipt']},packet)
        self.peer.full_answer['evidence_ids']=['invented']
        self.assertEqual(self.bridge.full_review(self.id,'owner',c['brief']['revision'])['status'],'unavailable')
        self.change()
        with self.assertRaisesRegex(ValueError,'Evidence changed'):self.bridge.full_review(self.id,'owner',c['brief']['revision'])
    def test_full_review_excludes_raw_transcripts(self):
        self.peer.cases[self.id]['result']['ReviewHistoryJSON']=[{'content':'private raw transcript','verdict':'YES'}]
        packet=full_case_review_input(self.detail(),self.receipt)
        self.assertNotIn('private raw transcript',json.dumps(packet))
    def test_new_human_decision_invalidates_old_full_review(self):
        self.change();c=self.detail();revision=c['brief']['revision']
        self.assertEqual(self.bridge.full_review(self.id,'owner',revision)['status'],'ready')
        self.assertEqual(self.peer.full_review_reads,1)
        self.bridge.decide(self.id,'owner',revision,'defer','Ask the responsible owner about the changed setting')
        self.assertNotIn('full_review',self.detail())
        self.peer.full_answer.update(human_choice_assessment='SUPPORTED',human_reason_assessment='SUPPORTED',evidence_ids=['human','configuration'])
        self.assertEqual(self.bridge.full_review(self.id,'owner',revision)['status'],'ready')
        self.assertEqual(self.peer.full_review_reads,2)

class DecisionHttpTests(unittest.TestCase):
    def setUp(self):
        import os
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from test_api import web
        self.web=web;self.peer=Peer();self.addCleanup(self.peer.close)
        self.env=patch.dict(os.environ,{'BATTERY_NATIVE_URL':self.peer.url,'BATTERY_NATIVE_USER':'adapter','BATTERY_NATIVE_PASSWORD':'test-only','BATTERY_ACCESS_KEY':'k'*40})
        self.env.start();self.addCleanup(self.env.stop)
        self.engine=BatteryEngine(SyntheticTaskAdapter(),ledger=Ledger());web.engine=self.engine
        self.client=TestClient(web.app)
        self.assertEqual(self.client.post('/api/session',json={'access_key':'k'*40}).status_code,200)
        p=self.client.post('/api/intents/task/17/run',json={'task_definition_reviewed':True}).json()
        r=self.client.post('/api/actions/task-run/'+p['certificate']['token']+'/execute',headers={'Idempotency-Key':'decision-fixture-operation'}).json()
        c=self.client.post('/api/cases',json={'receipt_id':r['id']},headers={'Idempotency-Key':'decision-fixture-review'}).json()
        self.url='/api/cases/'+c['id']
    def test_http_decision_persists_and_double_submit_does_not_execute(self):
        self.engine.adapter.tasks[17]['Name']='Later intent'
        c=self.client.get(self.url).json()
        body={'revision':c['brief']['revision'],'choice':'keep_current','reason':'Owner requested this configuration'}
        first=self.client.post(self.url+'/decision',json=body);self.assertEqual(first.status_code,200,first.text)
        second=self.client.post(self.url+'/decision',json=body);self.assertEqual(first.json(),second.json())
        self.assertEqual(len(self.client.get(self.url).json()['decisions']),1);self.assertEqual(self.engine.adapter.run_calls,1)
    def test_http_rejects_stale_foreign_origin_and_invented_actions(self):
        self.engine.adapter.tasks[17]['Name']='Later intent';c=self.client.get(self.url).json()
        body={'revision':c['brief']['revision'],'choice':'defer','reason':'Need context'}
        self.assertEqual(self.client.post(self.url+'/decision',json=body,headers={'Origin':'https://unrelated.invalid'}).status_code,403)
        self.engine.adapter.tasks[17]['Name']='Changed again'
        self.assertEqual(self.client.post(self.url+'/decision',json=body).status_code,409)
        self.assertEqual(self.client.post(self.url+'/decision',json={**body,'choice':'execute'}).status_code,409)
    def test_http_explanation_and_session_expiry(self):
        c=self.client.get(self.url).json();body={'revision':c['brief']['revision']}
        r=self.client.post(self.url+'/explain',json=body);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'ready')
        self.client.post('/api/session/logout')
        self.assertEqual(self.client.post(self.url+'/explain',json=body).status_code,401)
        self.assertEqual(self.client.post(self.url+'/decision',json={'revision':body['revision'],'choice':'defer','reason':'no session'}).status_code,401)
    def test_http_full_review_is_explicit_and_scoped(self):
        c=self.client.get(self.url).json();body={'revision':c['brief']['revision']}
        self.assertEqual(self.peer.full_review_reads,0)
        r=self.client.post(self.url+'/full-review',json=body);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['status'],'ready');self.assertEqual(self.peer.full_review_reads,1)
        self.assertEqual(self.client.post(self.url+'/full-review',json=body).json(),r.json())
        self.assertEqual(self.peer.full_review_reads,1);self.assertEqual(self.engine.adapter.run_calls,1)
    def test_http_follow_up_review_retains_parent_without_new_operation(self):
        self.engine.adapter.tasks[17]['Name']='Later intent';c=self.client.get(self.url).json()
        body={'revision':c['brief']['revision'],'choice':'request_evidence','reason':'Read the changed target'}
        r=self.client.post(self.url+'/decision',json=body);self.assertEqual(r.status_code,200,r.text)
        self.assertNotEqual(r.json()['child_id'],c['id']);self.assertEqual(self.peer.posts[-1]['parent_id'],c['id'])
        again=self.client.post(self.url+'/decision',json=body);self.assertEqual(again.json()['child_id'],r.json()['child_id'])
        self.assertEqual(self.engine.adapter.run_calls,1)
