param([int]$MicrophoneIndex=-1)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
& .\.venv\Scripts\python.exe scripts/prepare-desktop.py --microphone-index $MicrophoneIndex
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the desktop launcher.' }
$taskPrograms=[Environment]::GetFolderPath('Programs')
$taskShortcutPath=Join-Path $taskPrograms 'Babblet.lnk'
$taskShell=New-Object -ComObject WScript.Shell
$taskShortcut=$taskShell.CreateShortcut($taskShortcutPath)
$taskShortcut.TargetPath=Join-Path $taskRoot '.venv\Scripts\pythonw.exe'
$taskShortcut.Arguments='-m babblet.desktop'
$taskShortcut.WorkingDirectory=$taskRoot
$taskShortcut.IconLocation=(Join-Path $taskRoot 'runtime\babblet.ico')+',0'
$taskShortcut.Description='Start local live translation and connect the reMarkable over USB'
$taskShortcut.WindowStyle=1
$taskShortcut.Save()
Write-Output "Installed Start menu app: $taskShortcutPath"
