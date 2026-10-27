param([string]$Tablet = 'root@10.11.99.1', [string]$HostKeyAlias = '10.11.99.1')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
if ($Tablet -notmatch '^[A-Za-z0-9][A-Za-z0-9_.@:-]*$' -or $HostKeyAlias -notmatch '^[A-Za-z0-9][A-Za-z0-9_.:-]*$') { throw 'Invalid SSH destination.' }
$taskOptions = @('-o',"HostKeyAlias=$HostKeyAlias",'-o','StrictHostKeyChecking=yes')
Write-Host 'Checking the tablet and existing AppLoad. This does not install a launcher or restart its UI.'
$taskArch = & ssh @taskOptions $Tablet 'uname -m'
if ($LASTEXITCODE -ne 0 -or ($taskArch -join '').Trim() -ne 'armv7l') { throw 'The connected tablet must be reMarkable 2 ARM32.' }
$taskRelease = & ssh @taskOptions $Tablet 'cat /etc/os-release'
if ($LASTEXITCODE -ne 0 -or -not ($taskRelease -match '^IMG_VERSION="3\.29\.0\.153"$')) { throw 'The tablet firmware does not match the reviewed version.' }
& ssh @taskOptions $Tablet 'test -f /home/root/xovi/extensions.d/appload.so'
if ($LASTEXITCODE -ne 0) { throw 'AppLoad is missing. See remarkable/INSTALL.md.' }
& .\.venv\Scripts\python.exe scripts/build-remarkable.py --paired
if ($LASTEXITCODE -ne 0) { throw 'App bundle build failed.' }
$taskPackage = Join-Path $taskRoot 'artifacts/remarkable/babblet-appload-paired.zip'
$taskDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskPackage).Hash.ToLowerInvariant()
Write-Host 'Resources are replaced by rename. Close and reload Babblet to activate the update.'
& ssh @taskOptions $Tablet 'mkdir -p /home/root/babblet-install'
if ($LASTEXITCODE -ne 0) { throw 'Could not create staging directory.' }
& scp @taskOptions $taskPackage "${Tablet}:/home/root/babblet-install/babblet-appload-paired.zip"
if ($LASTEXITCODE -ne 0) { throw 'Could not upload the app bundle.' }
$taskStage = 'stage-' + $taskDigest
$taskInstall = "set -eu; cd /home/root/babblet-install; chmod 600 babblet-appload-paired.zip; echo '$taskDigest  babblet-appload-paired.zip' | sha256sum -c -; if test -d /home/root/xovi/exthome/appload/babblet; then cp -a /home/root/xovi/exthome/appload/babblet babblet-backup-`$(date +%s); fi; mkdir -p $taskStage; unzip -o babblet-appload-paired.zip -d $taskStage; chmod -R go-rwx $taskStage/babblet; mkdir -p /home/root/xovi/exthome/appload/babblet; for f in manifest.json resources.rcc icon.png PACKAGE.txt FLAGS-LICENSE; do mv -f $taskStage/babblet/`$f /home/root/xovi/exthome/appload/babblet/`$f; done; chmod -R go-rwx /home/root/xovi/exthome/appload/babblet"
& ssh @taskOptions $Tablet $taskInstall
if ($LASTEXITCODE -ne 0) { throw 'App deployment failed; inspect the remote staging directory.' }
Write-Host 'Installed Babblet. In AppLoad, tap Reload, then Babblet. Start scripts/start-tablet-network.ps1 on the computer.'
Write-Host 'No xochitl restart or firmware change was performed. If AppLoad caches an older resource bundle, close all custom apps and restart the UI explicitly after saving notebooks.'
