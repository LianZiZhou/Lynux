#!/usr/bin/env python3
"""Use pip for resolution, aria2 for wheel payloads, and pip's offline installer."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

from download import download_many


def install(requirements):
    if not requirements:
        raise ValueError("Specify at least one Python tooling requirement")
    with tempfile.TemporaryDirectory(prefix="lynux-wheels-") as directory:
        temp = Path(directory)
        report = temp / "report.json"
        subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
                        "--only-binary=:all:", "--report", str(report), *requirements], check=True)
        jobs = []
        for package in json.loads(report.read_text())["install"]:
            source = package["download_info"]
            url = source["url"]
            name = Path(unquote(urlsplit(url).path)).name
            if not name.endswith(".whl"):
                raise ValueError("CI tooling requires a published wheel")
            jobs.append((url, temp / name, "sha-256=" + source["archive_info"]["hashes"]["sha256"]))
        download_many(jobs)
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(temp),
                        *requirements], check=True)


if __name__ == "__main__":
    install(sys.argv[1:])
