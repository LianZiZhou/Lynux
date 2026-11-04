#!/usr/bin/env python3
"""Two-phase publish: verified immutable objects -> GitHub Release -> latest index.

Requires boto3, gh and pre-existing public S3 HTTPS delivery. No bucket is created.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
from download import download


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def collect(directory):
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
        required_tools = {"codex", "claude", "kimi", "dsh", "opencode"}
        if (provider.get("mock_only") is not True or set(provider.get("results", {})) != required_tools
                or not all(v.get("passed") is True for v in provider["results"].values())
                or provider.get("rootfs_sha256") != meta.get("rootfs_sha256")):
            raise ValueError(f"Missing model protocol smoke evidence: {arch}")
        metadata[arch] = meta
    if metadata["x86_64"]["version"] != metadata["aarch64"]["version"]:
        raise ValueError("Architecture release versions differ")
    versions = [json.loads((directory / f"{arch}-harness-versions.json").read_text())
                for arch in ("x86_64", "aarch64")]
    required = {"codex", "claude", "kimi", "dsh", "opencode"}
    if any(set(v) != required for v in versions):
        raise ValueError("All five harnesses are mandatory")
    if {k: v["version"] for k, v in versions[0].items()} != {k: v["version"] for k, v in versions[1].items()}:
        raise ValueError("Harness versions differ between architectures")
    # Only validated ISO paths and known public evidence are release assets. A build directory
    # can also contain unsigned images, old candidates, or local operator files.
    names = {meta["iso"] for meta in metadata.values()}
    names.update({"lynux.cer", "lynux.crt", "dependency-lock.tar.gz", "aarch64-bootstrap-SHA256SUMS.txt"})
    for arch in metadata:
        for suffix in ("build.json", "packages.txt", "harness-versions.json", "node-version.txt", "python-version.txt",
                       "secure-usb.json", "secure-cdrom.json", "integrity-negative.json", "provider-smoke.json", "ventoy.json"):
            names.add(f"{arch}-{suffix}")
    names.update({"x86_64-bios-usb.json", "x86_64-bios-cdrom.json"})
    files = [directory / name for name in sorted(names) if (directory / name).is_file()]
    return files, metadata


def verify_url(url, expected):
    with tempfile.TemporaryDirectory(prefix="lynux-publish-verify-") as folder:
        download(url, Path(folder) / "asset", "sha-256=" + expected, fresh=True)


def publish(directory, repository, commit, dry_run=False):
    files, metadata = collect(directory)
    version = metadata["x86_64"]["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}", version):
        raise ValueError("Invalid version")
    hashes = {p.name: sha(p) for p in files}
    sums = directory / "SHA256SUMS"
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
    signature = directory / "SHA256SUMS.sig"
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", os.environ["RELEASE_SIGNING_KEY"],
                    "-out", str(signature), str(sums)], check=True)
    files += [sums, signature]
    urls = {}
    for path in files:
        key = f"{keybase}/{path.name}"
        expected = sha(path)
        client.upload_file(str(path), bucket, key, ExtraArgs={"Metadata": {"sha256": expected}})
        url = f"{public}/{urllib.parse.quote(key, safe='/')}"
        verify_url(url, expected)
        urls[path.name] = url
    notes = directory / "release-notes.md"
    lines = [f"# Lynux {version}", "", "完整镜像已上传并通过 HTTPS 下载摘要验证。", ""]
    for arch, meta in metadata.items():
        lines.append(f"- [{arch} ISO]({urls[meta['iso']]}) — SHA-256 `{meta['sha256']}`")
    lines += ["", "Secure Boot：直接烧录 UEFI 镜像，并手动导入 lynux.cer；Ventoy 无需安全启动。",
              "ARM64 仅覆盖兼容 UEFI 设备；板级支持以实机验证记录为准。", "", f"Source commit: `{commit}`"]
    notes.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assets = [p for p in files if p.suffix != ".iso" and p.stat().st_size < 2 * 1024 ** 3]
    subprocess.run(["gh", "release", "create", f"v{version}", "--repo", repository, "--target", commit,
                    "--title", f"Lynux {version}", "--notes-file", str(notes), *map(str, assets)], check=True)
    # Only a complete published GitHub Release may become the latest pointer.
    client.put_object(Bucket=bucket, Key=f"{prefix}/latest.json", ContentType="application/json",
                      CacheControl="no-cache", Body=json.dumps({"version": version, "commit": commit,
                                                               "downloads": urls}, indent=2).encode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--dry-run", action="store_true")
    publish(**vars(parser.parse_args()))
