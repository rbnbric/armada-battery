/// A bounded evidence case supplied to Battery's interoperability workflow.
Class Battery.Interop.CaseRequest Extends Ens.Request
{
Property RunId As %String(MAXLEN=120);
Property CaseJSON As %String(MAXLEN = "") [ Required ];
}
