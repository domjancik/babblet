param(
    [string]$Tablet = 'root@10.11.99.1',
    [string]$HostKeyAlias = '10.11.99.1'
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
if ($Tablet -notmatch '^[A-Za-z0-9][A-Za-z0-9_.@:-]*$' -or $HostKeyAlias -notmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]*$') {
    throw 'Use a tablet SSH hostname or root@IP, not additional SSH options.'
}
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskState = Invoke-RestMethod 'http://127.0.0.1:8090/api/tablet' -TimeoutSec 3
if (-not $taskState.session) { throw 'Restart Babblet with the tablet presentation endpoint first.' }
& $taskPython -c "from babblet.tablet import read_token; read_token('runtime/tablet.key')"
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the tablet token.' }
$taskToken = (Get-Content -Raw 'runtime/tablet.key').Trim()
$taskHeaders = @{ Authorization = 'Bearer ' + $taskToken }
$taskGatewayReady = $false
try { $null = Invoke-RestMethod 'http://127.0.0.1:8092/v1/display' -Headers $taskHeaders -TimeoutSec 2; $taskGatewayReady = $true } catch {}
if (-not $taskGatewayReady) {
    $taskGateway = Start-Process -FilePath $taskPython -ArgumentList @('-m','babblet.tablet') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'artifacts/tablet-gateway-stdout.log' -RedirectStandardError 'artifacts/tablet-gateway-stderr.log'
    $taskGateway.Id | Set-Content 'artifacts/tablet-gateway.pid'
    for ($taskAttempt = 0; $taskAttempt -lt 20; $taskAttempt++) {
        Start-Sleep -Milliseconds 250
        try { $null = Invoke-RestMethod 'http://127.0.0.1:8092/v1/display' -Headers $taskHeaders -TimeoutSec 1; $taskGatewayReady = $true; break } catch {}
        if ($taskGateway.HasExited) { throw 'Tablet gateway could not start. See artifacts/tablet-gateway-stderr.log.' }
    }
}
if (-not $taskGatewayReady) { throw 'Tablet gateway is not ready.' }
Write-Host 'Opening encrypted network tunnel. Keep this terminal open; Ctrl+C disconnects the tablet.'
Write-Host 'USB networking only by default. No LAN listener or firewall change is required.'
# HostKeyAlias reuses the tablet identity already verified over USB. A mismatch
# fails instead of silently trusting a new Wi-Fi host key.
& ssh -N -T -o "HostKeyAlias=$HostKeyAlias" -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -R '127.0.0.1:8092:127.0.0.1:8092' $Tablet
exit $LASTEXITCODE
