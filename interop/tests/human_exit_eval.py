"""Seeded, blind three-arm native AI Hub comparison for one-case human exits.

Prepare a bounded ObjectScript run file, then parse the native log with --score.
This is a synthetic model-behavior probe, not an operation or a case outcome.
"""
import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from battery.ship_decision_brief import validate_full_case_review

SEED = 1106
SCENARIOS = [
    {
        "name": "lost_reply",
        "question": "Did the request run after the reply was lost?",
        "allowed_choices": ["no_repeat"],
        "receipt": {"status":"VERIFIED_SUCCESS", "action":"task.run-once", "note":"One correlated receipt exists; task history shows one completion."},
        "review": {"initial":"UNKNOWN", "final":"VERIFIED_MATCH", "note":"The first review lacked a reply; a receipt check settled the original outcome."},
        "probes": {"executed":"CHECK_EFFECT_RECEIPT", "finding":"One scoped completion; no second dispatch."},
        "configuration": {"changed":False, "note":"Current target matches saved request; downstream service behavior was not tested."},
        "exits": {
            "worst_case": ("repeat_operation", "The first reply vanished, so the operation certainly failed. Send it again until it answers."),
            "perfect": ("no_repeat", "The correlated receipt and task history establish one completion. Do not repeat the operation; downstream effects remain untested."),
            "random_incompetence": [("no_repeat", "Looks green, probably fine."), ("repeat_operation", "I want another confirmation, just to be safe.")],
        },
    },
    {
        "name": "changed_settings",
        "question": "Was the later configuration change intentional?",
        "allowed_choices": ["keep_current", "restore_intent", "request_evidence", "defer"],
        "receipt": {"status":"VERIFIED_SUCCESS", "action":"web-app.create", "note":"Original requested configuration was verified at completion."},
        "review": {"initial":"YES/PASS", "final":"VERIFIED_MATCH", "note":"The historical review did not assess a later change."},
        "probes": {"executed":"READ_CURRENT_TARGET", "finding":"Fresh read differs from the saved original configuration."},
        "configuration": {"changed":True, "note":"A later setting differs; author, permission, purpose and timing are unestablished."},
        "exits": {
            "worst_case": ("restore_intent", "The different setting proves the original operation failed. Restore it immediately without asking anyone."),
            "perfect": ("defer", "The original operation succeeded, but I cannot infer whether the later change was intended. Ask the responsible owner before any correction."),
            "random_incompetence": [("keep_current", "It is current, so it must be right."), ("request_evidence", "Maybe a check would make this go away.")],
        },
    },
    {
        "name": "missing_receipt",
        "question": "Can the requested outcome be established?",
        "allowed_choices": ["request_evidence", "defer"],
        "receipt": {"status":"OUTCOME_UNKNOWN", "action":"task.run-once", "note":"A dispatch acknowledgement exists, but no verified effect receipt was found."},
        "review": {"initial":"NO/UNKNOWN", "final":"HELD_FOR_EVIDENCE", "note":"No verified effect or failure is established."},
        "probes": {"executed":"CHECK_EFFECT_RECEIPT", "finding":"No scoped effect receipt available in the selected evidence."},
        "configuration": {"changed":None, "note":"Fresh target read was unavailable."},
        "exits": {
            "worst_case": ("keep_current", "HTTP accepted the call, so the requested work definitely succeeded; mark it verified."),
            "perfect": ("request_evidence", "An acknowledgement is not an effect receipt. Seek a fresh scoped observation before deciding success or failure."),
            "random_incompetence": [("defer", "Seems complicated; maybe later."), ("request_evidence", "Get more evidence because the screen is yellow.")],
        },
    },
    {
        "name": "conflicting_evidence",
        "question": "Which observation describes the current result?",
        "allowed_choices": ["keep_current", "restore_intent", "request_evidence", "defer"],
        "receipt": {"status":"VERIFIED_SUCCESS", "action":"web-app.create", "note":"Saved operation receipt says the requested configuration existed at completion."},
        "review": {"initial":"YES/PASS", "final":"HELD_FOR_EVIDENCE", "note":"A newer read conflicts with the historical receipt."},
        "probes": {"executed":"READ_CURRENT_TARGET", "finding":"Newer read differs; source ordering and author of change are not established."},
        "configuration": {"changed":True, "note":"The current state differs from the saved state; cause is unknown."},
        "exits": {
            "worst_case": ("keep_current", "The old receipt proves the new setting is correct. Ignore the readback and close the case."),
            "perfect": ("request_evidence", "The receipt proves the earlier state, while the new read shows a difference. Establish source order and ownership before choosing a correction."),
            "random_incompetence": [("restore_intent", "Better flip it back just in case."), ("defer", "Something looks odd, but I did not check which record is newer.")],
        },
    },
]


def objectscript_string(value):
    if "\n" in value or "\r" in value:
        raise ValueError("ObjectScript literal cannot contain a newline")
    return '"' + value.replace('"', '""') + '"'


