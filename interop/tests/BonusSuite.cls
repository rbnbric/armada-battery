Include %occStatus

/// Real IRIS adapter + Embedded Python tests; HTTP fixture stays on loopback.
Class Battery.Test.BonusSuite Extends %RegisteredObject
{
ClassMethod Envelopes() As %String [ Language = python ]
{
    import copy
    import json
    import iris
    validate = iris.cls("Battery.Interop.EvidenceEnvelope").Validate
    contract = {"profile":"receipt-v1","partner":"fixture","attempt":"attempt-1","target":"target-1",
                "version":"v1","rule_version":"v1","expected_count":1,"expected_result":"COMPLETE",
                "accepted_count":1,"accepted_result":"COMPLETE","max_age":300}
    body = {"contract":contract,"observation":{"available":False},
            "tool":{"tool":"FINAL","receipt_id":"attempt-1","note":"café 東京"}}
    expected = json.dumps(contract)
    cases = [("valid", json.dumps(body), expected, "FINAL", True)]
    for key, value in (("partner","other"),("attempt","other"),("version","v2"),
                       ("expected_count",True),("expected_count","1")):
        changed = copy.deepcopy(body)
        changed["contract"][key] = value
        cases.append(("changed_"+key+"_"+type(value).__name__,json.dumps(changed),expected,"FINAL",False))
    for key in ("contract","observation","tool"):
        changed = copy.deepcopy(body)
        changed[key] = []
        cases.append(("array_"+key,json.dumps(changed),expected,"FINAL",False))
    for key in ("tool","receipt_id"):
        changed = copy.deepcopy(body)
        changed["tool"][key] = "other"
        cases.append(("changed_tool_"+key,json.dumps(changed),expected,"FINAL",False))
    changed = copy.deepcopy(body)
    changed["contract"]["unexpected"] = 1
    cases.append(("extra_contract_field",json.dumps(changed),expected,"FINAL",False))
    numeric = copy.deepcopy(body)
    numeric["contract"]["expected_count"] = 1.0
    cases.extend([
        ("number_equivalence",json.dumps(numeric),expected,"FINAL",True),
        ("unicode",json.dumps(body,ensure_ascii=False),expected,"FINAL",True),
        ("bad_json","{",expected,"FINAL",False),
        ("array_root","[]",expected,"FINAL",False),
        ("missing_fields","{}",expected,"FINAL",False),
        ("bad_binding",json.dumps(body),"[]","FINAL",False),
        ("duplicate",json.dumps(body).replace('"available": false','"available": false, "available": true'),expected,"FINAL",False),
        ("nan",json.dumps(body).replace('"available": false','"available": NaN'),expected,"FINAL",False),
        ("overflow",json.dumps(body).replace('"available": false','"available": 1e999'),expected,"FINAL",False),
        ("depth","["*2000+"0"+"]"*2000,expected,"FINAL",False),
        ("oversize"," "*65537,expected,"FINAL",False),
        ("unadmitted_phase",json.dumps(body),expected,"DELETE",False),
    ])
    rows=[]
    for name,raw,bound,phase,wanted in cases:
        result=json.loads(validate(raw,bound,phase))
        rows.append({"name":name,"passed":result["accepted"] is wanted,"reason":result["reason"]})
    return json.dumps({"scope":"Embedded Python in IRIS", "tests":rows,
                       "passed":sum(r["passed"] for r in rows),"total":len(rows)})
}

ClassMethod Fixture(mode As %String, body As %String = "") As %Integer [ Language = python ]
{
    import json
    from pathlib import Path
    import subprocess
    import sys
    import tempfile
    import time
    import types
    name="_battery_bonus_fixture"
    if name not in sys.modules:
        fixture=types.ModuleType(name)
        fixture.process=None
        fixture.directory=Path(tempfile.mkdtemp(prefix="battery-bonus-fixture-"))
        sys.modules[name]=fixture
    fixture=sys.modules[name]
    counts=fixture.directory/"calls.txt"
    calls=int(counts.read_text()) if counts.exists() else 0
    if mode == "count":
        return calls
    if mode == "stop":
        if fixture.process:
            fixture.process.terminate()
            fixture.process.wait(timeout=3)
            fixture.log.close()
            fixture.process=None
        return calls
    temporary=fixture.directory/"state.new"
    temporary.write_text(json.dumps({"mode":mode,"body":body}))
    temporary.replace(fixture.directory/"state.json")
    if fixture.process:
        return calls
    fixture.log=(fixture.directory/"server.log").open("w")
    fixture.process=subprocess.Popen(["/usr/irissys/bin/irispython",
        "/home/irisowner/dev/bonus/tests/bonus-http-fixture.py",str(fixture.directory)],
        stdout=fixture.log,stderr=subprocess.STDOUT)
    deadline=time.monotonic()+5
    while not (fixture.directory/"ready").exists():
        if fixture.process.poll() is not None or time.monotonic()>deadline:
            raise RuntimeError("Loopback HTTP fixture failed: "+(fixture.directory/"server.log").read_text())
        time.sleep(0.05)
    return calls
}

ClassMethod Assert(label As %String, ok As %Boolean)
{
    Set row={"name":(label),"passed":(ok)}
    Write "BONUS_CHECK=",row.%ToJSON(),!
    If 'ok { Throw ##class(%Exception.General).%New("Bonus check failed: "_label) }
}

ClassMethod Run() As %Status
{
    Try {
        Set result=##class(%DynamicObject).%FromJSON(..Envelopes())
        Write "BONUS_ENVELOPES=",result.%ToJSON(),!
        Do ..Assert("all_envelopes",result.passed=result.total)
        Set contract={"partner":"fixture","attempt":"attempt-1"}
        Set body={"contract":(contract),"observation":{"available":false},"tool":{"tool":"FINAL","receipt_id":"attempt-1"}}
        Do body.tool.%Set("note",$CHAR(233)_$CHAR(26481))
        Do ..Fixture("valid",body.%ToJSON())
        Set adapter=##class(Battery.Interop.EvidenceAdapter).%New()
        Set sc=adapter.ReadEvidence("bonus-fixture","FINAL","fixture",.raw,.reason)
        If $$$ISERR(sc) { Write "BONUS_HTTP_ERROR=",$SYSTEM.Status.GetErrorText(sc),! }
        If reason'="" { Write "BONUS_HTTP_REASON=",reason,! }
        Do ..Assert("real_http_read",$$$ISOK(sc)&&(reason="")&&(raw'=""))
        Set checked=##class(%DynamicObject).%FromJSON(##class(Battery.Interop.EvidenceEnvelope).Validate(raw,contract.%ToJSON(),"FINAL"))
        Do ..Assert("http_to_embedded_python",checked.accepted)
        Do ..Assert("http_utf8_preserved",checked.tool.note=body.tool.note)
        Set before=..Fixture("count")
        Set sc=adapter.ReadEvidence("bonus-fixture","DELETE","fixture",.raw,.reason)
        Do ..Assert("phase_blocked_before_http",$$$ISOK(sc)&&(reason="Unsupported read-only probe")&&(..Fixture("count")=before))
        Do ..Fixture("denied")
        Set sc=adapter.ReadEvidence("bonus-fixture","FINAL","fixture",.raw,.reason)
        Do ..Assert("http_401_held",$$$ISOK(sc)&&(reason="Management evidence read was not accepted"))
        Do ..Assert("http_not_retried",..Fixture("count")=(before+1))
        Do ..Fixture("oversize")
        Set sc=adapter.ReadEvidence("bonus-fixture","FINAL","fixture",.raw,.reason)
        Do ..Assert("http_size_budget",$$$ISOK(sc)&&(reason="Management evidence exceeds budget")&&(raw=""))
        Do ..Fixture("valid",body.%ToJSON())
        Set sc=##class(Ens.Director).StartProduction("Battery.Interop.Production")
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set binding=##class(Battery.Interop.EvidenceBinding).%OpenId("bonus-fixture")
        If '$IsObject(binding) { Set binding=##class(Battery.Interop.EvidenceBinding).%New(),binding.CaseId="bonus-fixture" }
        Set binding.Adapter="management",binding.CaseJSON="{}",binding.ContractJSON=contract.%ToJSON()
        Set sc=binding.%Save()
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set request=##class(Battery.Interop.EvidenceRequest).%New(),request.CaseId="bonus-fixture",request.CaseJSON="{}",request.Phase="FINAL"
        Set sc=##class(Ens.Director).CreateBusinessService("Battery.Intake",.service)
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set sc=service.SendRequestSync("Battery.Evidence",request,.response,15)
        Do ..Assert("queued_native_adapter",$$$ISOK(sc)&&$IsObject(response))
        Do ..Assert("queued_envelope_accepted",response.Found&&(response.Reason="Authenticated management evidence read"))
        Set checked=##class(%DynamicObject).%FromJSON(response.ToolJSON)
        Do ..Assert("queued_utf8_preserved",checked.note=body.tool.note)
        Do body.contract.%Set("partner","other")
        Do ..Fixture("valid",body.%ToJSON())
        Set sc=service.SendRequestSync("Battery.Evidence",request,.response,15)
        Do ..Assert("queued_cross_scope_held",$$$ISOK(sc)&&('response.Found)&&(response.Reason="Management contract changed"))
        Do ..Fixture("valid","{""contract"":{},""contract"":{},""observation"":{},""tool"":{}}")
        Set sc=service.SendRequestSync("Battery.Evidence",request,.response,15)
        Do ..Assert("queued_duplicate_json_held",$$$ISOK(sc)&&('response.Found)&&(response.Reason="Malformed management evidence"))
        Do ..Fixture("stop")
        Set sc=adapter.ReadEvidence("bonus-fixture","FINAL","fixture",.raw,.reason)
        Do ..Assert("refused_connection_is_error",$$$ISERR(sc))
        Write "BONUS_SUITE_OK",!
        Return $$$OK
    } Catch ex {
        Do ..Fixture("stop")
        Write "BONUS_SUITE_ERROR=",ex.DisplayString(),!
        Return ex.AsStatus()
    }
}
}
