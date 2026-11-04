Include %occStatus

/// Runs fault injection through the native Service -> Process -> Operation path.
/// Always restores the real production; synthetic provider errors are labelled.
Class Battery.Test.FaultSuite Extends %RegisteredObject
{
ClassMethod Run() As %Status
{
    Set result=$$$OK
    Try {
        Set sc=##class(Ens.Director).StopProduction()
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set sc=##class(Ens.Director).StartProduction("Battery.Test.FaultProduction")
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        For mode="agree","yes_fail","no_pass","unknown" {
            Set wanted=$SELECT(mode="agree":"AGREED_PENDING_GATE",1:"INVESTIGATION_PENDING_GATE")
            Do ..Check(mode,"",wanted,1,$SELECT(mode="agree":0,1:1))
        }
        For mode="reviewer_error","reviewer_noresponse","reviewer_empty","reviewer_malformed","reviewer_array","reviewer_fabricated","reviewer_extra","reviewer_timeout" {
            Do ..Check(mode,"","HELD_FOR_REVIEW",1,0)
        }
        For mode="investigator_error","investigator_noresponse","investigator_empty","investigator_malformed","investigator_array","investigator_fabricated","investigator_extra","investigator_probe","investigator_timeout" {
            Do ..Check(mode,"","HELD_FOR_REVIEW",1,1)
        }
        Do ..Check("invalid_case","{","HELD_FOR_REVIEW",0,0)
        Do ..Check("oversize_case",$JUSTIFY("",65537),"HELD_FOR_REVIEW",0,0)
        Do ..Check("bad_case_types","{""id"":17}","HELD_FOR_REVIEW",0,0)
        Do ..Check("agree","","AGREED_PENDING_GATE",1,0)
        Set sc=##class(Ens.Director).StopProduction()
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set sc=##class(Ens.Director).StartProduction("Battery.Test.FaultProduction")
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Do ..Check("agree","","AGREED_PENDING_GATE",1,0)
    } Catch ex {
        Set result=ex.AsStatus()
        Write "FAULT_SUITE_ERROR=",$SYSTEM.Status.GetErrorText(result),!
    }
    Set sc=##class(Ens.Director).StopProduction()
    If $$$ISERR(sc) { Return sc }
    Set sc=##class(Ens.Director).StartProduction("Battery.Interop.Production")
    If $$$ISERR(sc) { Return sc }
    Write !,"FAULT_PRODUCTION_RESTORED",!
    Return result
}

ClassMethod Check(mode As %String, raw As %String, wanted As %String, reviewCalls As %Integer, investigateCalls As %Integer)
{
    Kill ^BatteryFault
    Set ^BatteryFault("mode")=mode
    Set request=##class(Battery.Interop.CaseRequest).%New()
    Set case={"id":("fault-"_mode),"rule":"A verified receipt is required","expected":"held","acceptance":"Held without receipt","observed":"marked complete without receipt","facts":{"F1":"No verified receipt exists"}}
    Set request.CaseJSON=$SELECT(raw="":case.%ToJSON(),1:raw)
    Set sc=##class(Ens.Director).CreateBusinessService("Battery.Intake",.service)
    If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
    Set sc=service.ProcessInput(request,.response)
    Set state="NO_RESPONSE",explanation="",handoffOK=1,lateStable=1
    If $IsObject(response) { Set state=response.State,explanation=response.Explanation }
    If mode [ "_timeout" {
        Set lateStable=0
        If $IsObject(response) {
            Set responseId=response.%Id()
            Hang 3
            Set saved=##class(Battery.Interop.CaseResponse).%OpenId(responseId)
            If $IsObject(saved) { Set lateStable=(saved.State="HELD_FOR_REVIEW") }
        }
    }
    If investigateCalls {
        Set handoffOK=0
        If ($Get(^BatteryFault("request","investigator"))'="")&&$IsObject(response) {
            Set handoff=##class(%DynamicObject).%FromJSON(^BatteryFault("request","investigator"))
            Set handoffOK=(handoff.case.id=case.id)&&(handoff.review.verdict=response.ReviewerVerdict)
        }
    }
    Set rc=$Get(^BatteryFault("calls","reviewer"),0),ic=$Get(^BatteryFault("calls","investigator"),0)
    Set passed=($$$ISOK(sc))&&(state=wanted)&&(rc=reviewCalls)&&(ic=investigateCalls)&&handoffOK&&lateStable&&(explanation'="")
    Set row={"mode":(mode),"passed":(passed),"state":(state),"expected_state":(wanted),"reviewer_calls":(rc),"investigator_calls":(ic),"handoff_preserved":(handoffOK),"late_response_kept_hold":(lateStable),"explanation":(explanation)}
    Write !,"FAULT_CASE=",row.%ToJSON(),!
}
}
