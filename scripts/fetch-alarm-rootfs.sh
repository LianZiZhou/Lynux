#!/bin/bash
# Download the official Arch Linux ARM rootfs and verify its upstream signature.
# Usage: fetch-alarm-rootfs.sh OUTPUT_TARBALL
set -euo pipefail
out=${1:?output tarball}
here=$(cd "$(dirname "$0")" && pwd)
# Arch Linux ARM Build System <builder@archlinuxarm.org>, the key the archlinuxarm keyring trusts.
fingerprint=68B3537F39A313B3E574D06777193F152BDBE6A6
name=ArchLinuxARM-aarch64-latest.tar.gz
if [[ -n "${ALARM_ROOTFS_URL:-}" ]]; then
    urls=("$ALARM_ROOTFS_URL")
else
    # Official mirrors with valid HTTPS. The GeoIP host's certificate doesn't match its name.
    urls=("https://fl.us.mirror.archlinuxarm.org/os/$name"
          "https://ca.us.mirror.archlinuxarm.org/os/$name"
          "https://de3.mirror.archlinuxarm.org/os/$name")
fi
keyring=$(mktemp -d)
trap 'rm -rf "$keyring"' EXIT
gpg --homedir "$keyring" --batch --quiet --import "$here/../config/keys/archlinuxarm-build.asc"
for url in "${urls[@]}"; do
    if python3 "$here/download.py" "$url" "$out" --fresh && python3 "$here/download.py" "$url.sig" "$out.sig" --fresh; then
        status=$(gpg --homedir "$keyring" --batch --status-fd 1 --verify "$out.sig" "$out" 2>/dev/null || true)
        if grep -q "^\[GNUPG:\] VALIDSIG $fingerprint " <<< "$status"; then
            echo "Verified the Arch Linux ARM rootfs signature ($url)"
            exit 0
        fi
        echo "Signature check failed: $url" >&2
    fi
    echo "Trying the next mirror" >&2
done
echo "No mirror gave a correctly signed Arch Linux ARM rootfs" >&2
exit 1
