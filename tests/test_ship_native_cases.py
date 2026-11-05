import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from battery.ledger import Ledger
from battery.task_slice import BatteryEngine, SyntheticTaskAdapter
from battery.ship_native_cases import NativeCases, digest


class NativeCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.jsonl'
        self.adapter = SyntheticTaskAdapter()
        self.engine = BatteryEngine(self.adapter, ledger=Ledger(self.path))
        plan = self.engine.prepare_task_run(17, requested_by='operator', task_definition_reviewed=True)
        self.receipt = self.engine.execute_task_run(plan['certificate']['token'], 'effect-once', operator='operator')
        self.bridge = NativeCases(self.engine, 'http://native/api/battery', 'adapter', 'private')
        self.bridge.request = Mock(side_effect=lambda path, body=None: {'id': body['case']['id'], 'state': 'QUEUED'} if body else {'items': []})

    def submit(self, **kwargs):
        return self.bridge.submit(self.receipt['id'], 'native-request-00001', 'operator', **kwargs)

    def test_retry_preserves_exact_envelope_and_survives_engine_restart(self):
        first = self.submit()
        envelope = self.bridge.request.call_args.args[1]
        self.adapter.tasks[17]['Name'] = 'Changed while admission was uncertain'
        restart = NativeCases(BatteryEngine(self.adapter, ledger=Ledger(self.path)), 'http://native/api/battery', 'adapter', 'private')
        restart.request = self.bridge.request
        self.assertEqual(restart.submit(self.receipt['id'], 'native-request-00001', 'operator'), first)
        self.assertEqual(restart.request.call_args.args[1], envelope)
        self.assertEqual(self.adapter.run_calls, 1)

    def test_version_tool_detects_change_that_receipt_lookup_cannot_see(self):
        case = self.submit()['id']
        first = self.bridge.evidence(case, 'CHECK_EFFECT_RECEIPT')
        self.adapter.tasks[17]['Name'] = 'Changed'
        version = self.bridge.evidence(case, 'CHECK_TARGET_VERSION')
        self.assertEqual(first['observation']['version'], first['contract']['version'])
        self.assertNotEqual(version['observation']['version'], version['contract']['version'])
        self.assertNotEqual(first['tool']['source'], version['tool']['source'])
        self.assertEqual(version['tool']['source_scope'], 'synthetic')

    def test_initial_contract_uses_receipt_snapshot_not_later_target(self):
        original = dict(self.adapter.tasks[17])
        self.adapter.tasks[17]['Name'] = 'Changed before submission'
        case = self.submit()['id']
        final = self.bridge.evidence(case, 'FINAL')
        self.assertEqual(final['contract']['version'], digest(original))
        self.assertNotEqual(final['observation']['version'], final['contract']['version'])

    def test_operator_scope_unknown_tools_and_key_conflicts(self):
        case = self.submit()['id']
        with self.assertRaises(KeyError): self.bridge.get(case, 'stranger')
        with self.assertRaises(ValueError): self.bridge.evidence(case, 'EXECUTE_SHELL')
        with self.assertRaises(ValueError): self.bridge.submit('different', 'native-request-00001', 'operator')
        with self.assertRaises(KeyError): self.bridge.submit(self.receipt['id'], 'native-other-00001', 'stranger')
        with self.assertRaises(ValueError): self.bridge.submit(self.receipt['id'], 'x', 'operator')

    def test_unknown_receipt_stays_unknown_and_retains_original_source_time(self):
        case = self.submit()['id']
        known = self.bridge.evidence(case, 'FINAL')
        self.assertEqual(known['observation']['result'], 'COMPLETE')
        self.assertEqual(known['observation']['observed_at'], self.bridge.evidence(case, 'FINAL')['observation']['observed_at'])
        from battery.models import ReceiptStatus, to_data
        receipt = self.engine.receipts[self.receipt['id']]
        receipt.status = ReceiptStatus.OUTCOME_UNKNOWN
        self.engine.ledger.append('action_reconciled', to_data(receipt))
        self.assertEqual(self.bridge.evidence(case, 'FINAL')['observation'], {'available': False})

    def test_resume_retains_parent_and_cannot_borrow_another_receipt(self):
        parent = self.submit()['id']
        result = self.bridge.submit(self.receipt['id'], 'native-revision-0002', 'operator', parent)
        self.assertNotEqual(result['id'], parent)
        self.assertEqual(self.bridge.request.call_args.args[1]['parent_id'], parent)
        with self.assertRaises(ValueError): self.bridge.submit('other', 'native-revision-0003', 'operator', parent)

    def test_failed_native_admission_stays_durable_without_resending_effect(self):
        self.bridge.request = Mock(side_effect=TimeoutError('simulated response loss'))
        with self.assertRaises(TimeoutError): self.submit()
        self.assertEqual(len(self.bridge._contexts()), 1)
        self.assertEqual(self.adapter.run_calls, 1)

    def test_corrupt_ledger_cannot_supply_evidence(self):
        case = self.submit()['id']
        text = self.path.read_text().replace('native_case_admitted', 'native_case_fabricated')
        self.path.write_text(text)
        with self.assertRaises(ValueError): self.bridge.evidence(case, 'FINAL')


    def test_native_wire_bytes_do_not_depend_on_json_key_order(self):
        from unittest.mock import patch
        from contextlib import nullcontext
        import io
        import json
        bridge = NativeCases(self.engine, 'http://native/api/battery', 'adapter', 'private')
        captured = []
        def open_request(request, timeout):
            captured.append(request.data)
            return nullcontext(io.BytesIO(b'{"state":"QUEUED"}'))
        original = {'case': {'rule': 'rule', 'id': 'id'}, 'parent_id': ''}
        restored = json.loads(json.dumps(original, sort_keys=True))
        with patch('urllib.request.urlopen', side_effect=open_request):
            bridge.request('/cases', original)
            bridge.request('/cases', restored)
        self.assertEqual(captured[0], captured[1])
