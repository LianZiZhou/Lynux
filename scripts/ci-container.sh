#!/bin/bash
set -euo pipefail
arch=${1:?architecture}
[[ $(uname -m) == "$arch" ]] || exit 1
repo=$(pwd)
mkdir -p out "${RUNNER_TEMP:?}/lynux-keys"
image=archlinux:base-devel
if [[ "$arch" == aarch64 ]]; then
    bash scripts/fetch-alarm-rootfs.sh "$RUNNER_TEMP/archlinuxarm.tar.gz"
    sha256sum "$RUNNER_TEMP/archlinuxarm.tar.gz" > out/aarch64-bootstrap-SHA256SUMS.txt
    image=$(docker import "$RUNNER_TEMP/archlinuxarm.tar.gz")
fi
name="lynux-${arch}-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
docker volume create "$name" >/dev/null
docker run -d --name "$name" --privileged --network host -e LYNUX_ARCH="$arch" -e PYTHONUNBUFFERED=1 \
  -e LYNUX_DOWNLOAD_CONNECTIONS="${LYNUX_DOWNLOAD_CONNECTIONS:-16}" \
  -e LYNUX_DOWNLOAD_JOBS="${LYNUX_DOWNLOAD_JOBS:-8}" \
  -v "$repo:/src:ro" -v "$repo/out:/out" -v "$name:/build" \
  -v "$RUNNER_TEMP/lynux-keys:/keys:ro" "$image" sleep infinity
printf 'container=%s\nvolume=%s\n' "$name" "$name" >> "$GITHUB_OUTPUT"
docker exec "$name" bash /src/scripts/builder-entry.sh --setup-only
