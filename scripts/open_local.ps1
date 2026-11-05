param([string]$EnvironmentFile = ".env")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$path = Join-Path $root $EnvironmentFile
$values = @{}
foreach ($line in (Get-Content -LiteralPath $path)) {
    if ($line -match '^([A-Z_]+)=(.*)$') { $values[$matches[1]] = $matches[2].Trim() }
}
$key = $values['BATTERY_ACCESS_KEY']
if (-not $key -or $key.Length -lt 32) { throw 'Operator access key missing from the selected private environment file.' }
$port = 8080
if ($values.ContainsKey('BATTERY_WEB_PORT')) { $port = [int]$values['BATTERY_WEB_PORT'] }
if ($port -lt 1 -or $port -gt 65535) { throw 'Invalid local web port.' }
Set-Clipboard -Value $key
Start-Process ("http://127.0.0.1:" + $port)
Write-Output 'Battery opened. Paste the operator key from your clipboard into the sign-in field.'
