Include %occStatus

/// Deployment-owned, read-only transport for Battery's management evidence.
/// A model supplies neither the destination nor credentials. No retry on failure.
Class Battery.Interop.EvidenceAdapter Extends Ens.OutboundAdapter
{
Method ReadEvidence(caseId As %String, phase As %String, partner As %String, Output raw As %String, Output reason As %String) As %Status
{
    Set raw="",reason=""
    If (phase'="CHECK_EFFECT_RECEIPT")&&(phase'="CHECK_FRESH_READBACK")&&(phase'="CHECK_TARGET_VERSION")&&(phase'="FINAL") {
        Set reason="Unsupported read-only probe" Return $$$OK
    }
    If (caseId="")||($LENGTH(caseId)>120)||(partner="")||($LENGTH(partner)>120) {
        Set reason="Invalid evidence read scope" Return $$$OK
    }
    Try {
        Set host=$SYSTEM.Util.GetEnviron("BATTERY_MANAGEMENT_HOST"),key=$SYSTEM.Util.GetEnviron("BATTERY_ADAPTER_KEY")
        If (host="")||($LENGTH(key)<32) { Set reason="Management evidence adapter is not configured" Return $$$OK }
        Set http=##class(%Net.HttpRequest).%New(),http.Server=host,http.Port=8080,http.Timeout=5,http.OpenTimeout=3
        Do http.SetHeader("X-Battery-Adapter",key)
        Do http.SetHeader("X-Battery-Operator",partner)
        Set path="/api/native-evidence/"_##class(%CSP.Page).EscapeURL(caseId)_"?phase="_phase
        Set sc=http.Get(path)
        If $$$ISERR(sc) { Return sc }
        If http.HttpResponse.StatusCode'=200 { Set reason="Management evidence read was not accepted" Return $$$OK }
        If http.HttpResponse.Data.Size>65536 { Set reason="Management evidence exceeds budget" Return $$$OK }
        Do http.HttpResponse.Data.Rewind()
        Set raw=http.HttpResponse.Data.Read(65537)
        Return $$$OK
    } Catch ex { Return ex.AsStatus() }
}
}
