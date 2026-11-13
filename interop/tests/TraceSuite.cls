Include %occStatus
/// Checks saved native message bodies after the whole workflow has completed.
Class Battery.Test.TraceSuite Extends %RegisteredObject
{
ClassMethod Run() As %Status
{
    Try {
        Set sc=##class(Ens.Director).StopProduction()
        If $$$ISERR(sc) { Return sc }
        Set sc=##class(Ens.Director).StartProduction("Battery.Test.SolverProduction")
        If $$$ISERR(sc) { Return sc }
        Set round=##class(Battery.Interop.OutcomeProof).Now(),id="solver4-fault-recovered-"_round
        Do ##class(Battery.Test.SolverSuite).Check("recovered",round,0)
        Set statement=##class(%SQL.Statement).%New()
        Set sc=statement.%Prepare("SELECT TOP 1 h.SessionId FROM Ens.MessageHeader h JOIN Battery_Interop.CaseResponse r ON h.MessageBodyId=r.ID WHERE h.MessageBodyClassName='Battery.Interop.CaseResponse' AND r.CaseId=? ORDER BY h.ID DESC")
        If $$$ISERR(sc) { Return sc }
        Set result=statement.%Execute(id)
        If result.%SQLCODE<0 { Return $$$ERROR($$$GeneralError,result.%Message) }
        If 'result.%Next() { Return $$$ERROR($$$GeneralError,"No trace session") }
        Set session=result.%Get("SessionId")
        Set statement=##class(%SQL.Statement).%New()
        Set sc=statement.%Prepare("SELECT e.ID,e.Phase FROM Ens.MessageHeader h JOIN Battery_Interop.EvidenceRequest e ON h.MessageBodyId=e.ID WHERE h.SessionId=? AND h.MessageBodyClassName='Battery.Interop.EvidenceRequest' ORDER BY h.ID")
        If $$$ISERR(sc) { Return sc }
        Set result=statement.%Execute(session),phases="",ids=""
        If result.%SQLCODE<0 { Return $$$ERROR($$$GeneralError,result.%Message) }
        While result.%Next() { Set phases=phases_result.%Get("Phase")_"|",ids=ids_result.%Get("ID")_"|" }
        Do ..Check("original_probe_phases_survive",phases="INITIAL|CHECK_EFFECT_RECEIPT|FINAL|")
        Do ..Check("distinct_evidence_message_bodies",($PIECE(ids,"|",1)'=$PIECE(ids,"|",2))&&($PIECE(ids,"|",2)'=$PIECE(ids,"|",3))&&($PIECE(ids,"|",1)'=$PIECE(ids,"|",3)))
        Set statement=##class(%SQL.Statement).%New()
        Set sc=statement.%Prepare("SELECT r.ID,r.CaseJSON FROM Ens.MessageHeader h JOIN Battery_Interop.CaseRequest r ON h.MessageBodyId=r.ID WHERE h.SessionId=? AND h.MessageBodyClassName='Battery.Interop.CaseRequest' AND h.TargetConfigName='Battery.Review' ORDER BY h.ID")
        If $$$ISERR(sc) { Return sc }
        Set result=statement.%Execute(session),count=0
        If result.%SQLCODE<0 { Return $$$ERROR($$$GeneralError,result.%Message) }
        While result.%Next() { Set count=count+1,reviewId(count)=result.%Get("ID"),reviewBody(count)=result.%Get("CaseJSON") }
        Do ..Check("distinct_review_snapshots",(count=2)&&(reviewId(1)'=reviewId(2))&&(reviewBody(1)'=reviewBody(2)))
        Write "TRACE_CONTRACTS_OK",!
        Return $$$OK
    } Catch ex { Write "TRACE_CONTRACTS_ERROR=",ex.DisplayString(),! Return ex.AsStatus() }
}
ClassMethod Check(name As %String, passed As %Boolean)
{
    Set row={"name":(name),"passed":(passed)}
    Write "TRACE_CHECK=",row.%ToJSON(),!
    If 'passed { Throw ##class(%Exception.General).%New("Trace contract failed: "_name) }
}
}
