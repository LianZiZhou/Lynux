#!/usr/bin/env python3
"""Re-run boot checks against an existing artifact, without signing keys or publication."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def reverify(directory, checks="all"):
    meta = json.loads((directory / "x86_64-build.json").read_text())
    name = meta["iso"]
    if Path(name).name != name or not name.endswith("-x86_64-signed.iso") or meta["arch"] != "x86_64":
        raise ValueError("Invalid ISO artifact name/architecture")
    iso = directory / name
    with iso.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != meta["sha256"]:
            raise ValueError("ISO differs from build metadata")
    if checks == "all":
        work = Path("/build/reverify-secure")
        work.mkdir(parents=True, exist_ok=False)
        subprocess.run(["xorriso", "-osirrox", "on", "-indev", str(iso), "-extract",
                        "/EFI/Linux/lynux.efi", str(work / "lynux.efi")], check=True)
        subprocess.run([sys.executable, "/src/tests/image_matrix.py", "--iso", str(iso), "--arch", "x86_64",
                        "--cert", str(directory / "lynux.crt"), "--secure-work", str(work),
                        "--report-dir", str(directory)], check=True)
    subprocess.run([sys.executable, "/src/tests/ventoy_boot.py", "--iso", str(iso), "--arch", "x86_64",
                    "--report", str(directory / "x86_64-ventoy.json")], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--checks", choices=("all", "ventoy"), default="all")
    reverify(**vars(parser.parse_args()))
