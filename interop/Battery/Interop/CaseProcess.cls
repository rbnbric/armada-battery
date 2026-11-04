Include %occStatus

/// Routes an evidence case through a binary AI Hub review and, when needed,
/// a larger AI Hub investigation. It never dispatches the business effect.
Class Battery.Interop.CaseProcess Extends Ens.BusinessProcess
{
Method OnRequest(pRequest As Battery.Interop.CaseRequest, Output pResponse As Battery.Interop.CaseResponse) As %Status
{
    Set pResponse = ##class(Battery.Interop.CaseResponse).%New()
    Set pResponse.State = "HELD_FOR_REVIEW"
    Try {
        If '..ParseObject(pRequest.CaseJSON, .case, .detail) { Set pResponse.Explanation = "Invalid case: " _ detail Return $$$OK }
        Set pResponse.CaseId = case.%Get("id")
        Set facts = case.%Get("facts")
        If (pResponse.CaseId = "") || ('$IsObject(facts)) || (case.%Get("rule") = "") || (case.%Get("expected") = "") || (case.%Get("acceptance") = "") || (case.%Get("observed") = "") {
            Set pResponse.Explanation = "Case lacks id, rule, expected, acceptance, observed, or facts"
            Return $$$OK
        }
        Set reviewRequest = ##class(Battery.Interop.AgentRequest).%New()
        Set reviewRequest.Role = "reviewer"
        Set reviewRequest.CaseJSON = pRequest.CaseJSON
        Set sc = ..SendRequestSync("Battery.Agent", reviewRequest, .reviewResponse, 90)
        If $$$ISERR(sc) { Set pResponse.Explanation = "Reviewer call failed" Return $$$OK }
        If '$IsObject(reviewResponse) { Set pResponse.Explanation = "Reviewer returned no response" Return $$$OK }
        Set pResponse.ReviewerUsageJSON = reviewResponse.UsageJSON
        If '..ParseObject(reviewResponse.Content, .review, .detail) { Set pResponse.Explanation = "Invalid reviewer JSON: " _ detail Return $$$OK }
        If '..ValidReview(review, facts) { Set pResponse.Explanation = "Reviewer output failed contract validation" Return $$$OK }
        Set pResponse.ReviewerVerdict = review.%Get("verdict")
        Set pResponse.ReviewerApplicability = review.%Get("applicability")
        Set pResponse.OutputResult = review.%Get("output_result")
        Set pResponse.ReviewerUsageJSON = reviewResponse.UsageJSON
        Set pResponse.Explanation = review.%Get("summary")
        If (pResponse.ReviewerVerdict = "YES") && (pResponse.OutputResult = "PASS") {
            Set pResponse.State = "AGREED_PENDING_GATE"
            Return $$$OK
        }
        Set investigateRequest = ##class(Battery.Interop.AgentRequest).%New()
        Set investigateRequest.Role = "investigator"
        Set handoff = ##class(%DynamicObject).%New()
        Do handoff.%Set("case", case)
        Do handoff.%Set("review", review)
        Set investigateRequest.CaseJSON = handoff.%ToJSON()
        Set sc = ..SendRequestSync("Battery.Agent", investigateRequest, .investigateResponse, 90)
        If $$$ISERR(sc) { Set pResponse.Explanation = "Investigator call failed after escalation" Return $$$OK }
        If '$IsObject(investigateResponse) { Set pResponse.Explanation = "Investigator returned no response" Return $$$OK }
        Set pResponse.InvestigatorUsageJSON = investigateResponse.UsageJSON
        If '..ParseObject(investigateResponse.Content, .investigation, .detail) { Set pResponse.Explanation = "Invalid investigator JSON: " _ detail Return $$$OK }
        If '..ValidInvestigation(investigation, facts) { Set pResponse.Explanation = "Investigator output failed contract validation" Return $$$OK }
        Set pResponse.InvestigatorProbe = investigation.%Get("next_probe")
        Set pResponse.InvestigatorUsageJSON = investigateResponse.UsageJSON
        Set pResponse.Explanation = investigation.%Get("hypothesis")
        Set pResponse.State = "INVESTIGATION_PENDING_GATE"
        Return $$$OK
    } Catch ex {
        Set pResponse.Explanation = "Case held: " _ $SYSTEM.Status.GetErrorText(ex.AsStatus())
        Return $$$OK
    }
}

/// Accept a JSON object, optionally enclosed in one complete Markdown fence.
/// Never extract a convenient fragment from prose or repair invented fields.
ClassMethod ParseObject(text As %String, Output parsed As %DynamicObject, Output detail As %String) As %Boolean
{
    Set parsed = "", detail = ""
    Try {
        Set text = $ZSTRIP(text, "<>W")
        If ($EXTRACT(text, 1, 7) = "```json") && ($EXTRACT(text, *-2, *) = "```") {
            Set text = $ZSTRIP($EXTRACT(text, 8, *-3), "<>W")
        } ElseIf ($EXTRACT(text, 1, 3) = "```") && ($EXTRACT(text, *-2, *) = "```") {
            Set text = $ZSTRIP($EXTRACT(text, 4, *-3), "<>W")
        }
        Set parsed = ##class(%DynamicObject).%FromJSON(text)
        If '$IsObject(parsed) { Set detail = "Expected a JSON object" Return 0 }
        If 'parsed.%IsA("%DynamicObject") { Set detail = "Expected a JSON object" Return 0 }
        Return 1
    } Catch ex {
        Set detail = $SYSTEM.Status.GetErrorText(ex.AsStatus())
        Return 0
    }
}

/// Validate the answer before using even its non-effecting review state.
ClassMethod ValidReview(review As %DynamicObject, facts As %DynamicObject) As %Boolean
{
    If ('$IsObject(review)) || ('$IsObject(facts)) { Return 0 }
    If ('review.%IsA("%DynamicObject")) || ('facts.%IsA("%DynamicObject")) { Return 0 }
    Set verdict = review.%Get("verdict")
    Set applicability = review.%Get("applicability")
    Set outputResult = review.%Get("output_result")
    If (verdict '= "YES") && (verdict '= "NO") { Return 0 }
    If (applicability '= "APPLICABLE") && (applicability '= "INAPPLICABLE") && (applicability '= "UNKNOWN") { Return 0 }
    If (outputResult '= "PASS") && (outputResult '= "FAIL") && (outputResult '= "UNKNOWN") { Return 0 }
    If (verdict = "YES") && (applicability '= "APPLICABLE") { Return 0 }
    If (review.%Get("summary") = "") || ($LENGTH(review.%Get("summary")) > 300) { Return 0 }
    Return ..ValidEvidence(review.%Get("evidence_ids"), facts)
}

ClassMethod ValidInvestigation(investigation As %DynamicObject, facts As %DynamicObject) As %Boolean
{
    If ('$IsObject(investigation)) || ('$IsObject(facts)) { Return 0 }
    If ('investigation.%IsA("%DynamicObject")) || ('facts.%IsA("%DynamicObject")) { Return 0 }
    Set probe = investigation.%Get("next_probe")
    If (probe '= "CHECK_TARGET_VERSION") && (probe '= "CHECK_EFFECT_RECEIPT") && (probe '= "CHECK_PARTNER_SCOPE") && (probe '= "CHECK_MAPPING") && (probe '= "CHECK_RULE_SELECTION") && (probe '= "CHECK_FRESH_READBACK") && (probe '= "HOLD_FOR_HUMAN") { Return 0 }
    If (investigation.%Get("hypothesis") = "") || ($LENGTH(investigation.%Get("hypothesis")) > 300) { Return 0 }
    If (investigation.%Get("uncertainty") = "") || ($LENGTH(investigation.%Get("uncertainty")) > 200) { Return 0 }
    Return ..ValidEvidence(investigation.%Get("evidence_ids"), facts)
}

ClassMethod ValidEvidence(ids As %DynamicArray, facts As %DynamicObject) As %Boolean
{
    If '$IsObject(ids) { Return 0 }
    If ('ids.%IsA("%DynamicArray")) || (ids.%Size() = 0) { Return 0 }
    For i=0:1:(ids.%Size()-1) {
        If ids.%GetTypeOf(i) '= "string" { Return 0 }
        Set id = ids.%Get(i)
        If (id = "") || (facts.%Get(id) = "") { Return 0 }
    }
    Return 1
}
}
