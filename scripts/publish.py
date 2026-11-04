#!/usr/bin/env python3
"""Two-phase publish: verified immutable objects -> GitHub Release -> latest index.

Requires boto3, gh and pre-existing public S3 HTTPS delivery. No bucket is created.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
from download import download

TOOLS = {"codex": "Codex", "claude": "Claude Code", "kimi": "Kimi Code", "dsh": "DeepSeek Harness",
         "opencode": "OpenCode"}
REPORTS = ("secure-usb", "secure-cdrom", "bios-usb", "bios-cdrom", "ventoy", "integrity-negative", "provider-smoke")
REPORT_SUFFIXES = (".json", ".serial.log", ".qemu.log", ".png")
BOOTS = {"x86_64": "BIOS and UEFI", "aarch64": "UEFI"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def collect(directory):
    """Check every piece of release evidence. Returns per-arch build metadata and CLI versions."""
    metadata = {}
    for arch in ("x86_64", "aarch64"):
        meta = json.loads((directory / f"{arch}-build.json").read_text())
        if not meta.get("signed") or meta["arch"] != arch:
            raise ValueError(f"Unsigned or incorrect {arch} image")
        if meta.get("certificate_sha256") != sha(directory / "lynux.cer"):
            raise ValueError(f"Certificate does not match the {arch} signing manifest")
        iso = directory / meta["iso"]
        if iso.name != meta["iso"] or iso.suffix.lower() != ".iso" or sha(iso) != meta["sha256"]:
            raise ValueError(f"Image digest mismatch: {arch}")
        for media in ("usb", "cdrom"):
            report = json.loads((directory / f"{arch}-secure-{media}.json").read_text())
            if (not report.get("passed") or not report.get("secure_boot")
                    or report.get("iso_sha256") != meta["sha256"]):
                raise ValueError(f"Missing final-byte boot evidence: {arch}/{media}")
        for kind in (["ventoy", "bios-usb", "bios-cdrom"] if arch == "x86_64" else ["ventoy"]):
            report = json.loads((directory / f"{arch}-{kind}.json").read_text())
            if not report.get("passed") or report.get("iso_sha256") != meta["sha256"]:
                raise ValueError(f"Missing final-byte boot evidence: {arch}/{kind}")
        negative = json.loads((directory / f"{arch}-integrity-negative.json").read_text())
        if (not all(negative.get(k) for k in ("passed", "wrong_certificate_rejected", "modified_uki_rejected"))
                or negative.get("baseline_sha256") != meta["sha256"]):
            raise ValueError(f"Missing integrity negative-test evidence: {arch}")
        provider = json.loads((directory / f"{arch}-provider-smoke.json").read_text())
        if (provider.get("mock_only") is not True or set(provider.get("results", {})) != set(TOOLS)
                or not all(v.get("passed") is True for v in provider["results"].values())
                or provider.get("rootfs_sha256") != meta.get("rootfs_sha256")):
            raise ValueError(f"Missing model protocol smoke evidence: {arch}")
        metadata[arch] = meta
    if metadata["x86_64"]["version"] != metadata["aarch64"]["version"]:
        raise ValueError("Architecture release versions differ")
    versions = [json.loads((directory / f"{arch}-harness-versions.json").read_text())
                for arch in ("x86_64", "aarch64")]
    if any(set(v) != set(TOOLS) for v in versions):
        raise ValueError("All five harnesses are mandatory")
    if {k: v["version"] for k, v in versions[0].items()} != {k: v["version"] for k, v in versions[1].items()}:
        raise ValueError("Harness versions differ between architectures")
    return metadata, versions[0]


def bundle(target, root, members):
    """Write a tarball with fixed owners and times, so the same inputs give the same file."""
    with target.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed, \
            tarfile.open(fileobj=compressed, mode="w") as archive:
        for path in sorted(members):
            info = archive.gettarinfo(str(path), f"{root}/{path.name}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)


def stage(directory, metadata, target):
    """Pack validated build outputs into the release file set: {published name: local path}.

    Only validated ISOs and known evidence are included. A build directory can also hold
    unsigned images, old candidates or operator files.
    """
    base = f"lynux-{metadata['x86_64']['version']}"
    files = {name: directory / name for name in ("lynux.crt", "lynux.cer")}
    for arch, meta in metadata.items():
        details = {key: value for key, value in meta.items() if key != "test"}
        details["iso"] = f"{base}-{arch}.iso"
        details["size"] = (directory / meta["iso"]).stat().st_size
        tools = json.loads((directory / f"{arch}-harness-versions.json").read_text())
        details["harnesses"] = {name: tools[name]["version"] for name in TOOLS}
        details["node"] = (directory / f"{arch}-node-version.txt").read_text().strip()
        details["python"] = (directory / f"{arch}-python-version.txt").read_text().strip().removeprefix("Python ")
        bootstrap = directory / f"{arch}-bootstrap-SHA256SUMS.txt"
        if bootstrap.is_file():
            details["bootstrap_rootfs_sha256"] = bootstrap.read_text().split()[0]
        packages = (directory / f"{arch}-packages.txt").read_text().splitlines()
        details["packages"] = dict(line.split(" ", 1) for line in packages if line.strip())
        info = target / f"{base}-{arch}.json"
        info.write_text(json.dumps(details, indent=2) + "\n")
        files[info.name] = info
        files[details["iso"]] = directory / meta["iso"]
        reports = [directory / f"{arch}-{kind}{suffix}" for kind in REPORTS for suffix in REPORT_SUFFIXES]
        archive = target / f"{base}-{arch}-test-reports.tar.gz"
        bundle(archive, archive.name.removesuffix(".tar.gz"), [path for path in reports if path.is_file()])
        files[archive.name] = archive
    lock = target / f"{base}-dependency-lock.tar.gz"
    shutil.copyfile(directory / "dependency-lock.tar.gz", lock)
    files[lock.name] = lock
    return dict(sorted(files.items()))


def notes(version, commit, tools, urls, hashes):
    base = f"lynux-{version}"
    # No title here: GitHub already shows the release name as the page heading.
    lines = [f"Built from commit `{commit[:12]}`.", "",
             "| Architecture | Boots on | Download | SHA-256 |", "|---|---|---|---|"]
    for arch, boots in BOOTS.items():
        name = f"{base}-{arch}.iso"
        lines.append(f"| {arch} | {boots} | [{name}]({urls[name]}) | `{hashes[name]}` |")
    lines += ["", "Included CLIs: " + ", ".join(f"{TOOLS[key]} {tools[key]['version']}" for key in TOOLS) + ".", "",
              "Put the ISO on a Ventoy drive or write it straight to a USB stick. For Secure Boot, write it "
              "directly and add `lynux.cer` to your firmware's `db`. ARM64 only boots on machines with UEFI firmware.",
              "", "### Files", "", "| File | What it is |", "|---|---|",
              "| `SHA256SUMS`, `SHA256SUMS.sig` | Checksums of every file, signed with the release key |",
              "| `lynux.crt`, `lynux.cer` | Secure Boot and release signing certificate (PEM, DER) |",
              f"| `{base}-<arch>.json` | Build details: hashes, CLI and runtime versions, package list |",
              f"| `{base}-<arch>-test-reports.tar.gz` | QEMU boot, Secure Boot, Ventoy and model API test results |",
              f"| `{base}-dependency-lock.tar.gz` | Exact CLI and archiso inputs used for this build |",
              "", "Check a download:", "", "```sh", "sha256sum --ignore-missing -c SHA256SUMS",
              "openssl x509 -in lynux.crt -pubkey -noout > release.pub",
              "openssl dgst -sha256 -verify release.pub -signature SHA256SUMS.sig SHA256SUMS", "```"]
    return "\n".join(lines) + "\n"


def verify_url(url, expected):
    with tempfile.TemporaryDirectory(prefix="lynux-publish-verify-") as folder:
        download(url, Path(folder) / "asset", "sha-256=" + expected, fresh=True)


def publish(directory, repository, commit, dry_run=False):
    metadata, tools = collect(directory)
    version = metadata["x86_64"]["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}", version):
        raise ValueError("Invalid version")
    with tempfile.TemporaryDirectory(prefix="lynux-release-") as folder:
        release(Path(folder), directory, metadata, tools, version, repository, commit, dry_run)


def release(folder, directory, metadata, tools, version, repository, commit, dry_run):
    files = stage(directory, metadata, folder)
    hashes = {name: sha(path) for name, path in files.items()}
    sums = folder / "SHA256SUMS"
    sums.write_text("".join(f"{value}  {name}\n" for name, value in hashes.items()))
    if dry_run:
        print(json.dumps({"version": version, "files": hashes}, indent=2))
        return
    cert_public = subprocess.check_output(["openssl", "x509", "-in", str(directory / "lynux.crt"),
                                           "-pubkey", "-noout"])
    key_public = subprocess.check_output(["openssl", "pkey", "-in", os.environ["RELEASE_SIGNING_KEY"], "-pubout"])
    if cert_public.strip() != key_public.strip():
        raise ValueError("Release signing key does not match the image certificate")
    certificate_der = subprocess.check_output(["openssl", "x509", "-in", str(directory / "lynux.crt"),
                                               "-outform", "DER"])
    if hashlib.sha256(certificate_der).hexdigest() != sha(directory / "lynux.cer"):
        raise ValueError("PEM and DER certificates differ")
    import boto3
    endpoint = os.environ["S3_ENDPOINT"]
    bucket = os.environ["S3_BUCKET"]
    public = os.environ["DOWNLOAD_BASE_URL"].rstrip("/")
    if not endpoint.startswith("https://") or not public.startswith("https://"):
        raise ValueError("HTTPS storage and download endpoints are required")
    prefix = (os.environ.get("S3_PREFIX") or "lynux").strip("/")
    keybase = f"{prefix}/{version}"
    client = boto3.client("s3", endpoint_url=endpoint, region_name=os.environ.get("S3_REGION") or "auto")
    # A create-only reservation prevents retries from overwriting any existing version.
    client.put_object(Bucket=bucket, Key=f"{keybase}/reserved.json", IfNoneMatch="*",
                      Body=json.dumps({"commit": commit, "version": version}).encode())
    signature = folder / "SHA256SUMS.sig"
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", os.environ["RELEASE_SIGNING_KEY"],
                    "-out", str(signature), str(sums)], check=True)
    files = {sums.name: sums, signature.name: signature, **files}
    urls = {}
    for name, path in files.items():
        key = f"{keybase}/{name}"
        expected = sha(path)
        client.upload_file(str(path), bucket, key, ExtraArgs={"Metadata": {"sha256": expected}})
        url = f"{public}/{urllib.parse.quote(key, safe='/')}"
        verify_url(url, expected)
        urls[name] = url
    release_notes = folder / "release-notes.md"
    release_notes.write_text(notes(version, commit, tools, urls, hashes), encoding="utf-8")
    # ISOs are too large for GitHub Release assets; the notes link to them on S3.
    # `gh` labels an asset by its file name, so every asset must already carry its published name.
    assets = []
    for name, path in files.items():
        if name.endswith(".iso"):
            continue
        if path.name != name:
            raise ValueError(f"Release asset {path} is not staged under its published name {name}")
        assets.append(str(path))
    subprocess.run(["gh", "release", "create", f"v{version}", "--repo", repository, "--target", commit,
                    "--title", f"Lynux {version}", "--notes-file", str(release_notes), *assets], check=True)
    images = {arch: {"url": urls[f"lynux-{version}-{arch}.iso"], "sha256": hashes[f"lynux-{version}-{arch}.iso"]}
              for arch in metadata}
    # Only a complete published GitHub Release may become the latest pointer.
    client.put_object(Bucket=bucket, Key=f"{prefix}/latest.json", ContentType="application/json",
                      CacheControl="no-cache", Body=json.dumps({"version": version, "commit": commit,
                                                               "images": images, "downloads": urls},
                                                              indent=2).encode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--dry-run", action="store_true")
    publish(**vars(parser.parse_args()))
