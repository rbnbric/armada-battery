Include (%occStatus, Ensemble)
/// Private adapter API. Password-authenticated application; never expose IRIS credentials in the browser.
Class Battery.Interop.CaseAPI Extends %CSP.REST
{
Parameter UseSession=0;
Parameter HandleCorsRequest=0;
XData UrlMap
{
<Routes>
<Route Url="/cases" Method="GET" Call="List"/>
<Route Url="/cases/:id" Method="GET" Call="Get"/>
<Route Url="/cases/:id/explain" Method="POST" Call="Explain"/>
<Route Url="/cases" Method="POST" Call="Submit"/>
</Routes>
}
ClassMethod Reply(value As %DynamicObject, code As %String="200 OK") As %Status
{
    Set %response.Status=code,%response.ContentType="application/json"
    Write value.%ToJSON()
    Return $$$OK
}
ClassMethod List() As %Status
{
    Set sc=##class(Battery.Interop.CaseRecord).Sweep()
    If $$$ISERR(sc) { Return ..Reply({"detail":"Case maintenance unavailable"},"503 Service Unavailable") }
    Set operator=%request.GetCgiEnv("HTTP_X_BATTERY_OPERATOR")
    Set items=[],stamp="",count=0
    For {
        Set stamp=$ORDER(^BatteryCaseList(stamp),-1) Quit:stamp=""
        Set id=""
        For {
            Set id=$ORDER(^BatteryCaseList(stamp,id)) Quit:id=""
            Set r=##class(Battery.Interop.CaseRecord).%OpenId(id)
            If $IsObject(r) { If (r.Owner=$USERNAME)&&((operator="")||(r.Operator=operator)) { Do items.%Push(##class(Battery.Interop.CaseRecord).View(r,0)) Set count=count+1 } }
            Quit:count>=50
        }
        Quit:count>=50
    }
    Return ..Reply({"items":(items),"scope":"authenticated adapter account and operator","budget":(##class(Battery.Interop.CaseRecord).Budget($USERNAME,operator))})
}
ClassMethod Get(id As %String) As %Status
{
    Set sc=##class(Battery.Interop.CaseRecord).Sweep()
    If $$$ISERR(sc) { Return ..Reply({"detail":"Case maintenance unavailable"},"503 Service Unavailable") }
    Set r=##class(Battery.Interop.CaseRecord).%OpenId(id)
    If '$IsObject(r) { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
    If r.Owner'=$USERNAME { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
    Set operator=%request.GetCgiEnv("HTTP_X_BATTERY_OPERATOR")
    If (operator'="")&&(r.Operator'=operator) { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
    Return ..Reply(##class(Battery.Interop.CaseRecord).View(r))
}
/// One explicit explanation attempt per evidence revision, separate from the solver.
/// A failed explanation never changes the case outcome or dispatches an operation.
ClassMethod Explain(id As %String) As %Status
{
    Set locked=0
    Try {
        If %request.Content.Size>16384 { Return ..Reply({"detail":"Brief too large"},"413 Content Too Large") }
        Try { Set body=##class(%DynamicObject).%FromJSON(%request.Content) }
        Catch parseError { Return ..Reply({"detail":"Invalid explanation request"},"400 Bad Request") }
        If '$IsObject(body) { Return ..Reply({"detail":"Invalid explanation request"},"400 Bad Request") }
        If 'body.%IsA("%DynamicObject") { Return ..Reply({"detail":"Invalid explanation request"},"400 Bad Request") }
        Set revision=body.%Get("revision"),brief=body.%Get("brief"),operator=%request.GetCgiEnv("HTTP_X_BATTERY_OPERATOR")
        If (body.%GetTypeOf("revision")'="string")||($LENGTH(revision)'=64)||(revision'?64AN) { Return ..Reply({"detail":"Invalid revision"},"400 Bad Request") }
        If '$IsObject(brief) { Return ..Reply({"detail":"Missing brief"},"400 Bad Request") }
        If 'brief.%IsA("%DynamicObject") { Return ..Reply({"detail":"Invalid brief"},"400 Bad Request") }
        If (brief.%Get("case_id")'=id)||(brief.%Get("revision")'=revision) { Return ..Reply({"detail":"Brief binding mismatch"},"409 Conflict") }
        Set r=##class(Battery.Interop.CaseRecord).%OpenId(id)
        If '$IsObject(r) { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
        If (r.Owner'=$USERNAME)||(operator="")||(r.Operator'=operator) { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
        If ##class(Battery.Interop.CaseRecord).Active(r.State) { Return ..Reply({"detail":"Review still active"},"409 Conflict") }
        Set attempt=body.%Get("attempt",1)
        If (attempt'=1)&&(attempt'=2) { Return ..Reply({"detail":"Invalid explanation attempt"},"400 Bad Request") }
        Set cacheKey=revision_$SELECT(attempt=1:"",1:"-retry")
        Set sc=##class(Ens.Director).GetProductionStatus(.productionName,.productionState)
        If $$$ISERR(sc)||(productionState'=$$$eProductionStateRunning) { Return ..Reply({"detail":"Native production is not running; inspect production recovery"},"503 Service Unavailable") }
        Set raw=brief.%ToJSON()
        Lock +^BatteryExplainService:2
        If '$TEST { Return ..Reply({"detail":"Explanation service busy"},"409 Conflict") }
        Set locked=1
        If $DATA(^BatteryExplanation(id,cacheKey)) {
            Set cached=^BatteryExplanation(id,cacheKey)
            Lock -^BatteryExplainService Set locked=0
            If cached="pending" { Return ..Reply({"detail":"Prior explanation attempt is unconfirmed"},"409 Conflict") }
            If cached="failed" { Return ..Reply({"detail":"Prior explanation failed; use the structured brief"},"503 Service Unavailable") }
            Return ..Reply(##class(%DynamicObject).%FromJSON(cached))
        }
        Set day=+$HOROLOG
        If ($Get(^BatteryExplanationBudget(day,"all"),0)>=100)||($Get(^BatteryExplanationBudget(day,$USERNAME,operator),0)>=20) {
            Lock -^BatteryExplainService Set locked=0
            Return ..Reply({"detail":"Explanation budget exhausted"},"429 Too Many Requests")
        }
        Set ^BatteryExplanation(id,cacheKey)="pending"
        Set n=$INCREMENT(^BatteryExplanationBudget(day,"all")),n=$INCREMENT(^BatteryExplanationBudget(day,$USERNAME,operator))
        Lock -^BatteryExplainService Set locked=0
        Set sc=##class(Ens.Director).CreateBusinessService("Battery.Intake",.service)
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set request=##class(Battery.Interop.AgentRequest).%New(),request.Role="explainer",request.CaseJSON=raw
        Set sc=service.Explain(request,.answer)
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        If '$IsObject(answer) { Throw ##class(%Exception.General).%New("No explainer response") }
        Set out={"content":(answer.Content),"usage":(answer.UsageJSON),"response_id":(answer.%Id())}
        Set ^BatteryExplanation(id,cacheKey)=out.%ToJSON()
        Return ..Reply(out)
    } Catch ex {
        If locked { Lock -^BatteryExplainService }
        If $Get(cacheKey)'="" { If $Get(^BatteryExplanation(id,cacheKey))="pending" { Set ^BatteryExplanation(id,cacheKey)="failed" } }
        Set ^BatteryExplanationErrors($INCREMENT(^BatteryExplanationErrors))=$SYSTEM.Status.GetErrorText(ex.AsStatus())
        Return ..Reply({"detail":"Explanation failed; structured brief remains available"},"503 Service Unavailable")
    }
}

ClassMethod Submit() As %Status
{
    Set locked=0
    Try {
        If %request.Content.Size>131072 { Return ..Reply({"detail":"Case envelope too large"},"413 Content Too Large") }
        Try { Set body=##class(%DynamicObject).%FromJSON(%request.Content) }
        Catch parseError { Return ..Reply({"detail":"Request must be a JSON object"},"400 Bad Request") }
        If '$IsObject(body) { Return ..Reply({"detail":"Request must be a JSON object"},"400 Bad Request") }
        If 'body.%IsA("%DynamicObject") { Return ..Reply({"detail":"Request must be a JSON object"},"400 Bad Request") }
        Set case=body.%Get("case"),contract=body.%Get("contract"),initial=body.%Get("initial"),parent=body.%Get("parent_id","")
        If '##class(Battery.Interop.CaseProcess).ValidCase(case) { Return ..Reply({"detail":"Invalid case"},"400 Bad Request") }
        If '$IsObject(contract) { Return ..Reply({"detail":"Missing contract"},"400 Bad Request") }
        If '##class(Battery.Interop.OutcomeProof).Contract(contract.%ToJSON(),.validated) { Return ..Reply({"detail":"Invalid measurement contract"},"400 Bad Request") }
        If '$IsObject(initial) { Return ..Reply({"detail":"Missing initial observation"},"400 Bad Request") }
        If (body.%GetTypeOf("parent_id")'="string")&&(body.%IsDefined("parent_id")) { Return ..Reply({"detail":"Invalid parent"},"400 Bad Request") }
        If $LENGTH(parent)>120 { Return ..Reply({"detail":"Invalid parent"},"400 Bad Request") }
        Set operator=%request.GetCgiEnv("HTTP_X_BATTERY_OPERATOR")
        If operator="" { Set operator=contract.partner }
        If (operator'=contract.partner)||($LENGTH(operator)>120) { Return ..Reply({"detail":"Operator scope mismatch"},"403 Forbidden") }
        Set id=case.id,raw=body.%ToJSON()
        Lock +^BatteryCaseService:2
        If '$TEST { Return ..Reply({"detail":"Case admission busy"},"409 Conflict") }
        Set locked=1
        Do ##class(Battery.Interop.CaseRecord).SweepLocked()
        Set r=##class(Battery.Interop.CaseRecord).%OpenId(id)
        If $IsObject(r) {
            Lock -^BatteryCaseService Set locked=0
            If (r.Owner'=$USERNAME)||(r.Operator'=operator) { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
            If r.RequestJSON'=raw { Return ..Reply({"detail":"Case revision is immutable"},"409 Conflict") }
            Return ..Reply(##class(Battery.Interop.CaseRecord).View(r))
        }
        If '##class(Battery.Interop.CaseRecord).Capacity($USERNAME,operator) { Lock -^BatteryCaseService Set locked=0 Return ..Reply({"detail":"Active or daily review budget exhausted"},"429 Too Many Requests") }
        If parent'="" {
            Set previous=##class(Battery.Interop.CaseRecord).%OpenId(parent)
            If '$IsObject(previous) { Lock -^BatteryCaseService Set locked=0 Return ..Reply({"detail":"Parent case not found"},"409 Conflict") }
            If (previous.Owner'=$USERNAME)||(previous.Operator'=operator) { Lock -^BatteryCaseService Set locked=0 Return ..Reply({"detail":"Parent unavailable"},"409 Conflict") }
            If ##class(Battery.Interop.CaseRecord).Active(previous.State) { Lock -^BatteryCaseService Set locked=0 Return ..Reply({"detail":"Parent is still active"},"409 Conflict") }
        }
        Set sc=##class(Ens.Director).CreateBusinessService("Battery.Intake",.service)
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        TSTART
        Set binding=##class(Battery.Interop.EvidenceBinding).%New(),binding.CaseId=id,binding.CaseJSON=case.%ToJSON(),binding.ContractJSON=contract.%ToJSON(),binding.InitialJSON=initial.%ToJSON(),binding.CurrentJSON=initial.%ToJSON(),binding.Adapter="management"
        Set sc=binding.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set r=##class(Battery.Interop.CaseRecord).%New(),r.CaseId=id,r.ParentId=parent,r.RequestJSON=raw,r.State="QUEUED",r.CreatedAt=$ZDATETIME($HOROLOG,3,1),r.UpdatedAt=r.CreatedAt
        Set r.Owner=$USERNAME,r.Operator=operator,r.Deadline=##class(Battery.Interop.OutcomeProof).Now()+##class(Battery.Interop.CaseRecord).Limit("QUEUE_SECONDS",120,10,600)
        Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set ^BatteryCaseList(r.CreatedAt,id)=1
        Do ##class(Battery.Interop.CaseRecord).Reserve(r)
        TCOMMIT
        Set request=##class(Battery.Interop.CaseRequest).%New(),request.CaseJSON=binding.CaseJSON,request.RunId=id
        Set sc=service.Queue(request)
        If $$$ISERR(sc) {
            Set r.State="ADMISSION_UNCERTAIN",r.ResultJSON="{""explanation"":""Queue admission uncertain; inspect the native trace before resuming""}"
            Set saved=r.%Save() If $$$ISERR(saved) { Throw ##class(%Exception.StatusException).CreateFromStatus(saved) }
        }
        Lock -^BatteryCaseService Set locked=0
        Return ..Reply(##class(Battery.Interop.CaseRecord).View(r),"202 Accepted")
    } Catch ex {
        If $TLEVEL { TROLLBACK }
        If locked { Lock -^BatteryCaseService }
        Set ^BatteryCaseAdmissionErrors($INCREMENT(^BatteryCaseAdmissionErrors))=$SYSTEM.Status.GetErrorText(ex.AsStatus())
        Return ..Reply({"detail":"Native case admission failed; inspect server event log"},"500 Internal Server Error")
    }
}
}
