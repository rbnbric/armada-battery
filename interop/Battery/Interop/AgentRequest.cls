/// Ask the native IRIS AI Hub operation for one bounded agent decision.
Class Battery.Interop.AgentRequest Extends Ens.Request
{
Property Role As %String(MAXLEN = 20) [ Required ];
Property RepairJSON As %String(MAXLEN = "");
Property CaseJSON As %String(MAXLEN = "") [ Required ];
}
