/// Visible result of a Battery interoperability review. No external effect is sent.
Class Battery.Interop.CaseResponse Extends Ens.Response
{
Property CaseId As %String(MAXLEN = 120);
Property State As %String(MAXLEN = 60);
Property ReviewerVerdict As %String(MAXLEN = 8);
Property ReviewerApplicability As %String(MAXLEN = 20);
Property OutputResult As %String(MAXLEN = 20);
Property InvestigatorProbe As %String(MAXLEN = 60);
Property Explanation As %String(MAXLEN = 500);
Property ReviewerUsageJSON As %String(MAXLEN = "");
Property InvestigatorUsageJSON As %String(MAXLEN = "");
}
