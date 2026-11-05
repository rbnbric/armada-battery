/// Ask the native IRIS AI Hub operation for one bounded agent decision.
Class Battery.Interop.AgentRequest Extends Ens.Request
{
Property RunId As %String(MAXLEN=120);
Property Lease As %String(MAXLEN=100);
Property Role As %String(MAXLEN = 20) [ Required ];
Property RepairJSON As %String(MAXLEN = "");
Property CaseJSON As %String(MAXLEN = "") [ Required ];
}
