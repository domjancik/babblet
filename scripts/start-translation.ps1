param([ValidateSet('q4','q8')][string]$Model='q8', [switch]$Cpu)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath runtime\translation.key)) {
    [System.IO.File]::WriteAllText((Join-Path $PWD 'runtime\translation.key'),[Guid]::NewGuid().ToString('N'))
}
$quant = if ($Model -eq 'q8') { 'Q8_0' } else { 'Q4_K_M' }
$layers = if ($Cpu) { 0 } else { 99 }
& .\runtime\llama\llama-server.exe -m "models\hymt2\Hy-MT2-1.8B-$quant.gguf" --host 127.0.0.1 --port 18081 -ngl $layers -c 2048 --parallel 1 --api-key-file runtime\translation.key --no-webui
exit $LASTEXITCODE
