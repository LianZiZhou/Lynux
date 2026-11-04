#!/bin/bash
set -euo pipefail
# pacman owns the .part -> final rename and verifies package signatures after download.
url=${1:?URL}; output=${2:?output}
fresh=()
case "$url" in *.db|*.db.sig|*.files|*.files.sig) fresh=(--fresh);; esac
exec /usr/bin/python /usr/local/lib/lynux/download.py "$url" "$output" "${fresh[@]}"
