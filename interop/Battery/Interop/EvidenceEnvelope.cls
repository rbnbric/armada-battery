/// Strict JSON boundary executed by Embedded Python inside the IRIS worker.
/// Validating an envelope does not establish that its observation proves success.
Class Battery.Interop.EvidenceEnvelope Extends %RegisteredObject
{
ClassMethod Validate(raw As %String, expected As %String, phase As %String) As %String [ Language = python ]
{
    import json
    import math

    def rejected(reason):
        return json.dumps({"accepted": False, "reason": reason})

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON member")
            result[key] = value
        return result

    def invalid_number(value):
        raise ValueError("Non-finite JSON number")

    def same(left, right):
        # JSON has one number type, but booleans and strings are distinct.
        if type(left) in (int, float) and type(right) in (int, float):
            return math.isfinite(left) and math.isfinite(right) and left == right
        if type(left) is not type(right):
            return False
        if isinstance(left, dict):
            return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
        if isinstance(left, list):
            return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
        return left == right

    try:
        if len(raw.encode("utf-8")) > 65536 or len(expected.encode("utf-8")) > 65536:
            return rejected("Management evidence exceeds budget")
        if phase not in ("CHECK_EFFECT_RECEIPT", "CHECK_FRESH_READBACK", "CHECK_TARGET_VERSION", "FINAL"):
            return rejected("Unsupported read-only probe")
        options = {"object_pairs_hook": unique_object, "parse_constant": invalid_number}
        body, contract = json.loads(raw, **options), json.loads(expected, **options)
        if not isinstance(body, dict) or not isinstance(contract, dict):
            return rejected("Malformed management evidence")
        if not all(isinstance(body.get(k), dict) for k in ("contract", "observation", "tool")):
            return rejected("Malformed management evidence")
        if not same(body["contract"], contract):
            return rejected("Management contract changed")
        tool = body["tool"]
        if not isinstance(contract.get("attempt"), str) or not contract["attempt"]:
            return rejected("Malformed evidence binding")
        if tool.get("tool") != phase or tool.get("receipt_id") != contract["attempt"]:
            return rejected("Tool result scope mismatch")
        return json.dumps({"accepted": True, "reason": "Authenticated management evidence read",
                           "observation": body["observation"], "tool": tool}, allow_nan=False)
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        return rejected("Malformed management evidence")
}
}
