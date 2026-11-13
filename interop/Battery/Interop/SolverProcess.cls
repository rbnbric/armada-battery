Include %occStatus

/// Bounded orchestration: review -> one read-only probe -> one follow-up -> fresh proof.
/// Raw model answers remain separate from the deterministic measurement verdict.
Class Battery.Interop.SolverProcess Extends Ens.BusinessProcess
{
Parameter REVIEWTIMEOUT = 200;
Method OnRequest(pRequest As Battery.Interop.CaseRequest, Output pResponse As Battery.Interop.CaseResponse) As %Status
{
    If pRequest.RunId'="" {
        Set pRequest.Lease=##class(Battery.Interop.CaseRecord).Begin(pRequest.RunId)
        If pRequest.Lease="" { Return $$$OK }
    }
    Set sc=..Solve(pRequest,.pResponse)
    If pRequest.RunId'="" {
        If $IsObject(pResponse) {
            Set saved=##class(Battery.Interop.CaseRecord).Complete(pRequest.RunId,pResponse,pRequest.Lease)
            If $$$ISERR(saved) { Return saved }
        }
    }
    Return sc
}
Method Solve(pRequest As Battery.Interop.CaseRequest, Output pResponse As Battery.Interop.CaseResponse) As %Status
{
    Set pResponse=##class(Battery.Interop.CaseResponse).%New()
    Set pResponse.ReasonCode="TECHNICAL_RECOVERY"
    Set pResponse.State="HELD_FOR_REVIEW",pResponse.GateVerdict="NO",pResponse.GateOutput="UNKNOWN"
    Set history=[],reads=[]
    Try {
        If '##class(Battery.Interop.CaseProcess).ParseObject(pRequest.CaseJSON,.case,.detail) { Set pResponse.Explanation="Invalid input JSON" Return $$$OK }
        If '##class(Battery.Interop.CaseProcess).ValidCase(case) { Set pResponse.Explanation="Invalid input fields" Return $$$OK }
        Set pResponse.CaseId=case.id
        Set er=##class(Battery.Interop.EvidenceRequest).%New()
        Set er.CaseId=case.id,er.CaseJSON=pRequest.CaseJSON,er.Phase="INITIAL"
        If '##class(Battery.Interop.CaseRecord).Current(pRequest.RunId,pRequest.Lease) { Set pResponse.Explanation="Case lease expired; no further work dispatched" Return $$$OK }
        Set sc=..SendRequestSync("Battery.Evidence",er,.initial,10)
        If $$$ISERR(sc) { Set pResponse.Explanation="Initial evidence read failed" Return $$$OK }
        If '$IsObject(initial) { Set pResponse.Explanation="Initial evidence read returned no response" Return $$$OK }
        Do ..RecordRead(reads,er.Phase,initial)
        If 'initial.Found { Set pResponse.ReasonCode="EVIDENCE_NEEDED",pResponse.State="HELD_FOR_EVIDENCE",pResponse.Explanation=initial.Reason,pResponse.ProbeHistoryJSON=reads.%ToJSON() Return $$$OK }
        If '##class(Battery.Interop.OutcomeProof).Contract(initial.ContractJSON,.contract) { Set pResponse.Explanation="Invalid adapter measurement contract",pResponse.ProbeHistoryJSON=reads.%ToJSON() Return $$$OK }
        Set proof=##class(Battery.Interop.OutcomeProof).Assess(initial.ContractJSON,initial.ObservationJSON)
        Set enriched=..Enrich(case,initial.ContractJSON,initial.ObservationJSON)
        Set rr=##class(Battery.Interop.CaseRequest).%New(),rr.CaseJSON=enriched,rr.RunId=pRequest.RunId,rr.Lease=pRequest.Lease
        If '##class(Battery.Interop.CaseRecord).Current(pRequest.RunId,pRequest.Lease) { Set pResponse.Explanation="Case lease expired; no further work dispatched" Return $$$OK }
        Set sc=..SendRequestSync("Battery.Review",rr,.review,..#REVIEWTIMEOUT)
        If $$$ISERR(sc) { Set pResponse.Explanation="Initial review failed" Return $$$OK }
        If '$IsObject(review) { Set pResponse.Explanation="Initial review returned no response" Return $$$OK }
        Do ..RecordReview(history,review),..CopyReview(pResponse,review)
        Set pResponse.ReviewHistoryJSON=history.%ToJSON(),pResponse.ProbeHistoryJSON=reads.%ToJSON()
        If (review.State="HELD_FOR_REVIEW")&&(review.ReviewerVerdict="") { Set pResponse.Explanation="Initial model review held: "_review.Explanation Return $$$OK }
        // A failed investigator cannot block a predefined read-only probe after a valid reviewer.
        // Preserve the failure in history; no model text is executed.
        Set selected=initial
        If (proof.verdict'="YES")||(proof.output'="PASS")||(review.State'="AGREED_PENDING_GATE") {
            // A receipt profile has a defined next observation. Never execute arbitrary model text.
            // Each send owns its message body; reusing one rewrites earlier Visual Trace entries.
            Set er=##class(Battery.Interop.EvidenceRequest).%New(),er.CaseId=case.id,er.CaseJSON=pRequest.CaseJSON
            Set er.Phase=$SELECT(proof.reason="Observation expired":"CHECK_FRESH_READBACK",1:"CHECK_EFFECT_RECEIPT")
            If pRequest.RunId'="" {
                Set proposed=review.InvestigatorProbe
                If proposed="HOLD_FOR_HUMAN" { Set pResponse.ReasonCode="CONTEXT_DECISION",pResponse.Explanation="Investigator requested human review; no probe executed" Return $$$OK }
                If proposed'="" {
                    If (proposed'="CHECK_EFFECT_RECEIPT")&&(proposed'="CHECK_TARGET_VERSION")&&(proposed'="CHECK_FRESH_READBACK") { Set pResponse.Explanation="Proposed probe is unavailable in this adapter: "_proposed Return $$$OK }
                    Set er.Phase=proposed
                }
            }
            Set pResponse.ExecutedProbe=er.Phase
            If '##class(Battery.Interop.CaseRecord).Current(pRequest.RunId,pRequest.Lease) { Set pResponse.Explanation="Case lease expired; no further work dispatched" Return $$$OK }
            Set sc=..SendRequestSync("Battery.Evidence",er,.probed,10)
            If $$$ISERR(sc) { Set pResponse.Explanation="Evidence probe failed" Return $$$OK }
            If '$IsObject(probed) { Set pResponse.Explanation="Evidence probe returned no response" Return $$$OK }
            Do ..RecordRead(reads,er.Phase,probed)
            Set pResponse.ProbeHistoryJSON=reads.%ToJSON()
            If ('probed.Found)||(probed.ContractJSON'=initial.ContractJSON) { Set pResponse.Explanation="Case or contract changed during probe" Return $$$OK }
            Set selected=probed
            Set proof=##class(Battery.Interop.OutcomeProof).Assess(probed.ContractJSON,probed.ObservationJSON)
            If proof.usable&&(probed.ObservationJSON'=initial.ObservationJSON) {
                Set rr=##class(Battery.Interop.CaseRequest).%New(),rr.RunId=pRequest.RunId,rr.Lease=pRequest.Lease
                Set rr.CaseJSON=..Enrich(case,probed.ContractJSON,probed.ObservationJSON)
                If '##class(Battery.Interop.CaseRecord).Current(pRequest.RunId,pRequest.Lease) { Set pResponse.Explanation="Case lease expired; no further work dispatched" Return $$$OK }
                Set sc=..SendRequestSync("Battery.Review",rr,.followup,..#REVIEWTIMEOUT)
                If $$$ISERR(sc) { Set pResponse.Explanation="Follow-up review failed" Return $$$OK }
                If '$IsObject(followup) { Set pResponse.Explanation="Follow-up review returned no response" Return $$$OK }
                Do ..RecordReview(history,followup),..CopyReview(pResponse,followup)
                Set pResponse.ReviewHistoryJSON=history.%ToJSON()
                If (followup.State="HELD_FOR_REVIEW")&&(followup.ReviewerVerdict="") { Set pResponse.Explanation="Follow-up model review held: "_followup.Explanation Return $$$OK }
            }
        }
        Set er=##class(Battery.Interop.EvidenceRequest).%New(),er.CaseId=case.id,er.CaseJSON=pRequest.CaseJSON,er.Phase="FINAL"
        If '##class(Battery.Interop.CaseRecord).Current(pRequest.RunId,pRequest.Lease) { Set pResponse.Explanation="Case lease expired; no further work dispatched" Return $$$OK }
        Set sc=..SendRequestSync("Battery.Evidence",er,.fresh,10)
        If $$$ISERR(sc) { Set pResponse.Explanation="Final evidence read failed" Return $$$OK }
        If '$IsObject(fresh) { Set pResponse.Explanation="Final evidence read returned no response" Return $$$OK }
        Do ..RecordRead(reads,er.Phase,fresh)
        Set pResponse.ProbeHistoryJSON=reads.%ToJSON()
        If ('fresh.Found)||(fresh.ContractJSON'=initial.ContractJSON)||(fresh.ObservationJSON'=selected.ObservationJSON) { Set pResponse.ReasonCode="EVIDENCE_NEEDED",pResponse.Explanation="Evidence changed after reasoning; resubmit against new snapshot" Return $$$OK }
        Set proof=##class(Battery.Interop.OutcomeProof).Assess(fresh.ContractJSON,fresh.ObservationJSON)
        Set pResponse.ProofJSON=proof.%ToJSON(),pResponse.GateVerdict=proof.verdict,pResponse.GateOutput=proof.output
        Set pResponse.Explanation=proof.reason
        If 'proof.usable { Set pResponse.ReasonCode="EVIDENCE_NEEDED",pResponse.State="HELD_FOR_EVIDENCE" Return $$$OK }
        Set pResponse.State=$SELECT((proof.verdict="YES")&&(proof.output="PASS"):"VERIFIED_MATCH",1:"VERIFIED_MISMATCH")
        Set pResponse.ReasonCode=$SELECT(pResponse.State="VERIFIED_MATCH":"COMPLETE",1:"CONTEXT_DECISION")
        // Verified means this bounded measurement only. This process performs no business mutation.
        Return $$$OK
    } Catch ex {
        Set pResponse.State="HELD_FOR_REVIEW",pResponse.Explanation="Solver error: "_$SYSTEM.Status.GetErrorText(ex.AsStatus())
        Set pResponse.ReviewHistoryJSON=history.%ToJSON(),pResponse.ProbeHistoryJSON=reads.%ToJSON()
        Return $$$OK
    }
}
ClassMethod Enrich(case As %DynamicObject, contract As %String, observation As %String) As %String
{
    Set copy=##class(%DynamicObject).%FromJSON(case.%ToJSON())
    // Replace untrusted free-form descriptions with the bound profile for this internal review.
    Do copy.%Set("id","receipt-review")
    Set c=##class(%DynamicObject).%FromJSON(contract)
    Do copy.%Set("rule","Selected rule is applicable when B_CONTRACT.version equals B_CONTRACT.rule_version. YES additionally requires an available, fresh B_OBSERVATION matching B_CONTRACT.partner, attempt, target and version exactly, plus expected_count and expected_result. Missing or mismatched evidence cannot verify the assertion: NO.")
    Do copy.%Set("expected","For the exact partner/attempt/target/version in B_CONTRACT, the selected rule predicts expected_count and expected_result. A receipt for a different scope does not support this prediction.")
    Do copy.%Set("acceptance","Grade independently of rule_version. First require available=true, exact partner/attempt/target/version matches, and 0 <= B_EVALUATED_AT minus observed_at < max_age. Otherwise UNKNOWN. With valid correlated evidence, compare count/result against accepted_count/accepted_result: both equal means PASS, either differs means FAIL. An inapplicable rule does not invalidate a valid observed outcome.")
    Do copy.%Set("observed",observation)
    // All original facts remain stored in the input trace; only adapter-bound facts enter this profile.
    Set facts={"B_CONTRACT":(contract),"B_OBSERVATION":(observation),"B_EVALUATED_AT":(""_##class(Battery.Interop.OutcomeProof).Now())}
    Set binding=##class(Battery.Interop.EvidenceBinding).%OpenId(case.id)
    If $IsObject(binding) {
        If binding.Adapter="management" { Do facts.%Set("B_TOOLS","CHECK_EFFECT_RECEIPT reads the scoped durable operation receipt; CHECK_TARGET_VERSION reads current target configuration through the management adapter; CHECK_FRESH_READBACK reads both. All are read-only. HOLD_FOR_HUMAN stops. Other probes are unavailable. count denotes correlated verified receipt records, not a physical effect count. Source may be synthetic; retain that scope.") }
    }
    Do copy.%Set("facts",facts)
    Return copy.%ToJSON()
}
ClassMethod RecordRead(list As %DynamicArray, phase As %String, r As Battery.Interop.EvidenceResponse)
{
    Do list.%Push({"phase":(phase),"found":(r.Found),"contract":(r.ContractJSON),"observation":(r.ObservationJSON),"reason":(r.Reason),"tool":(r.ToolJSON)})
}
ClassMethod RecordReview(list As %DynamicArray, r As Battery.Interop.CaseResponse)
{
    Do list.%Push({"state":(r.State),"verdict":(r.ReviewerVerdict),"output":(r.OutputResult),"applicability":(r.ReviewerApplicability),"probe":(r.InvestigatorProbe),"explanation":(r.Explanation),"reviewer_usage":(r.ReviewerUsageJSON),"investigator_usage":(r.InvestigatorUsageJSON),"agent_calls":(r.AgentCallsJSON)})
}
ClassMethod CopyReview(out As Battery.Interop.CaseResponse, r As Battery.Interop.CaseResponse)
{
    Set out.ReviewerVerdict=r.ReviewerVerdict,out.OutputResult=r.OutputResult,out.ReviewerApplicability=r.ReviewerApplicability
    If r.InvestigatorProbe'="" { Set out.InvestigatorProbe=r.InvestigatorProbe }
    Set out.ReviewerUsageJSON=r.ReviewerUsageJSON,out.InvestigatorUsageJSON=r.InvestigatorUsageJSON
}
}
