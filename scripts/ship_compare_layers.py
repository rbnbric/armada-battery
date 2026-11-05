"""Compare retained agent judgments with native receipt proof on identical snapshots.

SHIP_MANIFEST:
META:
  name: ship_compare_layers
  author: robin
  kind: operation
  capabilities: [ANALYZE]
  domains: [venture, evaluation]
  description: Score retained Battery agent stages against native snapshot baselines
INPUTS:
  - name: source
    type: str
    required: true
  - name: native_log
    type: str
    required: true
OUTPUTS:
  - name: comparison
    type: dict
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load_cases(path):
    data = json.loads(Path(path).read_text())
    rows = [r for r in data["native_rows"] if r["live"] == 1]
    if not rows or len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("Missing or duplicate real-model case records")
    for row in rows:
        reads = row["reads"]
        if not row["reviews"] or reads[0]["phase"] != "INITIAL" or reads[-1]["phase"] != "FINAL":
            raise ValueError("Incomplete case; cannot silently omit it")
        if any(not r["found"] for r in reads):
            raise ValueError("Unbound snapshot needs a separate comparison profile")
        if len({r["contract"] for r in reads}) != 1:
            raise ValueError("Changed contracts need a separate comparison profile")
        selected = reads[-2] if len(reads) > 2 else reads[0]
        if selected["observation"] != reads[-1]["observation"]:
            raise ValueError("Changing final evidence needs a separate comparison profile")
    return rows

def snapshots(rows):
    result = []
    for row in rows:
        observations = [json.loads(r["observation"]) for r in row["reads"]]
        stamps = [o["observed_at"] for o in observations if "observed_at" in o]
        if any(type(n) is not int or n <= 0 for n in stamps):
            raise ValueError("Invalid recorded clock")
        # Controlled replay clock, NOT reconstruction of the historical execution clock.
        now = max(stamps, default=6000000000)
        for stage, read in (("initial", row["reads"][0]), ("final", row["reads"][-1])):
            item = {"case_id": row["case_id"], "stage": stage,
                    "contract": read["contract"], "observation": read["observation"], "now": now}
            item["key"] = digest(json.dumps(item, sort_keys=True).encode())
            result.append(item)
    return result

def os_string(text):
    if "\n" in text or "\r" in text:
        raise ValueError("Multiline ObjectScript literal refused")
    return '"' + text.replace('"', '""') + '"'

def prepare(source):
    items = snapshots(load_cases(source))
    lines = ['zn "BATTERY"', 'write !,"COMPARISON_BEGIN=",$ZVERSION,!']
    for item in items:
        call = '##class(Battery.Interop.OutcomeProof).Assess(%s,%s,%s)' % (
            os_string(item["contract"]), os_string(item["observation"]), item["now"])
        lines.append('set proof=' + call)
        lines.append('write !,"COMPARISON_ROW=' + item["key"] + '|",proof.%ToJSON(),!')
    lines += ['write !,"COMPARISON_END",!', 'halt']
    return "\n".join(lines) + "\n"

def parse_native(log, items):
    if "COMPARISON_BEGIN=" not in log or len(re.findall(r"(?m)^COMPARISON_END\r?$", log)) != 1:
        raise ValueError("Native run incomplete")
    if re.search(r"<(?:UNDEFINED|SYNTAX|INVALID|FUNCTION|METHOD|PROTECT|NAMESPACE|SUBSCRIPT|OBJECT|CLASS)[^>]*>", log):
        raise ValueError("Native execution error")
    found = {}
    for match in re.finditer(r"(?m)^COMPARISON_ROW=([0-9a-f]{64})\|([^\r\n]+)", log):
        key, raw = match.groups()
        if key in found:
            raise ValueError("Duplicate native result")
        proof = json.loads(raw)
        if proof.get("verdict") not in ("YES", "NO") or proof.get("output") not in ("PASS", "FAIL", "UNKNOWN") or type(proof.get("usable")) is not bool:
            raise ValueError("Malformed native proof")
        if not proof["usable"] and (proof["verdict"], proof["output"]) != ("NO", "UNKNOWN"):
            raise ValueError("Unusable proof claimed a measured result")
        found[key] = proof
    if set(found) != {item["key"] for item in items}:
        raise ValueError("Missing, extra, or differently bound native results")
    return found

def pair(proof):
    return [proof["verdict"], proof["output"]]

def state(proof):
    if not proof["usable"]:
        return "HELD_FOR_EVIDENCE"
    return "VERIFIED_MATCH" if pair(proof) == ["YES", "PASS"] else "VERIFIED_MISMATCH"

def score(source, native_log):
    source, native_log = Path(source), Path(native_log)
    rows = load_cases(source); items = snapshots(rows)
    proofs = parse_native(native_log.read_text(), items)
    indexed = {(i["case_id"], i["stage"]): proofs[i["key"]] for i in items}
    output = []
    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "llm_ms": 0}
    usage_fields = {"calls": "total_interactions", "prompt_tokens": "total_prompt_tokens",
                    "completion_tokens": "total_completion_tokens", "llm_ms": "total_llm_duration_ms"}
    for row in rows:
        first = indexed[row["case_id"], "initial"]; last = indexed[row["case_id"], "final"]
        review = row["reviews"][0]; target = [row["expected_verdict"], row["expected_output"]]
        for round_ in row["reviews"]:
            # Count call records once, including rejected answers / repair calls.
            calls = json.loads(round_["agent_calls"])
            for call in calls:
                measured = json.loads(call["usage"]) if call["usage"] else {}
                for key, field in usage_fields.items():
                    value = measured.get(field)
                    if type(value) is not int or value < 0:
                        raise ValueError("Missing/invalid measured usage: " + field)
                    usage[key] += value
        output.append({"case_id": row["case_id"], "mode": row["mode"], "round": row["round"],
            "target": target, "expected_state": row["expected_state"],
            "rules_initial": pair(first), "rules_final_evidence": pair(last),
            "first_validated_review": [review["verdict"], review["output"]],
            "first_review_matches_initial_evidence": [review["verdict"], review["output"]] == pair(first),
            "recorded_workflow": [row["gate_verdict"], row["gate_output"]],
            "recorded_state": row["state"], "rules_final_state": state(last),
            "review_rounds": len(row["reviews"]), "evidence_reads": len(row["reads"]),
            "executed_probe": row["executed_probe"]})
    totals = {name: sum(r[name] == r["target"] for r in output) for name in
              ("rules_initial", "first_validated_review", "rules_final_evidence", "recorded_workflow")}
    totals.update(cases=len(output), distinct_scenarios=len({r["mode"] for r in output}),
        first_reviews_matching_initial_evidence=sum(r["first_review_matches_initial_evidence"] for r in output),
        rules_final_states_correct=sum(r["rules_final_state"] == r["expected_state"] for r in output),
        recorded_states_correct=sum(r["recorded_state"] == r["expected_state"] for r in output))
    return {"schema": "battery-layer-comparison/v1", "scope": "Retrospective native proof replay of retained synthetic scenarios; historical real-model responses",
        "source_sha256": digest(source.read_bytes()), "native_log_sha256": digest(native_log.read_bytes()),
        "replay_script_sha256": digest(prepare(source).encode()), "summary": totals,
        "historical_model_usage": usage, "new_model_calls": 0, "rows": output,
        "limits": ["Final snapshots came from the recorded workflow; this is not independent recovery execution.",
                   "Replay clock is latest observed_at per case; this does not test historical freshness or latency.",
                   "First review is the first validated response, after bounded repair if present; usage includes rejected calls.",
                   "Known development cases repeated three times are not independent unseen cases.",
                   "Observed rule parity does not measure explanation usefulness or general agent superiority.",
                   "SDK usage is not a billing receipt; replay duration is not comparable to historical workflow latency."]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "interop/results/implementation-109.json")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path); modes.add_argument("--score", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        args.prepare.write_text(prepare(args.source)); print("Prepared read-only native proof replay; no agent calls.")
    else:
        result = score(args.source, args.score)
        if args.output: args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result["summary"], indent=2))

# Optional internal discovery; the public CLI above uses only Python's standard library.
def register_with_toolbay(tool_bay):
    from devlathe.core.navbeacon import Capability, PluginInfo, Result
    class Comparison:
        info = PluginInfo(name="ship_compare_layers", description="Score native receipt comparison", capabilities=Capability.ANALYZE)
        def execute(self, **kwargs):
            return Result.success("Scored retained evidence", data=score(kwargs["source"], kwargs["native_log"]))
    tool_bay.register(Comparison())
    return Result.success("Registered ship_compare_layers")

if __name__ == "__main__":
    main()
