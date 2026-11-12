# Read-only Companion Windows beta preflight for the human validation.
# Does not install, stop, update, or reconfigure any running Companion.
param(
    [Parameter(Mandatory=$true)][string]$BetaOrigin
)
$ErrorActionPreference = 'Stop'
if ($BetaOrigin -notmatch '^https://[A-Za-z0-9.-]+(?::443)?$') {
    throw 'Specify the exact HTTPS origin of the private Montara beta.'
}
$Origin = $BetaOrigin.TrimEnd('/')
$uri = 'http://127.0.0.1:47820/health'
Write-Host 'Montara SMART Companion Windows preflight (read-only)'
Write-Host ('Beta origin: ' + $Origin)
try {
    $response = Invoke-WebRequest -Uri $uri -Headers @{ Origin = $Origin } -TimeoutSec 6 -UseBasicParsing
} catch {
    Write-Host 'RESULT: Companion unavailable or this beta origin was rejected.'
    Write-Host 'Keep the existing Companion intact. Do not force-stop active jobs.'
    exit 2
}
if ($response.StatusCode -ne 200) { throw ('Companion HTTP ' + $response.StatusCode) }
$health = $response.Content | ConvertFrom-Json
if ($health.app -ne 'montara-companion') { throw 'Unknown service on local port 47820' }
$engine = [string]$health.local_video.engine
$expected = 'b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b'
Write-Host ('Companion version: ' + $health.version)
Write-Host ('FFmpeg detected: ' + [bool]$health.ffmpeg)
Write-Host ('Active jobs: ' + [bool]$health.busy)
Write-Host ('Local renderer: ' + $(if ($engine) { $engine.Substring(0,[Math]::Min(12,$engine.Length)) } else { 'not installed' }))
if ($health.busy) {
    Write-Host 'RESULT: Companion has active work. No update or replacement is safe now.'
    exit 3
}
if ($engine -ne $expected) {
    Write-Host 'RESULT: The renderer does not match the current Stage Engine; a compatible Companion update is required before exporting.'
    exit 4
}
if (-not $health.ffmpeg) { Write-Host 'RESULT: FFmpeg unavailable'; exit 5 }
Write-Host 'RESULT: READY — local Companion reachable from the beta origin, FFmpeg available, exact Engine version matched.'
