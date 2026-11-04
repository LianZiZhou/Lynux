#!/bin/bash
set -euo pipefail
arch=${1:-x86_64}
[[ "$arch" == x86_64 || "$arch" == aarch64 ]] || exit 2
bash /src/scripts/setup-downloads.sh "$(uname -m)"
cp "/src/config/pacman.$arch.conf" /etc/pacman.conf
dbpath=$(mktemp -d)
trap 'rm -rf -- "$dbpath"' EXIT
pacman --dbpath "$dbpath" -Sy --noconfirm
missing=0
while read -r package; do
    [[ -z "$package" || "$package" == \#* ]] && continue
    if ! pacman --dbpath "$dbpath" -Sp --print-format '%n' "$package" >/dev/null; then
        echo "MISSING: $package"
        missing=1
    fi
done < <(cat /src/config/packages.common "/src/config/packages.$arch")
exit "$missing"
