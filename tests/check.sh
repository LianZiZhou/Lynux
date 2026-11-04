#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -m compileall -q runtime scripts tests
python3 -m unittest discover -s tests -p 'test_*.py' -v
for file in scripts/*.sh tests/*.sh overlay/usr/local/lib/lynux/* overlay/usr/local/bin/* boot/install-* boot/hook-*; do bash -n "$file"; done
if command -v shellcheck >/dev/null; then
    shellcheck -S warning scripts/*.sh tests/*.sh overlay/usr/local/lib/lynux/* overlay/usr/local/bin/*
fi
