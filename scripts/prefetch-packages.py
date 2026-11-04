#!/usr/bin/env python3
"""Batch Arch package payloads through aria2; pacstrap still verifies their signatures."""
import argparse
import base64
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit, unquote

from download import download_many, validate


def repository_signatures(dbpath):
    signatures = {}
    for path in (Path(dbpath) / "sync").glob("*.db"):
        with tarfile.open(path) as archive:
            for entry in archive:
                if entry.isfile() and entry.name.endswith("/desc"):
                    sections = archive.extractfile(entry).read().decode().split("\n\n")
                    fields = {lines[0]: "".join(lines[1:]) for section in sections if (lines := section.splitlines())}
                    if fields.get("%FILENAME%") and fields.get("%PGPSIG%"):
                        signatures[fields["%FILENAME%"]] = base64.b64decode(fields["%PGPSIG%"], validate=True)
    return signatures


def prefetch(config, packages, installed=False, snapshot=None):
    # mkarchiso derives pacstrap's cache from this profile, not /etc/pacman.conf.
    cache = Path(subprocess.check_output(["pacman-conf", "--config", str(config), "CacheDir"],
                                        text=True).splitlines()[0])
    cache.mkdir(parents=True, exist_ok=True)
    # Do not let installed host packages suppress target dependencies or pollute another architecture.
    with tempfile.TemporaryDirectory(prefix="lynux-pacman-db-") as directory:
        cmd = ["pacman", "--config", str(config), "--noconfirm"]
        if installed:
            # Builder setup has already refreshed/upgraded the native system.
            # Resolve only dependencies it still needs, retaining its real DB.
            cmd += ["--needed"]
            dbpath = subprocess.check_output(["pacman-conf", "--config", str(config), "DBPath"], text=True).strip()
        else:
            dbpath = directory
            cmd += ["--dbpath", directory]
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
            if installed and not listing.strip():
                return
            raise ValueError("No validated package URLs returned by pacman")
        download_many(jobs)
        # Cache payloads AND detached signatures. Without these, pacstrap can
        # still invoke XferCommand serially hundreds of times despite a warm cache.
        embedded = repository_signatures(dbpath)
        detached = []
        for url, path, _ in jobs:
            target = path.with_name(path.name + ".sig")
            validate(url + ".sig", target)
            if path.name in embedded:
                target.write_bytes(embedded[path.name])
            else:
                detached.append((url + ".sig", target, None))
        if detached:
            download_many(detached)
        if snapshot:
            snapshot.mkdir(parents=True, exist_ok=False)
            for source in (Path(dbpath) / "sync").iterdir():
                if source.is_file() and source.name.endswith((".db", ".db.sig")):
                    shutil.copy2(source, snapshot / source.name)
        print(f"Prefetched {len(jobs)} package payloads and signatures into {cache}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--installed", action="store_true", help="Prefetch missing native builder dependencies only")
    parser.add_argument("--snapshot", type=Path, help="Keep the exact repository databases used to resolve packages")
    args = parser.parse_args()
    prefetch(args.config, [line.strip() for line in args.packages.read_text().splitlines()
                          if line.strip() and not line.startswith("#")], installed=args.installed, snapshot=args.snapshot)
