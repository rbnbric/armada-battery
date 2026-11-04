/// Deterministic receipt profile: exact effect count + result, independent rule/acceptance.
/// UNKNOWN is not FAIL. Only fresh, correlated observations establish either.
Class Battery.Interop.OutcomeProof Extends %RegisteredObject
{
ClassMethod Now() As %Integer
{
    Return ($PIECE($HOROLOG,",",1)*86400)+$PIECE($HOROLOG,",",2)
}
ClassMethod Integer(obj As %DynamicObject, key As %String, upper As %Integer) As %Boolean
{
    If obj.%GetTypeOf(key)'="number" { Return 0 }
    Set n=obj.%Get(key)
    Return (n>=0)&&(n<=upper)&&(n=(n\1))
}
ClassMethod Contract(raw As %String, Output c As %DynamicObject) As %Boolean
{
    If '##class(Battery.Interop.CaseProcess).ParseObject(raw,.c,.detail) { Return 0 }
    If c.%Size()'=11 { Return 0 }
    For k="partner","attempt","target","version","rule_version","expected_result","accepted_result" {
        If '##class(Battery.Interop.CaseProcess).ValidText(c,k,120) { Return 0 }
    }
    If c.%Get("profile")'="receipt-v1" { Return 0 }
    If '..Integer(c,"expected_count",1000000) { Return 0 }
    If '..Integer(c,"accepted_count",1000000) { Return 0 }
    If '..Integer(c,"max_age",3600) { Return 0 }
    If c.%Get("max_age")<1 { Return 0 }
    Return 1
}
ClassMethod Assess(contract As %String, observation As %String, now As %Integer = 0) As %DynamicObject
{
    Set r={"verdict":"NO","output":"UNKNOWN","applicability":"UNKNOWN","usable":false,"reason":"Invalid measurement contract"}
    If '..Contract(contract,.c) { Return r }
    Do r.%Set("applicability",$SELECT(c.version=c.%Get("rule_version"):"APPLICABLE",1:"INAPPLICABLE"))
    Do r.%Set("reason","Missing or malformed observation")
    If '##class(Battery.Interop.CaseProcess).ParseObject(observation,.o,.detail) { Return r }
    If (o.%GetTypeOf("available")'="boolean") { Return r }
    If 'o.available { Do r.%Set("reason","Outcome not observed") Return r }
    If o.%Size()'=9 { Return r }
    For k="partner","attempt","target","version","result","source" {
        If '##class(Battery.Interop.CaseProcess).ValidText(o,k,120) { Return r }
    }
    If '..Integer(o,"count",1000000) { Return r }
    If '..Integer(o,"observed_at",99999999999) { Return r }
    For k="partner","attempt","target","version" {
        If o.%Get(k)'=c.%Get(k) { Do r.%Set("reason","Observation scope mismatch: "_k) Return r }
    }
    If now=0 { Set now=..Now() }
    If o.%Get("observed_at")>now { Do r.%Set("reason","Observation is from the future") Return r }
    If (now-o.%Get("observed_at"))>=c.%Get("max_age") { Do r.%Set("reason","Observation expired") Return r }
    Do r.%Set("usable",1,"boolean"),r.%Set("reason","Fresh scoped receipt measurement")
    Do r.%Set("output",$SELECT((o.count=c.%Get("accepted_count"))&&(o.result=c.%Get("accepted_result")):"PASS",1:"FAIL"))
    If (c.version=c.%Get("rule_version"))&&(o.count=c.%Get("expected_count"))&&(o.result=c.%Get("expected_result")) { Do r.%Set("verdict","YES") }
    Return r
}
}
