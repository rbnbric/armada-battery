"""Require complete native qualification logs and fail on any failed check."""

import json
from pathlib import Path
import re
import sys


def records(text, prefix):
    return [json.loads(m.group(1)) for m in re.finditer(re.escape(prefix) + r"=(\{[^\r\n]*\})", text)]


def verify(qualification, regression, proof):
    for text, marker in ((qualification, "BONUS_QUALIFICATION_OK"),
                         (regression, "BONUS_REGRESSION_FINISHED"),
                         (regression, "TRACE_CONTRACTS_OK"), (proof, "PROOF_END")):
        if marker not in text:
            raise ValueError("Missing completion marker: " + marker)
    envelope_rows = records(qualification, "BONUS_ENVELOPES")
    if len(envelope_rows) != 1:
        raise ValueError("Expected one envelope test report")
    groups = {
        "envelopes": envelope_rows[0]["tests"],
        "integration": [r for r in records(qualification, "BONUS_CHECK") if r["name"] != "all_envelopes"],
        "solver": records(regression, "SOLVER_CASE"),
        "agent_faults": records(regression, "FAULT_CASE"),
        "trace": records(regression, "TRACE_CHECK"),
        "proof": records(proof, "PROOF_CHECK"),
    }
    expected = {"envelopes": 24, "integration": 13, "solver": 32, "agent_faults": 26, "trace": 3, "proof": 149}
    for name, rows in groups.items():
        if len(rows) != expected[name]:
            raise ValueError(f"{name}: expected {expected[name]} records, got {len(rows)}")
        for row in rows:
            if row.get("passed") not in (True, 1, "1"):
                raise ValueError(f"{name}: failed check {row.get('name', row.get('mode', 'unknown'))}")
        if name == "agent_faults":
            # FaultSuite deliberately repeats agree before and after restarting the production.
            modes = ["agree", "yes_fail", "no_pass", "unknown"]
            modes += ["reviewer_" + m for m in ("error", "noresponse", "empty", "malformed", "array", "fabricated", "extra", "timeout")]
            modes += ["investigator_" + m for m in ("error", "noresponse", "empty", "malformed", "array", "fabricated", "extra", "probe", "timeout")]
            modes += ["invalid_case", "oversize_case", "bad_case_types", "agree", "agree"]
            if [r["mode"] for r in rows] != modes:
                raise ValueError("agent_faults: incomplete or reordered fault sequence")
            continue
        identities = [str(r.get("case_id", r.get("name", r.get("mode")))) for r in rows]
        if len(set(identities)) != len(identities):
            raise ValueError(name + ": duplicate test record")
    all_logs = "\n".join((qualification, regression, proof))
    if re.search(r"(?:BONUS_(?:SUITE|COMPILE|QUALIFICATION|REGRESSION|STOP)|TRACE_CONTRACTS|FAULT_SUITE|SOLVER)_ERROR=", all_logs):
        raise ValueError("Native error marker present")
    return {"passed": sum(expected.values()), "failed": 0, "groups": expected}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: verify_bonus_results.py qualification.log regression.log proof.log")
    try:
        result = verify(*(Path(p).read_text(encoding="utf-8", errors="strict") for p in sys.argv[1:]))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit("BONUS_VERIFICATION_FAILED: " + str(error)) from error
    print(json.dumps(result, indent=2))
