Include %occStatus

/// Read-only, traced adapter for persisted receipt snapshots. No SQL from models.
Class Battery.Interop.EvidenceOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method Read(pRequest As Battery.Interop.EvidenceRequest, Output pResponse As Battery.Interop.EvidenceResponse) As %Status
{
    Set pResponse=##class(Battery.Interop.EvidenceResponse).%New()
    If (pRequest.Phase'="INITIAL")&&(pRequest.Phase'="CHECK_EFFECT_RECEIPT")&&(pRequest.Phase'="CHECK_FRESH_READBACK")&&(pRequest.Phase'="CHECK_TARGET_VERSION")&&(pRequest.Phase'="FINAL") {
        Set pResponse.Reason="Unsupported read-only probe" Return $$$OK
    }
    Set binding=##class(Battery.Interop.EvidenceBinding).%OpenId(pRequest.CaseId)
    If '$IsObject(binding) { Set pResponse.Reason="No adapter-owned evidence binding" Return $$$OK }
    If binding.CaseJSON'=pRequest.CaseJSON { Set pResponse.Reason="Case differs from adapter-owned binding" Return $$$OK }
    If (binding.Adapter="management")&&(pRequest.Phase'="INITIAL") {
        Return ..Management(pRequest,binding,.pResponse)
    }
    Set pResponse.Found=1,pResponse.ContractJSON=binding.ContractJSON
    Set pResponse.ObservationJSON=$SELECT(pRequest.Phase="INITIAL":binding.InitialJSON,1:binding.CurrentJSON)
    Set pResponse.Reason="Read persisted adapter snapshot"
    Return $$$OK
}
/// Both tools are reads. Host, port and credential belong to deployment configuration.
Method Management(request As Battery.Interop.EvidenceRequest, binding As Battery.Interop.EvidenceBinding, Output response As Battery.Interop.EvidenceResponse) As %Status
{
    Set response=##class(Battery.Interop.EvidenceResponse).%New()
    Try {
        Set host=$SYSTEM.Util.GetEnviron("BATTERY_MANAGEMENT_HOST"),key=$SYSTEM.Util.GetEnviron("BATTERY_ADAPTER_KEY")
        If (host="")||($LENGTH(key)<32) { Set response.Reason="Management evidence adapter is not configured" Return $$$OK }
        Set http=##class(%Net.HttpRequest).%New(),http.Server=host,http.Port=8080,http.Timeout=5,http.OpenTimeout=3
        Do http.SetHeader("X-Battery-Adapter",key)
        Set path="/api/native-evidence/"_##class(%CSP.Page).EscapeURL(request.CaseId)_"?phase="_request.Phase
        Set sc=http.Get(path)
        If $$$ISERR(sc) { Return sc }
        If http.HttpResponse.StatusCode'=200 { Set response.Reason="Management evidence read was not accepted" Return $$$OK }
        If http.HttpResponse.Data.Size>65536 { Set response.Reason="Management evidence exceeds budget" Return $$$OK }
        Set body=##class(%DynamicObject).%FromJSON(http.HttpResponse.Data)
        Set contract=body.%Get("contract"),observation=body.%Get("observation"),tool=body.%Get("tool")
        If ('$IsObject(contract))||('$IsObject(observation))||('$IsObject(tool)) { Set response.Reason="Malformed management evidence" Return $$$OK }
        Set expected=##class(%DynamicObject).%FromJSON(binding.ContractJSON),it=expected.%GetIterator()
        If contract.%Size()'=expected.%Size() { Set response.Reason="Management contract changed" Return $$$OK }
        While it.%GetNext(.k,.v) {
            If (contract.%GetTypeOf(k)'=expected.%GetTypeOf(k))||(contract.%Get(k)'=v) { Set response.Reason="Management contract changed" Return $$$OK }
        }
        If (tool.%Get("tool")'=request.Phase)||(tool.%Get("receipt_id")'=expected.attempt) { Set response.Reason="Tool result scope mismatch" Return $$$OK }
        Set response.Found=1,response.ContractJSON=binding.ContractJSON,response.ObservationJSON=observation.%ToJSON(),response.ToolJSON=tool.%ToJSON(),response.Reason="Authenticated management evidence read"
        Return $$$OK
    } Catch ex { Return ex.AsStatus() }
}
XData MessageMap
{
<MapItems><MapItem MessageType="Battery.Interop.EvidenceRequest"><Method>Read</Method></MapItem></MapItems>
}
}
