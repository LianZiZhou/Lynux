#!/bin/bash
set -euo pipefail
bash /src/scripts/setup-downloads.sh x86_64
pacman -Syu --noconfirm
pacman -S --needed --noconfirm python cryptsetup e2fsprogs util-linux shellcheck dosfstools libisoburn \
  mtools python-pip git npm nodejs gnupg
cd /src
bash tests/check.sh
LYNUX_DISPOSABLE_TEST=1 python tests/integration_state.py
