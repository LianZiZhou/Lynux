#!/bin/bash
# Free disk on a disposable GitHub-hosted runner by deleting preinstalled SDKs the build never uses.
# Some hosted runners have a 72 GB disk; the x86_64 build needs about 27 GB on top of the image.
set -euo pipefail
if [[ "${RUNNER_ENVIRONMENT:-}" != github-hosted ]]; then
    echo "Not a GitHub-hosted runner; leaving its tools alone." >&2
    exit 1
fi
echo "Before:"
df -h /
paths=(
    /usr/share/dotnet /usr/local/lib/android /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache
    /usr/local/share/powershell /usr/local/share/chromium /usr/local/lib/node_modules
    /usr/share/swift /usr/lib/jvm /usr/share/kotlinc /usr/local/julia* /usr/share/miniconda
    /opt/az /opt/microsoft /opt/google /opt/pipx /opt/mssql-tools /usr/lib/google-cloud-sdk
    /usr/local/aws-cli /usr/local/aws-sam-cli /usr/local/share/vcpkg /usr/local/share/boost
)
for path in "${paths[@]}"; do
    if [[ -e "$path" ]]; then
        sudo rm -rf -- "$path" &
    fi
done
wait
# Hosted images may ship cached Docker images; the builder pulls or imports its own afterwards.
docker image prune --all --force > /dev/null || true
echo "After:"
df -h
