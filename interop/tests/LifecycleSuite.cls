Include %occStatus
/// Real database lifecycle tests; fixtures never dispatch a model or business effect.
Class Battery.Test.LifecycleSuite Extends %RegisteredObject
{
ClassMethod Assert(ok As %Boolean, name As %String)
{
    Write "LIFECYCLE_CASE=",{"name":(name),"passed":(ok)}.%ToJSON(),!
    If 'ok { Throw ##class(%Exception.General).%New("Lifecycle failed: "_name) }
}
ClassMethod Fixture(id As %String, owner As %String="lifecycle-test", operator As %String="alice") As Battery.Interop.CaseRecord
{
    Set r=##class(Battery.Interop.CaseRecord).%New(),r.CaseId=id,r.Owner=owner,r.Operator=operator,r.State="QUEUED",r.Deadline=##class(Battery.Interop.OutcomeProof).Now()+120,r.CreatedAt=$ZDATETIME($HOROLOG,3,1),r.UpdatedAt=r.CreatedAt,r.RequestJSON="{}"
    Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
    Set ^BatteryCaseActive(id)=1
    Return r
}
ClassMethod Run() As %Status
{
    Set prefix="lifecycle-"_$SYSTEM.Util.CreateGUID(),sc=$$$OK
    Try {
        Set a=..Fixture(prefix_"-a"),b=..Fixture(prefix_"-b")
        Do ..Assert('##class(Battery.Interop.CaseRecord).Capacity("lifecycle-test","alice"),"two active cases exhaust operator slots")
        Do ..Assert(##class(Battery.Interop.CaseRecord).Capacity("lifecycle-test","bob"),"different operator retains capacity")
        Set token=##class(Battery.Interop.CaseRecord).Begin(a.CaseId)
        Do ..Assert(token'="","queued case receives lease")
        Do ..Assert(##class(Battery.Interop.CaseRecord).Begin(a.CaseId)="","duplicate delivery cannot claim running case")
        Do ..Assert(##class(Battery.Interop.CaseRecord).Current(a.CaseId,token),"valid lease accepted")
        Do ..Assert('##class(Battery.Interop.CaseRecord).Current(a.CaseId,"forged"),"foreign lease denied")
        Set a=##class(Battery.Interop.CaseRecord).%OpenId(a.CaseId),a.Deadline=##class(Battery.Interop.OutcomeProof).Now()-1
        Set saved=a.%Save()
        Set response=##class(Battery.Interop.CaseResponse).%New(),response.State="VERIFIED_MATCH"
        Set late=##class(Battery.Interop.CaseRecord).Complete(a.CaseId,response,token)
        Do ..Assert($$$ISERR(late),"late successful completion rejected")
        Set a=##class(Battery.Interop.CaseRecord).%OpenId(a.CaseId)
        Do ..Assert((a.State="RECOVERY_REQUIRED")&&(a.ResultJSON=""),"expired run remains held without fabricated result")
        Do ..Assert('##class(Battery.Interop.CaseRecord).Current(a.CaseId,token),"expired worker cannot dispatch further provider calls")
        Set b.Deadline=##class(Battery.Interop.OutcomeProof).Now()-1,saved=b.%Save()
        Set saved=##class(Battery.Interop.CaseRecord).Sweep()
        Set b=##class(Battery.Interop.CaseRecord).%OpenId(b.CaseId)
        Do ..Assert(b.State="RECOVERY_REQUIRED","queue gap recovers without replay")
        Do ..Assert(##class(Battery.Interop.CaseRecord).Begin(b.CaseId)="","delayed queued delivery denied")
        Do ..Assert(##class(Battery.Interop.CaseRecord).Capacity("lifecycle-test","alice"),"expiry returns operator slots")
        Set c=..Fixture(prefix_"-c"),token=##class(Battery.Interop.CaseRecord).Begin(c.CaseId)
        Set done=##class(Battery.Interop.CaseRecord).Complete(c.CaseId,response,token)
        Do ..Assert($$$ISOK(done),"current worker completes")
        Set c=##class(Battery.Interop.CaseRecord).%OpenId(c.CaseId)
        Do ..Assert((c.State="VERIFIED_MATCH")&&('$DATA(^BatteryCaseActive(c.CaseId))),"completion releases active slot")
        Set again=##class(Battery.Interop.CaseRecord).Complete(c.CaseId,response,token)
        Do ..Assert($$$ISERR(again),"duplicate completion cannot overwrite result")
        Set day=+$HOROLOG,prior=$Get(^BatteryCaseBudget(day,"lifecycle-test","alice"),0)
        Set ^BatteryCaseBudget(day,"lifecycle-test","alice")=20
        Do ..Assert('##class(Battery.Interop.CaseRecord).Capacity("lifecycle-test","alice"),"daily budget persists outside worker memory")
        Do ..Assert(##class(Battery.Interop.CaseRecord).Capacity("lifecycle-test","bob"),"daily operator budget does not block another operator")
        Set ^BatteryCaseBudget(day,"lifecycle-test","alice")=prior
    } Catch ex { Set sc=ex.AsStatus() Write "LIFECYCLE_ERROR=",$SYSTEM.Status.GetErrorText(sc),! }
    For suffix="-a","-b","-c" { Set id=prefix_suffix,saved=##class(Battery.Interop.CaseRecord).%DeleteId(id) Kill ^BatteryCaseActive(id) }
    If $DATA(prior) { Set ^BatteryCaseBudget(day,"lifecycle-test","alice")=prior }
    If $$$ISOK(sc) { Write "LIFECYCLE_FINISHED",! }
    Return sc
}
}
