$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
foreach ($taskName in @('display','translation')) {
    $pidFile=Join-Path $taskRoot "artifacts\$taskName.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { continue }
    $taskPid=[int](Get-Content -LiteralPath $pidFile -Raw).Trim()
    $taskProcess=Get-CimInstance Win32_Process -Filter "ProcessId = $taskPid"
    if (-not $taskProcess) { continue }
    $expectedPath=if ($taskName -eq 'display') { Join-Path $taskRoot '.venv\Scripts\python.exe' } else { Join-Path $taskRoot 'runtime\llama\llama-server.exe' }
    if ($taskProcess.ExecutablePath -ne $expectedPath) { throw "PID does not belong to the $taskName demo" }
    if ($taskName -eq 'display' -and $taskProcess.CommandLine -notmatch 'babblet.cli') { throw 'Unexpected Python process' }
    if ($taskName -eq 'display') {
        $taskChildren=Get-CimInstance Win32_Process -Filter "ParentProcessId = $taskPid" | Where-Object { $_.CommandLine -match 'babblet.cli' }
        foreach($taskChild in $taskChildren) { Stop-Process -Id $taskChild.ProcessId -ErrorAction SilentlyContinue }
    }
    Stop-Process -Id $taskPid
    Write-Output "Stopped $taskName demo"
}
