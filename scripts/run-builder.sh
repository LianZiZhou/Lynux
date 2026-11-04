#!/bin/bash
# Usage: scripts/run-builder.sh x86_64 iso --arch x86_64 --work /build/work ...
set -euo pipefail
arch=${1:?architecture required}; shift
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $(uname -m) == "$arch" ]] || { echo 'Use a native runner for this architecture.' >&2; exit 1; }
lock_dir=/src/work/lock
read_lock=false
for argument in "$@"; do
    if [[ "$read_lock" == true ]]; then lock_dir=$argument; read_lock=false; continue; fi
    case "$argument" in
        --lock) read_lock=true ;;
        --lock=*) lock_dir=${argument#--lock=} ;;
    esac
done
[[ "$read_lock" == false ]] || { echo '--lock requires a directory' >&2; exit 2; }
[[ "$lock_dir" == /* ]] || lock_dir="/src/$lock_dir"
mkdir -p "$repo/out"
case "$arch" in
  x86_64) image=archlinux:base-devel ;;
  aarch64)
    # Official Arch Linux ARM rootfs; record its bytes rather than trusting a floating third-party image.
    mkdir -p "$repo/work/bootstrap"
    python3 "$repo/scripts/download.py" \
      "${ALARM_ROOTFS_URL:-https://mirrors.tuna.tsinghua.edu.cn/archlinuxarm/os/ArchLinuxARM-aarch64-latest.tar.gz}" \
      "$repo/work/bootstrap/archlinuxarm.tar.gz" --fresh
    sha256sum "$repo/work/bootstrap/archlinuxarm.tar.gz" > "$repo/work/bootstrap/SHA256SUMS"
    image=$(docker import "$repo/work/bootstrap/archlinuxarm.tar.gz") ;;
  *) echo 'Unsupported architecture' >&2; exit 2 ;;
esac
# Build products live in a Linux volume: file modes, device nodes and mounts must not use NTFS.
volume="lynux-build-${arch}-$(date +%s)-$$"
docker volume create "$volume" >/dev/null
echo "Build volume: $volume (retained for signing/testing; remove explicitly after use)"
docker run --rm --privileged --network host -w /src \
  -v "$repo:/src:ro" -v "$volume:/build" -v "$repo/out:/out" -v "$repo/out:/src/out" \
  -e LYNUX_ARCH="$arch" \
  -e LYNUX_LOCK_DIR="$lock_dir" \
  -e LYNUX_DOWNLOAD_CONNECTIONS="${LYNUX_DOWNLOAD_CONNECTIONS:-16}" \
  -e LYNUX_DOWNLOAD_JOBS="${LYNUX_DOWNLOAD_JOBS:-8}" \
  "$image" /bin/bash /src/scripts/builder-entry.sh "$@"
