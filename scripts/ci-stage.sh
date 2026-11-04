#!/bin/bash
# Report actual resource/process activity while retaining a complete stage log.
set -euo pipefail
stage=${1:?stage}; shift
[[ "$stage" =~ ^[a-z0-9-]+$ ]] || exit 2
mkdir -p out
log="out/${ARCH:-native}-${stage}.log"
monitor() {
    trap 'if [[ -n "${sleeper:-}" ]]; then kill "$sleeper" 2>/dev/null || true; fi; exit 0' TERM INT
    while true; do
        sleep 60 &
        sleeper=$!
        wait "$sleeper" || return
        printf '\n[Lynux %s] %s; captured log bytes: %s\n' "$stage" "$(date -u +%FT%TZ)" "$(stat -c %s "$log" 2>/dev/null || echo 0)"
        if [[ -n "${CONTAINER:-}" ]]; then
            timeout 10 docker stats --no-stream --format 'CPU={{.CPUPerc}} memory={{.MemUsage}} disk-IO={{.BlockIO}}' "$CONTAINER" || true
            timeout 10 docker top "$CONTAINER" -eo pid,etime,time,comm || true
            timeout 10 docker exec "$CONTAINER" df -h /build /out || true
        fi
    done
}
monitor &
monitor_pid=$!
trap 'kill "$monitor_pid" 2>/dev/null || true; wait "$monitor_pid" 2>/dev/null || true' EXIT
printf '[Lynux %s] started %s\n' "$stage" "$(date -u +%FT%TZ)"
"$@" 2>&1 | tee "$log"
printf '[Lynux %s] completed %s\n' "$stage" "$(date -u +%FT%TZ)"
