#!/usr/bin/env python3
"""Shared aria2 transport. Callers retain signature verification and version resolution."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


def options():
    connections = int(os.environ.get("LYNUX_DOWNLOAD_CONNECTIONS", "16"))
    parallel = int(os.environ.get("LYNUX_DOWNLOAD_JOBS", "8"))
    if not 1 <= connections <= 16 or not 1 <= parallel <= 32:
        raise ValueError("Download connections must be 1..16; jobs must be 1..32")
    return ["aria2c", "--no-conf=true", f"--max-connection-per-server={connections}",
            f"--split={connections}", f"--max-concurrent-downloads={parallel}", "--min-split-size=1M",
            "--file-allocation=none", "--auto-file-renaming=false", "--allow-overwrite=true",
            "--max-tries=5", "--retry-wait=3", "--connect-timeout=20", "--timeout=60",
            "--lowest-speed-limit=16K", "--check-certificate=true", "--enable-rpc=false",
            "--follow-torrent=false", "--follow-metalink=false", "--summary-interval=10",
            "--console-log-level=warn", "--download-result=hide",
            "--enable-color=false", "--show-console-readout=false"]


def validate(url, path, checksum=None):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or any(c in url for c in "\r\n\t"):
        raise ValueError("Downloads require an HTTPS URL without control characters")
    if any(c in str(path) for c in "\r\n\t"):
        raise ValueError("Invalid download path")
    if path.is_symlink():
        raise ValueError("Refusing a symlink download destination")
    if checksum and not re.fullmatch(r"(sha-256=[0-9a-f]{64}|sha-512=[0-9a-f]{128}|sha-1=[0-9a-f]{40})", checksum):
        raise ValueError("Invalid expected digest")


def verify(path, checksum):
    if checksum:
        algorithm, expected = checksum.split("=", 1)
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, algorithm.replace("-", "")).hexdigest()
        if actual != expected:
            raise ValueError(f"Download checksum mismatch: {path.name}")


def cached(path, checksum):
    if not checksum or not path.is_file() or path.with_name(path.name + ".aria2").exists():
        return False
    try:
        verify(path, checksum)
        return True
    except ValueError:
        return False


def download(url, path, checksum=None, fresh=False):
    path = Path(path).absolute()
    validate(url, path, checksum)
    if not fresh and cached(path, checksum):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [*options(), f"--continue={'false' if fresh else 'true'}", "--dir", str(path.parent),
           "--out", path.name]
    if checksum:
        cmd += [f"--checksum={checksum}", "--check-integrity=true"]
    command = [*cmd, url]
    if urlsplit(url).path.endswith((".db.sig", ".files.sig")):
        # Keep the failure status: pacman decides whether a database signature
        # is optional. Do not print aria2's large ERROR block for an absent one.
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode == 3:
            print(f"Repository database signature not published: {url}", file=sys.stderr)
        elif result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        result.check_returncode()
    else:
        subprocess.run(command, check=True)
    verify(path, checksum)
    return path


def fetch(url):
    # Mutable metadata must never reuse an earlier weekly response or resume against a newer one.
    with tempfile.TemporaryDirectory(prefix="lynux-fetch-") as folder:
        return download(url, Path(folder) / "response", fresh=True).read_bytes()


def download_many(jobs):
    """jobs: iterable of (https_url, destination, aria2_checksum), all immutable artifacts."""
    entries = []
    pending = []
    for url, path, checksum in jobs:
        path = Path(path).absolute()
        validate(url, path, checksum)
        if cached(path, checksum):
            continue
        pending.append((url, path, checksum))
        path.parent.mkdir(parents=True, exist_ok=True)
        entries.append(f"{url}\n  dir={path.parent}\n  out={path.name}\n  checksum={checksum}\n")
    if not entries:
        return
    subprocess.run([*options(), "--continue=true", "--check-integrity=true", "--input-file=-"],
                   input="".join(entries), text=True, check=True)
    for _, path, checksum in pending:
        verify(Path(path), checksum)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    try:
        download(args.url, args.output, f"sha-256={args.sha256}" if args.sha256 else None, args.fresh)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from None
