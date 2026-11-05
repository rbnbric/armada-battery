Class Battery.Interop.EvidenceResponse Extends Ens.Response
{
Property ToolJSON As %String(MAXLEN="");
Property Found As %Boolean;
Property ContractJSON As %String(MAXLEN = "");
Property ObservationJSON As %String(MAXLEN = "");
Property Reason As %String(MAXLEN = 300);
}
