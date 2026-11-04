#!/bin/bash
set -euo pipefail
# pacman owns the .part -> final rename and verifies package signatures after download.
url=${1:?URL}; output=${2:?output}
printf 'pacman transfer: %s -> %s\n' "${url##*/}" "${output##*/}" >&2
if [[ -n "${LYNUX_PACMAN_DB_SNAPSHOT:-}" ]]; then
    case "$url" in
        *.db|*.db.sig)
            source="${LYNUX_PACMAN_DB_SNAPSHOT}/${url##*/}"
            # Return failure for absent signatures; pacman still enforces SigLevel.
            [[ -f "$source" ]] || exit 1
            cp -- "$source" "$output"
            exit 0
            ;;
    esac
fi
export LYNUX_DOWNLOAD_TIMEOUT=${LYNUX_DOWNLOAD_TIMEOUT:-300}
case "$url" in *.sig) export LYNUX_DOWNLOAD_TIMEOUT=60;; esac
fresh=()
case "$url" in *.db|*.db.sig|*.files|*.files.sig) fresh=(--fresh);; esac
exec /usr/bin/python /usr/local/lib/lynux/download.py "$url" "$output" "${fresh[@]}"
