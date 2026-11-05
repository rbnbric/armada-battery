Include %occStatus
/// Application record, independent of native message retention. A revision is immutable.
Class Battery.Interop.CaseRecord Extends %Persistent
{
Property CaseId As %String(MAXLEN=120) [ Required ];
Property ParentId As %String(MAXLEN=120);
Property RequestJSON As %String(MAXLEN="");
Property State As %String(MAXLEN=60);
Property ResultJSON As %String(MAXLEN="");
Property CreatedAt As %TimeStamp;
Property UpdatedAt As %TimeStamp;
Index CaseKey On CaseId [ IdKey ];

ClassMethod View(r As Battery.Interop.CaseRecord, details As %Boolean = 1) As %DynamicObject
{
    Set out={"id":(r.CaseId),"parent_id":(r.ParentId),"state":(r.State),"created_at":(r.CreatedAt),"updated_at":(r.UpdatedAt)}
    If details&&(r.ResultJSON'="") { Do out.%Set("result",##class(%DynamicObject).%FromJSON(r.ResultJSON)) }
    Return out
}
ClassMethod Begin(id As %String) As %Boolean
{
    Lock +^BatteryCaseClaim(id):2
    If '$TEST { Return 0 }
    Try {
        Set r=..%OpenId(id)
        Set ok=$IsObject(r)
        If ok { Set ok=(r.State="QUEUED") }
        If ok { Set r.State="RUNNING",r.UpdatedAt=$ZDATETIME($HOROLOG,3,1) Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) } }
    } Catch ex { Lock -^BatteryCaseClaim(id) Throw ex }
    Lock -^BatteryCaseClaim(id)
    Return ok
}
ClassMethod Complete(id As %String, response As Battery.Interop.CaseResponse) As %Status
{
    Lock +^BatteryCaseClaim(id):2
    If '$TEST { Return $$$ERROR($$$GeneralError,"Case completion lock unavailable") }
    Try {
        Set r=..%OpenId(id)
        If '$IsObject(r) { Throw ##class(%Exception.General).%New("Case record missing") }
        Set sc=response.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set result={"state":(response.State),"assertion":(response.GateVerdict),"output":(response.GateOutput),"reviewer_assertion":(response.ReviewerVerdict),"reviewer_output":(response.OutputResult),"applicability":(response.ReviewerApplicability),"explanation":(response.Explanation),"proposed_probe":(response.InvestigatorProbe),"executed_probe":(response.ExecutedProbe),"response_id":(response.%Id())}
        For key="ProofJSON","ReviewHistoryJSON","ProbeHistoryJSON" {
            Set raw=$PROPERTY(response,key)
            If raw'="" { Do result.%Set(key,##class(%DynamicObject).%FromJSON(raw)) }
        }
        Set r.State=response.State,r.ResultJSON=result.%ToJSON(),r.UpdatedAt=$ZDATETIME($HOROLOG,3,1)
        Set sc=r.%Save()
    } Catch ex { Set sc=ex.AsStatus() }
    Lock -^BatteryCaseClaim(id)
    Return sc
}
}
