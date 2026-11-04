#!/usr/bin/env python3
"""Resolve a single immutable harness bill of materials for both architectures."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from download import fetch

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_REPO = "https://downloads.claude.ai/claude-code-releases"
CLAUDE_KEY = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve(out):
    out.mkdir(parents=True, exist_ok=False)
    specs = json.loads((ROOT / "config/harnesses.json").read_text())["harnesses"]
    lock = {"schema": 1, "resolved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "harnesses": {}, "files": {}}
    for tool, spec in specs.items():
        if spec["kind"] == "npm":
            meta = json.loads(fetch(f"https://registry.npmjs.org/{spec['package']}/latest"))
            version = meta["version"]
            directory = out / tool
            directory.mkdir()
            write_json(directory / "package.json", {"name": f"lynux-{tool}", "private": True,
                                                    "version": "1.0.0", "dependencies": {spec["package"]: version}})
            subprocess.run(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
                           cwd=directory, check=True)
            lock["harnesses"][tool] = {"kind": "npm", "package": spec["package"], "version": version,
                                       "url": meta["dist"]["tarball"], "integrity": meta["dist"]["integrity"]}
        else:
            version = fetch(f"{CLAUDE_REPO}/latest").decode().strip()
            if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-.a-zA-Z0-9]+)?", version):
                raise ValueError("Invalid Claude version")
            directory = out / tool
            directory.mkdir()
            for filename in ("manifest.json", "manifest.json.sig"):
                (directory / filename).write_bytes(fetch(f"{CLAUDE_REPO}/{version}/{filename}"))
            key = directory / "release-key.asc"
            key.write_bytes(fetch("https://downloads.claude.ai/keys/claude-code.asc"))
            with tempfile.TemporaryDirectory() as home:
                cmd = ["gpg", "--batch", "--homedir", home]
                subprocess.run([*cmd, "--import", str(key)], check=True)
                fingerprints = subprocess.check_output([*cmd, "--with-colons", "--fingerprint"], text=True)
                if f"fpr:::::::::{CLAUDE_KEY}:" not in fingerprints:
                    raise ValueError("Claude release key fingerprint changed")
                result = subprocess.run([*cmd, "--status-fd=1", "--verify", str(directory / "manifest.json.sig"),
                                         str(directory / "manifest.json")], text=True, capture_output=True, check=True)
                if CLAUDE_KEY not in result.stdout:
                    raise ValueError("Manifest was not signed by the expected Claude key")
            manifest = json.loads((directory / "manifest.json").read_text())
            lock["harnesses"][tool] = {"kind": "claude-native", "version": version, "platforms": {
                arch: {"url": f"{CLAUDE_REPO}/{version}/{native}/claude",
                       "sha256": manifest["platforms"][native]["checksum"]}
                for arch, native in (("x86_64", "linux-x64"), ("aarch64", "linux-arm64"))}}
            # Anthropic also distributes the identical native executable through npm's CDN.
            # Its extracted binary must still match the signed upstream manifest above.
            for arch, native in (("x86_64", "linux-x64"), ("aarch64", "linux-arm64")):
                try:
                    native_meta = json.loads(fetch(f"https://registry.npmjs.org/@anthropic-ai/claude-code-{native}/{version}"))
                except subprocess.CalledProcessError:
                    continue  # A new upstream release may precede publication to npm.
                lock["harnesses"][tool]["platforms"][arch].update({
                    "npm_url": native_meta["dist"]["tarball"], "npm_integrity": native_meta["dist"]["integrity"]})
    commit = subprocess.check_output(["git", "ls-remote", "https://github.com/archlinux/archiso.git", "HEAD"],
                                     text=True).split()[0]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Cannot resolve archiso commit")
    (out / "archiso.commit").write_text(commit + "\n")
    lock["archiso_commit"] = commit
    references = subprocess.check_output(["git", "ls-remote", "--tags", "https://github.com/tianocore/edk2.git"],
                                         text=True).splitlines()
    stable = {}
    for reference in references:
        object_id, name = reference.split()
        match = re.fullmatch(r"refs/tags/(edk2-stable[0-9]{6})(\^\{\})?", name)
        if match and (match[2] or match[1] not in stable):
            stable[match[1]] = object_id
    tag = max(stable)
    (out / "edk2.commit").write_text(stable[tag] + "\n")
    lock["edk2"] = {"tag": tag, "commit": stable[tag]}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            lock["files"][path.relative_to(out).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(out / "manifest.json", lock)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    resolve(parser.parse_args().out.resolve())
