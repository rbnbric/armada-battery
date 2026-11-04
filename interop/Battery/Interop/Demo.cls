Include %occStatus

/// Two source-bound cases for an operator to run through the live production.
Class Battery.Interop.Demo Extends %RegisteredObject
{
ClassMethod Start() As %Status
{
    Return ##class(Ens.Director).StartProduction("Battery.Interop.Production")
}

ClassMethod Run(which As %String = "match") As %Status
{
    Set case = ##class(%DynamicObject).%New()
    Set facts = ##class(%DynamicObject).%New()
    If which = "match" {
        Do case.%Set("id", "demo-alias-match")
        Do case.%Set("rule", "For partner A schema v2, copy clientId to customerId; accept when target validation confirms the value.")
        Do case.%Set("expected", "target accepted customerId=C17")
        Do case.%Set("acceptance", "Target accepts the customer value under its active contract.")
        Do case.%Set("observed", "target accepted customerId=C17")
        Do facts.%Set("A1", "Partner A contract v2 maps clientId to customerId.")
        Do facts.%Set("A2", "Saved target validation accepted customerId=C17.")
    } ElseIf which = "drift" {
        Do case.%Set("id", "demo-schema-drift")
        Do case.%Set("rule", "For partner A schema v2, copy clientId to customerId; accept when target validation confirms the value.")
        Do case.%Set("expected", "target accepted customerId=C17")
        Do case.%Set("acceptance", "Target accepts the customer value under its active contract.")
        Do case.%Set("observed", "target rejected unknown field customerId")
        Do facts.%Set("B1", "Partner A mapping still declares schema v2.")
        Do facts.%Set("B2", "Target reports active schema v3, where customerRef replaces customerId.")
        Do facts.%Set("B3", "Saved target validation rejected customerId.")
    } ElseIf which = "wrongrule" {
        Do case.%Set("id", "demo-wrong-rule-good-output")
        Do case.%Set("rule", "Reject a v2 message without orderId.")
        Do case.%Set("expected", "rejected: orderId required")
        Do case.%Set("acceptance", "A v2 message with orderId is accepted.")
        Do case.%Set("observed", "accepted")
        Do facts.%Set("D1", "Input includes orderId=O19.")
        Do facts.%Set("D2", "Validation receipt says accepted.")
    } ElseIf which = "badoutput" {
        Do case.%Set("id", "demo-good-rule-bad-output")
        Do case.%Set("rule", "For partner A schema v2, a valid customerId is accepted by target validation.")
        Do case.%Set("expected", "target accepted customerId=C17")
        Do case.%Set("acceptance", "The request creates at most one external effect for the same scoped key.")
        Do case.%Set("observed", "target accepted customerId=C17; two outbound effects recorded")
        Do facts.%Set("A3", "Partner A schema v2 requires customerId, and target validation accepted C17.")
        Do facts.%Set("A4", "Effect ledger records two outbound effects for Partner A/key K17.")
    } Else {
        Return $$$ERROR($$$GeneralError, "Unknown demo case")
    }
    Do case.%Set("facts", facts)
    Set request = ##class(Battery.Interop.CaseRequest).%New()
    Set request.CaseJSON = case.%ToJSON()
    Set sc = ##class(Ens.Director).CreateBusinessService("Battery.Intake", .service)
    If $$$ISERR(sc) { Return sc }
    Set sc = service.ProcessInput(request, .response)
    If $$$ISERR(sc) { Return sc }
    If '$IsObject(response) { Return $$$ERROR($$$GeneralError, "No case response") }
    Write "case=", response.CaseId, " state=", response.State, " assertion=", response.ReviewerVerdict, " output=", response.OutputResult, " applicability=", response.ReviewerApplicability, " probe=", response.InvestigatorProbe, !
    Write "explanation=", response.Explanation, !
    Return $$$OK
}
}
