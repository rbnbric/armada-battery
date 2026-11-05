Include %occStatus
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
    Set items=[],stamp="",count=0
    For {
        Set stamp=$ORDER(^BatteryCaseList(stamp),-1) Quit:stamp=""
        Set id=""
        For {
            Set id=$ORDER(^BatteryCaseList(stamp,id)) Quit:id=""
            Set r=##class(Battery.Interop.CaseRecord).%OpenId(id)
            If $IsObject(r) { Do items.%Push(##class(Battery.Interop.CaseRecord).View(r,0)) Set count=count+1 }
            Quit:count>=50
        }
        Quit:count>=50
    }
    Return ..Reply({"items":(items),"scope":"single-operator installation"})
}
ClassMethod Get(id As %String) As %Status
{
    Set r=##class(Battery.Interop.CaseRecord).%OpenId(id)
    If '$IsObject(r) { Return ..Reply({"detail":"Case not found"},"404 Not Found") }
    Return ..Reply(##class(Battery.Interop.CaseRecord).View(r))
}
ClassMethod Submit() As %Status
{
    Set locked=0
    Try {
        If %request.Content.Size>131072 { Return ..Reply({"detail":"Case envelope too large"},"413 Content Too Large") }
        Set body=##class(%DynamicObject).%FromJSON(%request.Content)
        Set case=body.%Get("case"),contract=body.%Get("contract"),initial=body.%Get("initial"),parent=body.%Get("parent_id","")
        If '##class(Battery.Interop.CaseProcess).ValidCase(case) { Return ..Reply({"detail":"Invalid case"},"400 Bad Request") }
        If '$IsObject(contract) { Return ..Reply({"detail":"Missing contract"},"400 Bad Request") }
        If '##class(Battery.Interop.OutcomeProof).Contract(contract.%ToJSON(),.validated) { Return ..Reply({"detail":"Invalid measurement contract"},"400 Bad Request") }
        If '$IsObject(initial) { Return ..Reply({"detail":"Missing initial observation"},"400 Bad Request") }
        If (body.%GetTypeOf("parent_id")'="string")&&(body.%IsDefined("parent_id")) { Return ..Reply({"detail":"Invalid parent"},"400 Bad Request") }
        If $LENGTH(parent)>120 { Return ..Reply({"detail":"Invalid parent"},"400 Bad Request") }
        Set id=case.id,raw=body.%ToJSON()
        Lock +^BatteryCaseClaim(id):2
        If '$TEST { Return ..Reply({"detail":"Case admission busy"},"409 Conflict") }
        Set locked=1,r=##class(Battery.Interop.CaseRecord).%OpenId(id)
        If $IsObject(r) {
            Lock -^BatteryCaseClaim(id) Set locked=0
            If r.RequestJSON'=raw { Return ..Reply({"detail":"Case revision is immutable"},"409 Conflict") }
            Return ..Reply(##class(Battery.Interop.CaseRecord).View(r))
        }
        If parent'="" {
            Set previous=##class(Battery.Interop.CaseRecord).%OpenId(parent)
            If '$IsObject(previous) { Lock -^BatteryCaseClaim(id) Set locked=0 Return ..Reply({"detail":"Parent case not found"},"409 Conflict") }
            If (previous.State="RUNNING")||(previous.State="QUEUED") { Lock -^BatteryCaseClaim(id) Set locked=0 Return ..Reply({"detail":"Parent is still active"},"409 Conflict") }
        }
        Set sc=##class(Ens.Director).CreateBusinessService("Battery.Intake",.service)
        If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        TSTART
        Set binding=##class(Battery.Interop.EvidenceBinding).%New(),binding.CaseId=id,binding.CaseJSON=case.%ToJSON(),binding.ContractJSON=contract.%ToJSON(),binding.InitialJSON=initial.%ToJSON(),binding.CurrentJSON=initial.%ToJSON(),binding.Adapter="management"
        Set sc=binding.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set r=##class(Battery.Interop.CaseRecord).%New(),r.CaseId=id,r.ParentId=parent,r.RequestJSON=raw,r.State="QUEUED",r.CreatedAt=$ZDATETIME($HOROLOG,3,1),r.UpdatedAt=r.CreatedAt
        Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set ^BatteryCaseList(r.CreatedAt,id)=1
        TCOMMIT
        Set request=##class(Battery.Interop.CaseRequest).%New(),request.CaseJSON=binding.CaseJSON,request.RunId=id
        Set sc=service.Queue(request)
        If $$$ISERR(sc) {
            Set r.State="ADMISSION_UNCERTAIN",r.ResultJSON="{""explanation"":""Queue admission uncertain; inspect the native trace before resuming""}"
            Set saved=r.%Save() If $$$ISERR(saved) { Throw ##class(%Exception.StatusException).CreateFromStatus(saved) }
        }
        Lock -^BatteryCaseClaim(id) Set locked=0
        Return ..Reply(##class(Battery.Interop.CaseRecord).View(r),"202 Accepted")
    } Catch ex {
        If $TLEVEL { TROLLBACK }
        If locked { Lock -^BatteryCaseClaim(id) }
        Set ^BatteryCaseAdmissionErrors($INCREMENT(^BatteryCaseAdmissionErrors))=$SYSTEM.Status.GetErrorText(ex.AsStatus())
        Return ..Reply({"detail":"Native case admission failed; inspect server event log"},"500 Internal Server Error")
    }
}
}
