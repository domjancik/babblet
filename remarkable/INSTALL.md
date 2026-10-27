# Install Babblet on reMarkable 2

Babblet is a frontend-only QML AppLoad application. Recognition and translation stay on the Windows computer. The tablet receives six fixed conversation rows over an encrypted USB SSH reverse tunnel.

## Compatibility

The tested combination is **reMarkable 2, firmware 3.29.0.153, ARM32**, with the device's Qt 6.10.3, XOVI 0.3.3, qt-resource-rebuilder v19-23052026 and AppLoad 0.6.0. The helpers check the exact firmware and architecture; do not bypass those checks for another version. Paper Pro and other firmware versions are not validated.

This is an independent developer application that modifies the running tablet UI. Save notebook work before launcher activation. Activation temporarily restarts the stock UI; ordinary Babblet updates do not. No boot autostart, Wi-Fi SSH, firewall rule or notebook modification is installed by these helpers.

## 1. Prepare the computer and SSH

Complete the [Windows installation](../README.md#install-on-windows) first. Connect the tablet by USB, keep it awake, and configure developer/SSH access using the tablet's own credentials and the upstream launcher documentation.

The tablet's USB address is normally `10.11.99.1`. It is the **tablet**, not the computer. Connect interactively once, verifying the host fingerprint before accepting it:

```powershell
ssh root@10.11.99.1
```

The desktop launcher needs passwordless key authentication; it does not store tablet passwords. If you do not already have an SSH key, create one with `ssh-keygen -t ed25519`, then install its public key using the tablet password:

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | ssh root@10.11.99.1 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys'
ssh -o BatchMode=yes root@10.11.99.1 'uname -m'
```

The second command should print `armv7l` without prompting. Keep the private key on your computer; do not copy it into this repository. SSH host-key mismatches fail instead of being silently accepted.

## 2. Install launcher prerequisites if missing

If XOVI/AppLoad are already installed, review their compatibility and skip this installation step. The helper refuses to replace an existing `/home/root/xovi` tree.

Prepare and review the pinned downloads without writing to the tablet:

```powershell
powershell -NoProfile -File scripts/install-remarkable-framework.ps1
```

Then install the prerequisite files:

```powershell
powershell -NoProfile -File scripts/install-remarkable-framework.ps1 -Install
```

The prepared archive contains only the required active extensions. It verifies published upstream SHA-256 values, checks the tablet firmware, and installs under `/home/root/xovi`. It does not activate the launcher or restart the UI.

| Component | Pinned artifact | SHA-256 |
| --- | --- | --- |
| XOVI 0.3.3 | `xovi-arm32.so` | `2878d88da2dcb37dcf5533fa78aeeb5cc933eb8c7e5b9041213a4e135a7fff14` |
| qt-resource-rebuilder v19-23052026 | `xovi-arm32.tar.gz` | `9aa00537ad41e9be0c3151992bfc25106465318cf5bb4c41cf59b3ddd4866377` |
| AppLoad 0.6.0 | `appload-arm32.tar.gz` | `25aa54735742ea63c0a043cba5496987dd4ca742d8b3fc26a21b7368372bf44f` |

See [AppLoad](https://github.com/asivery/rm-appload) and [the Qt integration notes](../docs/REMARKABLE_QT.md) for upstream context. Download URLs and hash receipts are generated under `artifacts/remarkable/prerequisites/`.

## 3. Activate AppLoad

Save work, close custom apps, keep the tablet awake, and be present to unlock it. Run the separate activation helper:

```powershell
scp .\remarkable\activate-launcher.sh root@10.11.99.1:/home/root/babblet-install/activate-launcher.sh
ssh root@10.11.99.1 'bash /home/root/babblet-install/activate-launcher.sh'
ssh root@10.11.99.1 'journalctl -fu babblet-launcher-setup'
```

The helper rebuilds the Qt resource hashtable and activates XOVI/AppLoad through the upstream scripts. The initial rebuild can take a minute or more and may wait for the tablet to be unlocked. It temporarily stops/restarts the stock UI and creates volatile systemd overrides; its cleanup restores xochitl after completion or failure. Do not repeatedly run the stock/start scripts in quick succession.

Recovery: a reboot clears the temporary service overrides and returns to stock mode. While SSH is available, `/home/root/xovi/stock` is upstream's return-to-stock command. Preserve `/home/root/babblet-install` until the launcher is working.

**Firmware-specific diagnostic limitation:** do not run `/usr/bin/screenshot` on the tested 3.29.0.153 build. Its legacy helper sent SIGUSR2 and terminated xochitl during testing. Use on-device observation, QML logs and connection metadata instead.

## 4. Pair and install Babblet

Start **Babblet** from the Windows Start menu, then deploy its paired resources:

```powershell
powershell -NoProfile -File scripts/deploy-remarkable.ps1
```

The helper generates a local bearer token, builds a private paired RCC bundle, verifies its checksum on the tablet, backs up the old app directory, and replaces files by atomic rename. It installs into `/home/root/xovi/exthome/appload/babblet` and refuses missing AppLoad or mismatched firmware. It does not restart the stock UI.

On the tablet, open **sidebar → AppLoad → Reload → Babblet**. Swipe down from the top edge to close it. On subsequent updates, close Babblet, redeploy, and reload it. AppLoad can cache resources until the app is closed and reopened.

**Paired ZIPs are private.** `artifacts/remarkable/babblet-appload-paired.zip` contains the token inside compiled QML resources. Do not commit or share it. To build a shareable, unpaired bundle:

```powershell
.venv\Scripts\python.exe scripts/build-remarkable.py --output artifacts/remarkable/public
```

An unpaired bundle cannot connect until it is rebuilt with the receiving computer's own pairing token.

## 5. Connect over USB

The Windows launcher attempts USB automatically. After plugging the tablet in, press **Start / reconnect** if necessary. To run transport manually while the computer server is listening:

```powershell
powershell -NoProfile -File scripts/start-tablet-network.ps1
```

Keep that terminal open. Ctrl+C disconnects its SSH tunnel. The inference/debug server stays on computer loopback `127.0.0.1:8090`. A separate bearer-authenticated gateway on computer loopback `127.0.0.1:8092` exposes only `/v1/display` and `/v1/languages`; it does not expose recordings or the inspector. The reverse SSH tunnel forwards tablet loopback port 8092 to that gateway.

The tablet's `http://127.0.0.1:8092` works only while the SSH tunnel is up. Disconnecting USB disconnects the tablet frontend; the computer can continue translating. These instructions do not enable wireless SSH or public LAN listeners. A firmware update or reboot can require the launcher activation step again.

## Reading controls

- The rotate control switches portrait/landscape. The speech bubble shows or hides original speech.
- **Readers** cycles through opposite columns, stacked panels, four panels and normal columns. A panel's language button and flip control rotate with that panel. The central divider separates readers.
- A small dot marks the newest row. The next occupied row to be replaced fades to 45%. Logical FIFO indices stay intact when a panel flips.
- One ink-flower graphic changes at actual processing-stage boundaries. There is no movement animation or scrolling transcript.
- The large language seal opens the picker from any view. All 38 display languages fit without scrolling: five columns in portrait, eight in landscape. Flag toggles save immediately.
- **Read/Hear** links expected speech to display languages by default. The chain control allows independent speaking-language hints.
- Tap the italic wordmark to reveal the Close control.

Only refined/final speech is published to the tablet. Changed translations replace their own cells; late results cannot overwrite a newer row. The tablet retains six presentation rows, independently of browser discard. No transcript archive or disk cache is created. Bundled Noto fonts cover every advertised native language label, including CJK regional faces and the required Indic, Southeast Asian and Tibetan scripts.

## Local validation and troubleshooting

```powershell
.venv\Scripts\python.exe scripts/build-remarkable.py
.venv\Scripts\python.exe scripts/check-remarkable-ui.py
.venv\Scripts\python.exe scripts/check-remarkable-network.py
.venv\Scripts\python.exe scripts/check-remarkable-fonts.py
```

These use the desktop Qt runtime and synthetic content. They test unchanged-poll redraw avoidance, fixed row updates, picker geometry, independent reader rotations, actual Qt XHR and bundled glyph coverage. `artifacts/remarkable/` previews are desktop renders, not tablet screenshots.

If the tablet is blank or disconnected, verify the version gate, AppLoad activation, passwordless USB SSH, computer server and USB tunnel. Inspect QML errors with `journalctl -u xochitl --since "-5 minutes"` over SSH. The tablet's stripped Qt build lacks desktop accessibility attached objects, so the frontend deliberately avoids `Accessible.*`. The RCC build uses format version 2 without compression and Qt Quick 2.15 imports.

[Riddle](https://github.com/MaximeRivest/riddle) informed the preference for changed-region updates and portable installation. Its native rendering backend and Paper Pro binaries were not copied into this ARM32 QML frontend.
