#!/bin/bash
# Explicit, interactive launcher activation AFTER installation is approved.
# systemd owns the operation so an SSH disconnect cannot strand the stock UI.
# Run on the tablet only after saving notebooks and reviewing INSTALL.md.
set -euo pipefail
if [[ "${1:-}" != "--inside-systemd" ]]; then
    test "$(uname -m)" = armv7l
    grep -q 'IMG_VERSION="3.29.0.153"' /etc/os-release
    test -f /home/root/xovi/extensions.d/appload.so
    echo 'This will briefly restart the tablet UI and build its Qt resource table.'
    echo 'Keep the tablet awake and unlock it if prompted. Reboot returns to stock mode.'
    systemd-run --unit=babblet-launcher-setup --collect \
        --property='ExecStopPost=-/bin/systemctl start xochitl' \
        /bin/bash "$(readlink -f "$0")" --inside-systemd
    echo 'Watch with: journalctl -fu babblet-launcher-setup'
    exit 0
fi
trap '/bin/systemctl start xochitl' EXIT
printf '\n' | /bin/bash /home/root/xovi/rebuild_hashtable
test -s /home/root/xovi/exthome/qt-resource-rebuilder/hashtab
/bin/bash /home/root/xovi/start
systemctl is-active --quiet xochitl
