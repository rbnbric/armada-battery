Include %occStatus

/// Routes an evidence case through a binary AI Hub review and, when needed,
/// a larger AI Hub investigation. It never dispatches the business effect.
Class Battery.Interop.CaseProcess Extends Ens.BusinessProcess
{
Parameter AGENTTIMEOUT = 90;

Method OnRequest(pRequest As Battery.Interop.CaseRequest, Output pResponse As Battery.Interop.CaseResponse) As %Status
{
    Set pResponse = ##class(Battery.Interop.CaseResponse).%New()
    Set pResponse.State = "HELD_FOR_REVIEW"
    Try {
        If $LENGTH(pRequest.CaseJSON) > 65536 { Set pResponse.Explanation = "Case exceeds 65536 characters" Return $$$OK }
        If '..ParseObject(pRequest.CaseJSON, .case, .detail) { Set pResponse.Explanation = "Invalid case: " _ detail Return $$$OK }
        If '..ValidCase(case) {
            Set pResponse.Explanation = "Case failed field, type, or size validation"
            Return $$$OK
        }
        Set pResponse.CaseId = case.%Get("id")
        Set facts = case.%Get("facts")
        Set reviewRequest = ##class(Battery.Interop.AgentRequest).%New()
        Set reviewRequest.Role = "reviewer"
        Set reviewRequest.CaseJSON = pRequest.CaseJSON
        Set sc = ..SendRequestSync("Battery.Agent", reviewRequest, .reviewResponse, ..#AGENTTIMEOUT)
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
        Set sc = ..SendRequestSync("Battery.Agent", investigateRequest, .investigateResponse, ..#AGENTTIMEOUT)
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

/// Reject malformed inputs before a provider call or persistent case identifier.
ClassMethod ValidCase(case As %DynamicObject) As %Boolean
{
    If '$IsObject(case) { Return 0 }
    If ('case.%IsA("%DynamicObject")) || (case.%Size() '= 6) { Return 0 }
    If '..ValidText(case, "id", 120) { Return 0 }
    For key="rule","expected","acceptance","observed" {
        If '..ValidText(case, key, 4096) { Return 0 }
    }
    If case.%GetTypeOf("facts") '= "object" { Return 0 }
    Set facts = case.%Get("facts")
    If (facts.%Size() = 0) || (facts.%Size() > 64) { Return 0 }
    Set iter = facts.%GetIterator()
    While iter.%GetNext(.key, .value) {
        If ($ZSTRIP(key, "<>W") = "") || ($LENGTH(key) > 80) { Return 0 }
        If '..ValidText(facts, key, 4096) { Return 0 }
    }
    Return 1
}

ClassMethod ValidText(obj As %DynamicObject, key As %String, limit As %Integer) As %Boolean
{
    If obj.%GetTypeOf(key) '= "string" { Return 0 }
    Set value = obj.%Get(key)
    Return ($ZSTRIP(value, "<>W") '= "") && ($LENGTH(value) <= limit)
}

/// Accept a JSON object, optionally enclosed in one complete Markdown fence.
/// Never extract a convenient fragment from prose or repair invented fields.
ClassMethod ParseObject(text As %String, Output parsed As %DynamicObject, Output detail As %String) As %Boolean
{
    Set parsed = "", detail = ""
    Try {
        If $LENGTH(text) > 65536 { Set detail = "JSON exceeds 65536 characters" Return 0 }
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
    If review.%Size() '= 5 { Return 0 }
    Set verdict = review.%Get("verdict")
    Set applicability = review.%Get("applicability")
    Set outputResult = review.%Get("output_result")
    If (verdict '= "YES") && (verdict '= "NO") { Return 0 }
    If (applicability '= "APPLICABLE") && (applicability '= "INAPPLICABLE") && (applicability '= "UNKNOWN") { Return 0 }
    If (outputResult '= "PASS") && (outputResult '= "FAIL") && (outputResult '= "UNKNOWN") { Return 0 }
    If (verdict = "YES") && (applicability '= "APPLICABLE") { Return 0 }
    If '..ValidText(review, "summary", 300) { Return 0 }
    Return ..ValidEvidence(review.%Get("evidence_ids"), facts)
}

ClassMethod ValidInvestigation(investigation As %DynamicObject, facts As %DynamicObject) As %Boolean
{
    If ('$IsObject(investigation)) || ('$IsObject(facts)) { Return 0 }
    If ('investigation.%IsA("%DynamicObject")) || ('facts.%IsA("%DynamicObject")) { Return 0 }
    If investigation.%Size() '= 4 { Return 0 }
    Set probe = investigation.%Get("next_probe")
    If (probe '= "CHECK_TARGET_VERSION") && (probe '= "CHECK_EFFECT_RECEIPT") && (probe '= "CHECK_PARTNER_SCOPE") && (probe '= "CHECK_MAPPING") && (probe '= "CHECK_RULE_SELECTION") && (probe '= "CHECK_FRESH_READBACK") && (probe '= "HOLD_FOR_HUMAN") { Return 0 }
    If '..ValidText(investigation, "hypothesis", 300) { Return 0 }
    If '..ValidText(investigation, "uncertainty", 200) { Return 0 }
    Return ..ValidEvidence(investigation.%Get("evidence_ids"), facts)
}

ClassMethod ValidEvidence(ids As %DynamicArray, facts As %DynamicObject) As %Boolean
{
    If ('$IsObject(ids)) || ('$IsObject(facts)) { Return 0 }
    If ('ids.%IsA("%DynamicArray")) || ('facts.%IsA("%DynamicObject")) || (ids.%Size() = 0) || (ids.%Size() > 16) { Return 0 }
    Set seen = ##class(%DynamicObject).%New()
    For i=0:1:(ids.%Size()-1) {
        If ids.%GetTypeOf(i) '= "string" { Return 0 }
        Set id = ids.%Get(i)
        If (id = "") || ('..ValidText(facts, id, 4096)) || seen.%IsDefined(id) { Return 0 }
        Do seen.%Set(id, 1)
    }
    Return 1
}
}
