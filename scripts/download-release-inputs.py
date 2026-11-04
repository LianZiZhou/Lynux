#!/usr/bin/env python3
"""Fetch persistent Release/S3 inputs for verification, without Actions artifacts."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import quote, unquote, urljoin, urlsplit

from download import download, verify

ROOT = Path(__file__).resolve().parents[1]


def release_iso_link(release, arch):
    matches = re.findall(r"\[" + re.escape(arch) + r" ISO\]\((https://[^\s)]+)\)", release["body"])
    if len(matches) != 1:
        raise ValueError("Release must contain one matching HTTPS ISO link")
    return matches[0]


def iso_url(release, meta, arch):
    name = meta["iso"]
    if meta["arch"] != arch or Path(name).name != name or not name.endswith(f"-{arch}-signed.iso"):
        raise ValueError("Invalid release image metadata")
    url = release_iso_link(release, arch)
    if Path(unquote(urlsplit(url).path)).name != name:
        raise ValueError("Release ISO link does not match the signed metadata")
    return url


def extract_lock(archive, destination):
    with tempfile.TemporaryDirectory(prefix="lynux-release-lock-") as directory:
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            for member in members:
                parts = PurePosixPath(member.name).parts
                if (not parts or parts[0] != "dependency-lock" or ".." in parts
                        or not (member.isfile() or member.isdir())):
                    raise ValueError("Unsafe dependency lock archive member")
            bundle.extractall(directory, members=members, filter="data")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(Path(directory) / "dependency-lock", destination)


def prepare(release, arch, out, lock, metadata_only=False):
    if release.get("draft") or arch not in ("x86_64", "aarch64"):
        raise ValueError("A published release and supported architecture are required")
    assets = {asset["name"]: asset["browser_download_url"] for asset in release["assets"]}
    link = release_iso_link(release, arch)

    def asset_url(name):
        if name not in assets:
            raise ValueError(f"Missing release asset: {name}")
        # The publisher mirrors every release asset beside the ISO on S3.
        return urljoin(link, quote(name, safe=""))

    out.mkdir(parents=True, exist_ok=True)
    for name in ("lynux.crt", "lynux.cer", "SHA256SUMS", "SHA256SUMS.sig"):
        download(asset_url(name), out / name, fresh=True)
    certificate = subprocess.check_output(["openssl", "x509", "-in", str(out / "lynux.crt"), "-outform", "DER"])
    if not any(certificate == path.read_bytes() for path in (ROOT / "docs/keys").glob("*.cer")):
        raise ValueError("Release certificate is not in this repository's trusted certificate catalog")
    if certificate != (out / "lynux.cer").read_bytes():
        raise ValueError("PEM and DER certificates differ")
    public = subprocess.check_output(["openssl", "x509", "-in", str(out / "lynux.crt"), "-pubkey", "-noout"])
    (out / "release-public.pem").write_bytes(public)
    subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(out / "release-public.pem"),
                    "-signature", str(out / "SHA256SUMS.sig"), str(out / "SHA256SUMS")], check=True)
    sums = {}
    for line in (out / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match or match[2] in sums:
            raise ValueError("Invalid checksum manifest")
        sums[match[2]] = match[1]
    for name in ("lynux.crt", "lynux.cer"):
        verify(out / name, "sha-256=" + sums[name])
    for name in (f"{arch}-build.json", "dependency-lock.tar.gz"):
        download(asset_url(name), out / name, "sha-256=" + sums[name])
    meta = json.loads((out / f"{arch}-build.json").read_text())
    if not meta.get("signed") or release["tag_name"] != "v" + meta["version"]:
        raise ValueError("Release tag does not identify the signed image version")
    url = iso_url(release, meta, arch)
    if meta["sha256"] != sums[meta["iso"]] or meta["certificate_sha256"] != hashlib.sha256(certificate).hexdigest():
        raise ValueError("Image metadata disagrees with the signed manifest")
    extract_lock(out / "dependency-lock.tar.gz", lock)
    if not metadata_only:
        download(url, out / meta["iso"], "sha-256=" + meta["sha256"])
    print(f"Verified release {release['tag_name']} inputs for {arch}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--arch", choices=("x86_64", "aarch64"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("Invalid repository")
    release = json.loads(subprocess.check_output([
        "gh", "api", f"repos/{args.repository}/releases/tags/{quote(args.tag, safe='')}"], text=True))
    prepare(release, args.arch, args.out, args.lock, args.metadata_only)
