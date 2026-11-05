Include %occStatus
/// Application record, independent of native message retention. A revision is immutable.
Class Battery.Interop.CaseRecord Extends %Persistent
{
Property CaseId As %String(MAXLEN=120) [ Required ];
Property Owner As %String(MAXLEN=120);
Property Operator As %String(MAXLEN=120);
Property Deadline As %BigInt;
Property Lease As %String(MAXLEN=100);
Property RecoveryReason As %String(MAXLEN=400);
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
    Do out.%Set("recovery_reason",r.RecoveryReason),out.%Set("deadline",r.Deadline)
    If details&&(r.ResultJSON'="") { Do out.%Set("result",##class(%DynamicObject).%FromJSON(r.ResultJSON)) }
    Return out
}
/// All admissions, claims, expiry, and completions share one durable state lock.
ClassMethod Begin(id As %String) As %String
{
    Lock +^BatteryCaseService:5
    If '$TEST { Return "" }
    Set token=""
    Try {
        Do ..SweepLocked()
        Set r=..%OpenId(id)
        If $IsObject(r) {
            If r.State="QUEUED" {
                Set token=$SYSTEM.Util.CreateGUID(),r.Lease=token,r.State="RUNNING",r.Deadline=##class(Battery.Interop.OutcomeProof).Now()+..Limit("RUN_SECONDS",600,60,900),r.UpdatedAt=$ZDATETIME($HOROLOG,3,1)
                Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
            }
        }
    } Catch ex { Lock -^BatteryCaseService Throw ex }
    Lock -^BatteryCaseService
    Return token
}
ClassMethod Limit(name As %String, fallback As %Integer, low As %Integer, high As %Integer) As %Integer
{
    Set raw=$SYSTEM.Util.GetEnviron("BATTERY_"_name)
    If raw="" { Return fallback }
    If (raw'?1.N)||(+raw<low)||(+raw>high) { Throw ##class(%Exception.General).%New("Invalid Battery service limit: "_name) }
    Return +raw
}
ClassMethod Active(state As %String) As %Boolean
{
    Return (state="QUEUED")||(state="RUNNING")||(state="ADMISSION_UNCERTAIN")
}
/// No automatic inference replay and no business-effect replay on recovery.
ClassMethod SweepLocked()
{
    Set id="",now=##class(Battery.Interop.OutcomeProof).Now()
    For {
        Set id=$ORDER(^BatteryCaseActive(id)) Quit:id=""
        Set r=..%OpenId(id)
        If '$IsObject(r) { Kill ^BatteryCaseActive(id) Continue }
        If '..Active(r.State) { Kill ^BatteryCaseActive(id) Continue }
        If r.Deadline<=now {
            Set r.RecoveryReason="Expired "_r.State_" lease; inspect the trace and explicitly create a new review revision. No operation was replayed.",r.State="RECOVERY_REQUIRED",r.Lease="",r.UpdatedAt=$ZDATETIME($HOROLOG,3,1)
            Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
            Kill ^BatteryCaseActive(id)
        }
    }
}
ClassMethod Sweep() As %Status
{
    Lock +^BatteryCaseService:5
    If '$TEST { Return $$$ERROR($$$GeneralError,"Maintenance lock unavailable") }
    Try { Do ..SweepLocked() Set sc=$$$OK } Catch ex { Set sc=ex.AsStatus() }
    Lock -^BatteryCaseService
    Return sc
}
/// Must be called while holding the service lock, before persisting admission.
ClassMethod Capacity(owner As %String, operator As %String) As %Boolean
{
    Do ..SweepLocked()
    Set all=0,own=0,id="",day=+$HOROLOG
    For {
        Set id=$ORDER(^BatteryCaseActive(id)) Quit:id=""
        Set all=all+1
        Set r=..%OpenId(id)
        If $IsObject(r) { If (r.Owner=owner)&&(r.Operator=operator) { Set own=own+1 } }
    }
    Return (all<..Limit("ACTIVE_LIMIT",4,1,32))&&(own<..Limit("OPERATOR_ACTIVE_LIMIT",2,1,16))&&($Get(^BatteryCaseBudget(day,"all"),0)<..Limit("DAILY_LIMIT",100,1,10000))&&($Get(^BatteryCaseBudget(day,owner,operator),0)<..Limit("OPERATOR_DAILY_LIMIT",20,1,1000))
}
ClassMethod Budget(owner As %String, operator As %String) As %DynamicObject
{
    Set day=+$HOROLOG
    Return {"operator_daily_used":($Get(^BatteryCaseBudget(day,owner,operator),0)),"operator_daily_limit":(..Limit("OPERATOR_DAILY_LIMIT",20,1,1000)),"service_daily_used":($Get(^BatteryCaseBudget(day,"all"),0)),"service_daily_limit":(..Limit("DAILY_LIMIT",100,1,10000)),"operator_active_limit":(..Limit("OPERATOR_ACTIVE_LIMIT",2,1,16)),"service_active_limit":(..Limit("ACTIVE_LIMIT",4,1,32))}
}
ClassMethod Reserve(r As Battery.Interop.CaseRecord)
{
    Set ^BatteryCaseActive(r.CaseId)=1,day=+$HOROLOG
    Set n=$INCREMENT(^BatteryCaseBudget(day,"all")),n=$INCREMENT(^BatteryCaseBudget(day,r.Owner,r.Operator))
}
ClassMethod Current(id As %String, lease As %String) As %Boolean
{
    If id="" { Return 1 }
    Set sc=..Sweep() If $$$ISERR(sc) { Return 0 }
    Set r=..%OpenId(id)
    If '$IsObject(r) { Return 0 }
    Return (r.State="RUNNING")&&(r.Lease=lease)&&(lease'="")&&(r.Deadline>##class(Battery.Interop.OutcomeProof).Now())
}
/// Old installations had no deadline/index. Migrate once during deployment.
ClassMethod Migrate() As %Status
{
    Lock +^BatteryCaseService:5
    If '$TEST { Return $$$ERROR($$$GeneralError,"Migration lock unavailable") }
    Try {
        Set stamp=""
        For {
            Set stamp=$ORDER(^BatteryCaseList(stamp)) Quit:stamp=""
            Set id=""
            For {
                Set id=$ORDER(^BatteryCaseList(stamp,id)) Quit:id=""
                Set r=..%OpenId(id) Continue:'$IsObject(r)
                If r.Owner="" {
                    Set r.Owner="BatteryAdapterUser"
                    Set r.Operator="legacy-operator"
                    If r.RequestJSON'= "" {
                        Set body=##class(%DynamicObject).%FromJSON(r.RequestJSON),contract=body.%Get("contract")
                        If $IsObject(contract) { Set r.Operator=contract.%Get("partner","legacy-operator") }
                    }
                    If ..Active(r.State) { Set r.State="RECOVERY_REQUIRED",r.RecoveryReason="Legacy active record had no lease; explicit review required" }
                    Set sc=r.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
                }
            }
        }
        Set sc=$$$OK
    } Catch ex { Set sc=ex.AsStatus() }
    Lock -^BatteryCaseService
    Return sc
}
ClassMethod Complete(id As %String, response As Battery.Interop.CaseResponse, lease As %String) As %Status
{
    Lock +^BatteryCaseService:2
    If '$TEST { Return $$$ERROR($$$GeneralError,"Case completion lock unavailable") }
    Try {
        Do ..SweepLocked()
        Set r=..%OpenId(id)
        If '$IsObject(r) { Throw ##class(%Exception.General).%New("Case record missing") }
        If (r.State'="RUNNING")||(r.Lease'=lease)||(lease="") { Lock -^BatteryCaseService Return $$$ERROR($$$GeneralError,"Expired or foreign case lease; completion rejected") }
        Set sc=response.%Save() If $$$ISERR(sc) { Throw ##class(%Exception.StatusException).CreateFromStatus(sc) }
        Set result={"state":(response.State),"assertion":(response.GateVerdict),"output":(response.GateOutput),"reviewer_assertion":(response.ReviewerVerdict),"reviewer_output":(response.OutputResult),"applicability":(response.ReviewerApplicability),"explanation":(response.Explanation),"proposed_probe":(response.InvestigatorProbe),"executed_probe":(response.ExecutedProbe),"response_id":(response.%Id())}
        For key="ProofJSON","ReviewHistoryJSON","ProbeHistoryJSON" {
            Set raw=$PROPERTY(response,key)
            If raw'="" { Do result.%Set(key,##class(%DynamicObject).%FromJSON(raw)) }
        }
        Set r.State=response.State,r.ResultJSON=result.%ToJSON(),r.UpdatedAt=$ZDATETIME($HOROLOG,3,1)
        Set sc=r.%Save()
        If $$$ISOK(sc) { Kill ^BatteryCaseActive(id) }
    } Catch ex { Set sc=ex.AsStatus() }
    Lock -^BatteryCaseService
    Return sc
}
}
