Include %occStatus
/// Adversarial test provider: deliberately affirms every case unless an error is injected.
Class Battery.Test.SolverAgent Extends Battery.Interop.AgentOperation
{
Method RunAgent(pRequest As Battery.Interop.AgentRequest, Output pResponse As Battery.Interop.AgentResponse) As %Status
{
    Set n=$Increment(^BatterySolverTest("calls")),mode=$Get(^BatterySolverTest("mode"))
    If mode="provider_error" { Return $$$ERROR($$$GeneralError,"Injected provider error") }
    Set pResponse=##class(Battery.Interop.AgentResponse).%New()
    Set pResponse.UsageJSON="{}"
    Set r={"verdict":"YES","output_result":"PASS","applicability":"APPLICABLE","summary":"Deliberately overconfident test reviewer","evidence_ids":["B_OBSERVATION"]}
    If mode="invalid_model" { Do r.%Set("evidence_ids",["invented"]) }
    If ((mode="investigator_bad_recovered")||(mode="investigator_error_recovered"))&&(n=1) { Do r.%Set("verdict","NO"),r.%Set("output_result","UNKNOWN") }
    Set pResponse.Content=r.%ToJSON()
    If (pRequest.Role="investigator")&&(mode="investigator_bad_recovered") { Set pResponse.Content="{" }
    If (pRequest.Role="investigator")&&(mode="investigator_error_recovered") { Return $$$ERROR($$$GeneralError,"Injected investigator failure after valid reviewer") }
    If (n=1)&&((mode="changed_contract")||(mode="changed_case")||(mode="changed_observation")) {
        Set b=##class(Battery.Interop.EvidenceBinding).%OpenId(^BatterySolverTest("case"))
        If mode="changed_contract" { Set c=##class(%DynamicObject).%FromJSON(b.ContractJSON) Do c.%Set("accepted_count",2) Set b.ContractJSON=c.%ToJSON() }
        If mode="changed_case" { Set b.CaseJSON="{}" }
        If mode="changed_observation" { Set o=##class(%DynamicObject).%FromJSON(b.CurrentJSON) Do o.%Set("count",2) Set b.CurrentJSON=o.%ToJSON() }
        Set sc=b.%Save()
        If $$$ISERR(sc) { Return sc }
    }
    Return $$$OK
}
}
