#!/bin/bash
set -euo pipefail
arch=${1:?architecture}
work=${2:?build directory}
out=${3:?report directory}
[[ "$arch" == x86_64 || "$arch" == aarch64 ]] || exit 2
test -f "$work/build.json"
root="$work/archiso/$arch/airootfs"
install -Dm644 /src/tests/provider_smoke.py "$root/usr/local/lib/lynux/provider-smoke.py"
cleanup() {
    if [[ -f "$root/usr/share/lynux/provider-smoke-report.json" ]]; then
        cp "$root/usr/share/lynux/provider-smoke-report.json" "$out/$arch-provider-smoke.json"
    fi
    rm -f "$root/usr/local/lib/lynux/provider-smoke.py" "$root/usr/share/lynux/provider-smoke-report.json"
}
trap cleanup EXIT
arch-chroot "$root" unshare --net /bin/bash -c \
  'ip link set lo up; python /usr/local/lib/lynux/provider-smoke.py --report /usr/share/lynux/provider-smoke-report.json'
python - "$root/usr/share/lynux/provider-smoke-report.json" "$work/archiso/iso/arch/$arch/airootfs.sfs" <<'PY'
import hashlib, json, sys
from pathlib import Path
path=Path(sys.argv[1]); report=json.loads(path.read_text())
with open(sys.argv[2],'rb') as stream:
    report['rootfs_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
PY