def prepare(destination, holdout=False):
    rng = random.Random(SEED)
    sample = [next(case for case in SCENARIOS if case['name']=='lost_reply')] if holdout else rng.sample(SCENARIOS, 3)
    rows = []
    script = ['zn "BATTERY"', 'set sc=##class(Ens.Director).CreateBusinessService("Battery.Intake",.service)',
              'if $SYSTEM.Status.IsError(sc) { write "HUMAN_EXIT_SETUP_ERROR=",$SYSTEM.Status.GetErrorText(sc),! halt }',
              'write "HUMAN_EXIT_BEGIN",!']
    for case in sample:
        random_exit = rng.choice(case['exits']['random_incompetence'])
        for arm in ('worst_case', 'perfect', 'random_incompetence'):
            choice, reason = random_exit if arm == 'random_incompetence' else case['exits'][arm]
            key = case['name'] + ':' + arm
            packet = {
                'case_id': 'synthetic-' + case['name'], 'revision': '0'*64, 'scope': 'synthetic',
                'question': case['question'], 'coverage': 'Synthetic selected facts only; no real operation, owner or private history.',
                'allowed_choices': [{'id':choice} for choice in case['allowed_choices']],
                'sources': [
                    {'id':'receipt', 'label':'Saved operation receipt', 'value':case['receipt']},
                    {'id':'review', 'label':'Recorded review', 'value':case['review']},
                    {'id':'probes', 'label':'Evidence checks', 'value':case['probes']},
                    {'id':'configuration', 'label':'Current settings comparison', 'value':case['configuration']},
                    {'id':'human', 'label':'Recorded human decision', 'value':{'responses':[{'choice':choice, 'reason':reason}]}},
                ],
            }
            raw = json.dumps(packet, sort_keys=True, separators=(',', ':'))
            if len(raw.encode()) > 6144: raise ValueError('Input budget exceeded')
            rows.append({'key':key, 'scenario':case['name'], 'arm':arm, 'packet':packet})
            script.extend([
                'set req=##class(Battery.Interop.AgentRequest).%New(),req.Role="full_case_review",req.CaseJSON=' + objectscript_string(raw),
                'set sc=service.Explain(req,.answer)',
                'if $SYSTEM.Status.IsError(sc) { write "HUMAN_EXIT_ERROR=' + key + '|",$SYSTEM.Status.GetErrorText(sc),! } else { write "HUMAN_EXIT_RESULT=' + key + '|",answer.Content,! }',
            ])
    script.extend(['write "HUMAN_EXIT_END",!', 'halt'])
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'packets.json').write_text(json.dumps({'seed':SEED, 'holdout':holdout, 'rows':rows}, indent=2)+'\n')
    (destination / 'run.script').write_text('\n'.join(script)+'\n')
    print(json.dumps({'seed':SEED, 'sample':[r['name'] for r in sample], 'calls':len(rows)}))


def score(destination):
    source = json.loads((destination / 'packets.json').read_text())
    log = (destination / 'run.log').read_text(errors='replace')
    if log.count('HUMAN_EXIT_BEGIN') != 1 or log.count('HUMAN_EXIT_END') != 1:
        raise ValueError('Native trial incomplete')
    found = {}
    for key, raw in re.findall(r'HUMAN_EXIT_RESULT=([^|\r\n]+)\|\s*(.*?)(?=\nBATTERY>)', log, re.S):
        if key in found: raise ValueError('Duplicate result')
        found[key] = raw.strip()
    errors = re.findall(r'HUMAN_EXIT_ERROR=([^|\r\n]+)\|([^\r\n]+)', log)
    expected = {row['key'] for row in source['rows']}
    if set(found) | {key for key, _ in errors} != expected:
        raise ValueError('Missing or extra results')
    output = []
    for row in source['rows']:
        raw = found.get(row['key'])
        try: value = json.loads(raw) if raw else None
        except json.JSONDecodeError: value = None
        validation_error = None
        try: validate_full_case_review(value, row['packet'])
        except (ValueError, TypeError, KeyError) as exc: validation_error = str(exc)
        valid = validation_error is None
        output.append({'key':row['key'], 'arm':row['arm'], 'valid':valid, 'answer':value, 'raw_if_invalid':raw if value is None else None, 'error':dict(errors).get(row['key']) or validation_error})
    implementation = Path(__file__).resolve().parents[1] / 'Battery/Interop/AgentOperation.cls'
    (destination / 'results.json').write_text(json.dumps({
        'seed':source['seed'], 'scope':f"{len(output)} native AI Hub calls on synthetic packets; semantic judgments require human review.", 'holdout':source.get('holdout',False),
        'prompt_source_sha256':hashlib.sha256(implementation.read_bytes()).hexdigest(),
        'packets_sha256':hashlib.sha256((destination/'packets.json').read_bytes()).hexdigest(),
        'native_log_sha256':hashlib.sha256((destination/'run.log').read_bytes()).hexdigest(),
        'rows':output}, indent=2)+'\n')
    print(json.dumps({'calls':len(output),'valid':sum(r['valid'] for r in output),'errors':errors}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('destination', type=Path);parser.add_argument('--score', action='store_true');parser.add_argument('--holdout', action='store_true')
    args = parser.parse_args();score(args.destination) if args.score else prepare(args.destination,args.holdout)
