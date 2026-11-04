#!/bin/bash
set -euo pipefail
arch=${LYNUX_ARCH:-$(uname -m)}
if [[ "$arch" == aarch64 ]]; then
    pacman-key --init
    pacman-key --populate archlinuxarm
fi
bash /src/scripts/setup-downloads.sh "$arch"
mkdir -p /build/pacman-cache
sed -i '/^CheckSpace/a CacheDir = /build/pacman-cache' /etc/pacman.conf
pacman -Syu --noconfirm
pacman -S --needed --noconfirm arch-install-scripts squashfs-tools dosfstools libisoburn mtools \
  e2fsprogs parted exfatprogs grub python python-yaml python-docutils git make gnupg npm nodejs systemd-ukify sbsigntools cpio zstd \
  qemu-system-x86 qemu-system-aarch64 qemu-hw-display-virtio-gpu-pci edk2-ovmf edk2-armvirt virt-firmware openssl
if [[ "$arch" == x86_64 ]]; then pacman -S --needed --noconfirm syslinux; fi
# ARM support varies in packaged archiso; pin one upstream commit in the shared resolver job.
commit=$(cat "${LYNUX_LOCK_DIR:-/src/work/lock}/archiso.commit")
[[ "$commit" =~ ^[a-f0-9]{40}$ ]] || exit 1
git init /build/archiso-source
git -C /build/archiso-source fetch --depth 1 --tags https://github.com/archlinux/archiso.git "$commit"
git -C /build/archiso-source checkout --detach FETCH_HEAD
make -C /build/archiso-source install PREFIX=/usr
if [[ "${1:-}" == --setup-only ]]; then exit 0; fi
python /src/build "$@"
