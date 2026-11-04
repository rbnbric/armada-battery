Include %occStatus
Class Battery.Test.SolverEvidence Extends Battery.Interop.EvidenceOperation
{
Method Read(pRequest As Battery.Interop.EvidenceRequest, Output pResponse As Battery.Interop.EvidenceResponse) As %Status
{
    Set mode=$Get(^BatterySolverTest("mode")),phase=pRequest.Phase
    If ((mode="initial_read_error")&&(phase="INITIAL"))||((mode="probe_read_error")&&(phase="CHECK_EFFECT_RECEIPT"))||((mode="final_read_error")&&(phase="FINAL")) { Return $$$ERROR($$$GeneralError,"Injected evidence read error") }
    Return ##super(pRequest,.pResponse)
}
}
