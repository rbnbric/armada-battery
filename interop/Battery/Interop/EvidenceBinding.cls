/// Adapter-owned case/measurement binding. The public intake cannot write this table.
/// Demo fixtures populate synthetic snapshots; external adapters are not yet connected.
Class Battery.Interop.EvidenceBinding Extends %Persistent
{
Property CaseId As %String(MAXLEN = 120) [ Required ];
Property CaseJSON As %String(MAXLEN = "") [ Required ];
Property ContractJSON As %String(MAXLEN = "") [ Required ];
Property InitialJSON As %String(MAXLEN = "");
Property CurrentJSON As %String(MAXLEN = "");
Index CaseKey On CaseId [ IdKey ];
}
