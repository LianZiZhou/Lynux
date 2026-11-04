#!/bin/bash
# EDK2 ArmVirt's distribution default does not enable Secure Boot; build the test firmware explicitly.
set -euo pipefail
[[ $(uname -m) == aarch64 ]] || { echo 'ARM firmware builds run on the native ARM builder.' >&2; exit 1; }
commit=$(cat "${LYNUX_LOCK_DIR:-/src/work/lock}/edk2.commit")
[[ "$commit" =~ ^[a-f0-9]{40}$ ]] || exit 1
mkdir -p /build/firmware /usr/share/qemu/firmware
cache=/out/arm-firmware
if [[ -f "$cache/edk2.commit" ]] && [[ $(cat "$cache/edk2.commit") == "$commit" ]]; then
    (cd "$cache" && sha256sum --strict -c SHA256SUMS)
    cp "$cache/QEMU_CODE.fd" "$cache/QEMU_VARS.fd" /build/firmware/
    cp "$cache/40-lynux-aarch64-secure.json" /usr/share/qemu/firmware/
    echo "Restored verified ARM test firmware for EDK2 $commit"
    exit 0
fi
packages=(base-devel python git acpica nasm openssl)
printf '%s\n' "${packages[@]}" > /build/firmware-packages.txt
python /src/scripts/prefetch-packages.py --config /etc/pacman.conf --packages /build/firmware-packages.txt --installed
pacman -S --needed --noconfirm "${packages[@]}"
git init /build/edk2
git -C /build/edk2 fetch --depth 1 https://github.com/tianocore/edk2.git "$commit"
git -C /build/edk2 checkout --detach FETCH_HEAD
git -C /build/edk2 submodule update --init --recursive --depth 1 --jobs 4
cd /build/edk2
make -C BaseTools -j"$(nproc)"
# Upstream setup does not support nounset.
set +u
# shellcheck disable=SC1091
source edksetup.sh
set -u
toolchain=GCC
if ! grep -q '^\*_GCC_AARCH64_CC_PATH' BaseTools/Conf/tools_def.template; then toolchain=GCC5; fi
export GCC_AARCH64_PREFIX='' GCC5_AARCH64_PREFIX=''
build -n "$(nproc)" -a AARCH64 -t "$toolchain" -p ArmVirtPkg/ArmVirtQemu.dsc -b RELEASE \
  -D SECURE_BOOT_ENABLE=TRUE -D FD_SIZE_IN_MB=3
mkdir -p /build/firmware /usr/share/qemu/firmware
python - "$toolchain" <<'PY'
import json
from pathlib import Path
import sys
base = Path('/build/edk2/Build/ArmVirtQemu-AArch64') / ('RELEASE_' + sys.argv[1]) / 'FV'
for source, target in [('QEMU_EFI.fd', 'QEMU_CODE.fd'), ('QEMU_VARS.fd', 'QEMU_VARS.fd')]:
    payload = (base / source).read_bytes()
    with (Path('/build/firmware') / target).open('wb') as stream:
        stream.write(payload)
        stream.write(b'\xff' * (64 * 1024 ** 2 - len(payload)))
descriptor = {
    'description': 'Lynux test firmware: pinned EDK2 ArmVirt with Secure Boot',
    'interface-types': ['uefi'], 'features': ['secure-boot'],
    'targets': [{'architecture': 'aarch64', 'machines': ['virt-*']}],
    'mapping': {'device': 'flash',
                'executable': {'filename': '/build/firmware/QEMU_CODE.fd', 'format': 'raw'},
                'nvram-template': {'filename': '/build/firmware/QEMU_VARS.fd', 'format': 'raw'}}
}
Path('/usr/share/qemu/firmware/40-lynux-aarch64-secure.json').write_text(json.dumps(descriptor))
PY
mkdir -p "$cache"
cp /build/firmware/QEMU_CODE.fd /build/firmware/QEMU_VARS.fd "$cache/"
cp /usr/share/qemu/firmware/40-lynux-aarch64-secure.json "$cache/"
printf '%s\n' "$commit" > "$cache/edk2.commit"
(cd "$cache" && sha256sum QEMU_CODE.fd QEMU_VARS.fd 40-lynux-aarch64-secure.json edk2.commit > SHA256SUMS)
