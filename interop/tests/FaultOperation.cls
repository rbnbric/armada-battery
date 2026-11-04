Include %occStatus

/// Test-only provider boundary. No external model requests are issued.
Class Battery.Test.FaultOperation Extends Battery.Interop.AgentOperation
{
Method RunAgent(pRequest As Battery.Interop.AgentRequest, Output pResponse As Battery.Interop.AgentResponse) As %Status
{
    Set role=pRequest.Role, mode=$Get(^BatteryFault("mode"))
    Set count=$Increment(^BatteryFault("calls",role))
    Set ^BatteryFault("request",role)=pRequest.CaseJSON
    If mode=(role_"_error") { Return $$$ERROR($$$GeneralError,"Injected provider boundary failure") }
    If mode=(role_"_noresponse") { Set pResponse="" Return $$$OK }
    If mode=(role_"_timeout") { Hang 3 }
    Set pResponse=##class(Battery.Interop.AgentResponse).%New()
    Set pResponse.UsageJSON="{}"
    If role="reviewer" {
        Set body={"verdict":"NO","applicability":"APPLICABLE","output_result":"FAIL","evidence_ids":["F1"],"summary":"Injected review"}
        If mode="agree" { Do body.%Set("verdict","YES"),body.%Set("output_result","PASS") }
        If mode="yes_fail" { Do body.%Set("verdict","YES") }
        If mode="no_pass" { Do body.%Set("output_result","PASS") }
        If mode="unknown" { Do body.%Set("applicability","UNKNOWN"),body.%Set("output_result","UNKNOWN") }
    } Else {
        Set body={"next_probe":"CHECK_EFFECT_RECEIPT","hypothesis":"Inspect supplied evidence","evidence_ids":["F1"],"uncertainty":"Test fixture"}
    }
    If mode=(role_"_fabricated") { Do body.%Set("evidence_ids",["invented"]) }
    If mode=(role_"_extra") { Do body.%Set("execute","SEND_NOW") }
    If (role="investigator")&&(mode="investigator_probe") { Do body.%Set("next_probe","SEND_AGAIN") }
    Set pResponse.Content=body.%ToJSON()
    If mode=(role_"_empty") { Set pResponse.Content="" }
    If mode=(role_"_malformed") { Set pResponse.Content="{" }
    If mode=(role_"_array") { Set pResponse.Content="[]" }
    Return $$$OK
}
}
