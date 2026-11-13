Include %occStatus

/// Traced evidence reads, with a native outbound adapter and strict envelope validation.
Class Battery.Interop.EvidenceOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Parameter ADAPTER = "Battery.Interop.EvidenceAdapter";
Property Adapter As Battery.Interop.EvidenceAdapter;
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
        Set scope=##class(%DynamicObject).%FromJSON(binding.ContractJSON)
        Set sc=..Adapter.ReadEvidence(request.CaseId,request.Phase,scope.partner,.raw,.reason)
        If $$$ISERR(sc) { Return sc }
        If reason'="" { Set response.Reason=reason Return $$$OK }
        Set checked=##class(%DynamicObject).%FromJSON(##class(Battery.Interop.EvidenceEnvelope).Validate(raw,binding.ContractJSON,request.Phase))
        If 'checked.accepted { Set response.Reason=checked.reason Return $$$OK }
        Set response.Found=1,response.ContractJSON=binding.ContractJSON,response.ObservationJSON=checked.observation.%ToJSON(),response.ToolJSON=checked.tool.%ToJSON(),response.Reason=checked.reason
        Return $$$OK
    } Catch ex { Return ex.AsStatus() }
}
XData MessageMap
{
<MapItems><MapItem MessageType="Battery.Interop.EvidenceRequest"><Method>Read</Method></MapItem></MapItems>
}
}
