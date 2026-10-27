param([switch]$Microphone, [int]$AudioDevice=-1)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$deckArgs=@('-m','babblet.cli','--serve')
if ($Microphone) { $deckArgs += '--mic' }
if ($AudioDevice -ge 0) { $deckArgs += @('--audio-device',"$AudioDevice") }
& .\.venv\Scripts\python.exe @deckArgs
exit $LASTEXITCODE
