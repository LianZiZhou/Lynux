#!/usr/bin/env python3
"""Batch Arch package payloads through aria2; pacstrap still verifies their signatures."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit, unquote

from download import download_many


def prefetch(config, packages):
    cache = Path(subprocess.check_output(["pacman-conf", "CacheDir"], text=True).splitlines()[0])
    cache.mkdir(parents=True, exist_ok=True)
    # Do not let installed host packages suppress target dependencies or pollute another architecture.
    with tempfile.TemporaryDirectory(prefix="lynux-pacman-db-") as directory:
        cmd = ["pacman", "--config", str(config), "--dbpath", directory, "--noconfirm"]
        subprocess.run([*cmd, "-Sy"], check=True)
        listing = subprocess.check_output([*cmd, "-Sp", "--print-format", "%h %l", *packages], text=True)
        jobs = []
        for line in listing.splitlines():
            match = re.fullmatch(r"([0-9a-f]{64}) (https://\S+)", line)
            if match:
                checksum, url = match.groups()
                name = Path(unquote(urlsplit(url).path)).name
                jobs.append((url, cache / name, "sha-256=" + checksum))
        if not jobs:
            raise ValueError("No validated package URLs returned by pacman")
        download_many(jobs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    args = parser.parse_args()
    prefetch(args.config, [line.strip() for line in args.packages.read_text().splitlines()
                          if line.strip() and not line.startswith("#")])
