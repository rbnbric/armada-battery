Include %occStatus

/// Read-only, traced adapter for persisted receipt snapshots. No SQL from models.
Class Battery.Interop.EvidenceOperation Extends Ens.BusinessOperation
{
Parameter INVOCATION = "Queue";
Method Read(pRequest As Battery.Interop.EvidenceRequest, Output pResponse As Battery.Interop.EvidenceResponse) As %Status
{
    Set pResponse=##class(Battery.Interop.EvidenceResponse).%New()
    If (pRequest.Phase'="INITIAL")&&(pRequest.Phase'="CHECK_EFFECT_RECEIPT")&&(pRequest.Phase'="CHECK_FRESH_READBACK")&&(pRequest.Phase'="FINAL") {
        Set pResponse.Reason="Unsupported read-only probe" Return $$$OK
    }
    Set binding=##class(Battery.Interop.EvidenceBinding).%OpenId(pRequest.CaseId)
    If '$IsObject(binding) { Set pResponse.Reason="No adapter-owned evidence binding" Return $$$OK }
    If binding.CaseJSON'=pRequest.CaseJSON { Set pResponse.Reason="Case differs from adapter-owned binding" Return $$$OK }
    Set pResponse.Found=1,pResponse.ContractJSON=binding.ContractJSON
    Set pResponse.ObservationJSON=$SELECT(pRequest.Phase="INITIAL":binding.InitialJSON,1:binding.CurrentJSON)
    Set pResponse.Reason="Read persisted adapter snapshot"
    Return $$$OK
}
XData MessageMap
{
<MapItems><MapItem MessageType="Battery.Interop.EvidenceRequest"><Method>Read</Method></MapItem></MapItems>
}
}
