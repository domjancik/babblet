param([string]$Tablet = 'root@10.11.99.1', [switch]$Install)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
if ($Tablet -notmatch '^[A-Za-z0-9][A-Za-z0-9_.@:-]*$') { throw 'Invalid SSH destination.' }
Write-Host 'Prerequisite plan for reMarkable 2 firmware 3.29.0.153:'
Write-Host '  XOVI 0.3.3 ARM32; qt-resource-rebuilder v19-23052026; AppLoad 0.6.0 ARM32.'
Write-Host '  Install only under /home/root/xovi after upstream SHA-256 verification.'
Write-Host '  No boot autostart, SSH-key, firmware, notebook, firewall or service changes.'
Write-Host '  Activation is a separate reviewed step which temporarily restarts xochitl.'
& .\.venv\Scripts\python.exe scripts/prepare-remarkable-framework.py
if ($LASTEXITCODE -ne 0) { throw 'Prerequisite preparation failed.' }
if (-not $Install) { Write-Host 'Review complete. Run with -Install only after approving this launcher installation.'; exit 0 }
$taskOptions = @('-o','HostKeyAlias=10.11.99.1','-o','StrictHostKeyChecking=yes')
& ssh @taskOptions $Tablet 'test "$(uname -m)" = armv7l || exit 20; grep -q ''IMG_VERSION="3.29.0.153"'' /etc/os-release || exit 21; test ! -e /home/root/xovi || exit 22; mkdir -p /home/root/babblet-install'
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed. This helper will not replace an existing XOVI installation or run on another firmware.' }
$taskArchive = Join-Path $taskRoot 'artifacts/remarkable/prerequisites/babblet-launcher-prerequisites.tar.gz'
$taskDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskArchive).Hash.ToLowerInvariant()
& scp @taskOptions $taskArchive "${Tablet}:/home/root/babblet-install/babblet-launcher-prerequisites.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Could not upload prerequisites.' }
$taskCommand = "set -eu; cd /home/root/babblet-install; echo '$taskDigest  babblet-launcher-prerequisites.tar.gz' | sha256sum -c -; test ! -e /home/root/xovi; tar -xzf babblet-launcher-prerequisites.tar.gz -C /home/root; echo 'Launcher files installed; activation has NOT been run.'"
& ssh @taskOptions $Tablet $taskCommand
if ($LASTEXITCODE -ne 0) { throw 'Prerequisite install failed. Inspect /home/root/babblet-install before retrying.' }
Write-Host 'Files installed. Review remarkable/INSTALL.md activation instructions before stopping the stock UI.'
