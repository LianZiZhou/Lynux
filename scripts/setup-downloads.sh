#!/bin/bash
# Run inside an Arch builder. The first aria2/Python bootstrap uses pacman's own transport.
set -euo pipefail
arch=${1:-$(uname -m)}
if ! command -v aria2c >/dev/null || ! command -v python >/dev/null; then
    sed '/^XferCommand/d' "/src/config/pacman.${arch}.conf" > /etc/pacman.conf
    # pacman's own downloader gives up on a mirror after a 10-second stall; retry the whole step.
    for attempt in 1 2 3; do
        pacman -Syu --needed --noconfirm aria2 python && break
        [[ $attempt == 3 ]] && exit 1
        echo "Package bootstrap failed (attempt $attempt of 3); retrying" >&2
        sleep 10
    done
fi
install -Dm755 /src/scripts/pacman-download.sh /usr/local/lib/lynux/pacman-download
install -Dm644 /src/scripts/download.py /usr/local/lib/lynux/download.py
cp "/src/config/pacman.${arch}.conf" /etc/pacman.conf
