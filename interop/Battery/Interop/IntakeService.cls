Include %occStatus

/// Adapterless input for repeatable cases in an actual IRIS production.
Class Battery.Interop.IntakeService Extends Ens.BusinessService
{
Parameter ADAPTER = "";

Method OnProcessInput(pInput As Battery.Interop.CaseRequest, Output pOutput As Battery.Interop.CaseResponse, pHint As %String = "") As %Status
{
    Quit ..SendRequestSync("Battery.CaseProcess", pInput, .pOutput)
}
}
