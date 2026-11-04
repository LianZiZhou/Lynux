#!/usr/bin/env python3
"""Executed inside the target rootfs, never in the developer's host environment."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from download import download, download_many


def supports(values, actual):
    if not values:
        return True
    if "!" + actual in values:
        return False
    positive = [v for v in values if not v.startswith("!")]
    return not positive or actual in positive or "any" in positive


def sri_checksum(integrity):
    algorithm, encoded = integrity.split()[0].split("-", 1)
    name = {"sha512": "sha-512", "sha256": "sha-256", "sha1": "sha-1"}[algorithm]
    return name + "=" + base64.b64decode(encoded, validate=True).hex()


def install_claude(asset, dest):
    if asset.get("npm_url"):
        archive = Path("/var/cache/lynux/tarballs/claude-native.tgz")
        download(asset["npm_url"], archive, sri_checksum(asset["npm_integrity"]))
        with tarfile.open(archive) as bundle:
            binaries = [m for m in bundle.getmembers() if m.isfile() and Path(m.name).name == "claude"]
            if len(binaries) != 1:
                raise ValueError("Claude native npm package has an unexpected layout")
            with bundle.extractfile(binaries[0]) as source, dest.open("wb") as output:
                shutil.copyfileobj(source, output)
    else:
        download(asset["url"], dest, "sha-256=" + asset["sha256"])
    with dest.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != asset["sha256"]:
            raise ValueError("Claude binary does not match the signed upstream manifest")
    dest.with_name(dest.name + ".aria2").unlink(missing_ok=True)


def prefetch_npm(prefix, env):
    """Transfer native-compatible locked tarballs via aria2, then install from npm's verified cache."""
    lock = json.loads((prefix / "package-lock.json").read_text())
    cpu = {"x86_64": "x64", "aarch64": "arm64"}[platform.machine()]
    jobs = {}
    for name, package in lock["packages"].items():
        if not name or package.get("dev") or package.get("link"):
            continue
        if not all((supports(package.get("os"), "linux"), supports(package.get("cpu"), cpu),
                    supports(package.get("libc"), "glibc"))):
            continue
        url = package["resolved"]
        checksum = sri_checksum(package["integrity"])
        path = Path("/var/cache/lynux/tarballs") / (hashlib.sha256(url.encode()).hexdigest() + ".tgz")
        jobs[str(path)] = (url, path, checksum)
    download_many(jobs.values())
    paths = list(jobs)
    for offset in range(0, len(paths), 32):
        subprocess.run(["npm", "cache", "add", "--offline", "--ignore-scripts", *paths[offset:offset + 32]],
                       env=env, cwd=prefix, check=True)


def install(lockdir):
    lock = json.loads((lockdir / "manifest.json").read_text())
    if lock["schema"] != 1:
        raise ValueError("Unknown harness lock format")
    for relative, expected in lock["files"].items():
        source = (lockdir / relative).resolve()
        if not source.is_relative_to(lockdir.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Invalid locked file: {relative}")
    observed = {}
    for tool, entry in lock["harnesses"].items():
        prefix = Path("/opt/lynux/harnesses") / tool
        if prefix.is_symlink():
            raise ValueError("Invalid harness installation prefix")
        prefix.mkdir(parents=True, exist_ok=True)
        (prefix / "bin").mkdir(exist_ok=True)
        dest = prefix / "bin" / tool
        if entry["kind"] == "npm":
            for filename in ("package.json", "package-lock.json"):
                shutil.copy2(lockdir / tool / filename, prefix / filename)
            env = {**os.environ, "npm_config_engine_strict": "true", "npm_config_update_notifier": "false"}
            env["npm_config_cache"] = "/var/cache/lynux/npm"
            prefetch_npm(prefix, env)
            subprocess.run(["npm", "ci", "--offline", "--ignore-scripts", "--omit=dev", "--include=optional",
                            "--no-audit", "--no-fund"],
                           cwd=prefix, env=env, check=True)
            npm_major = int(subprocess.check_output(["npm", "--version"], text=True).split(".")[0])
            if npm_major >= 12:
                # npm 12 requires explicit approvals. These are version-pinned installed dependencies
                # from the already validated lock, not a blanket global allow policy.
                subprocess.run(["npm", "install-scripts", "approve", "--all"], cwd=prefix, env=env, check=True)
            subprocess.run(["npm", "rebuild", "--offline"], cwd=prefix, env=env, check=True)
            target = prefix / "node_modules" / ".bin" / tool
            if not target.exists():
                raise ValueError(f"Missing platform executable: {tool}")
            if dest.is_symlink():
                dest.unlink()
            dest.symlink_to(target)
            package = json.loads((prefix / "node_modules" / entry["package"] / "package.json").read_text())
            if package["version"] != entry["version"]:
                raise ValueError(f"Installed version drift: {tool}")
        else:
            asset = entry["platforms"][platform.machine()]
            install_claude(asset, dest)
            dest.chmod(0o755)
        output = subprocess.check_output([str(dest), "--version"], text=True, timeout=60).strip()
        if entry["version"] not in output:
            raise ValueError(f"Unexpected {tool} version: {output}")
        subprocess.run([str(dest), "--help"], stdout=subprocess.DEVNULL, check=True, timeout=60)
        observed[tool] = {"version": entry["version"], "output": output}
        # All public commands pass through the session lock and root scope.
        wrapper = Path("/usr/local/bin") / tool
        wrapper.write_text(f'#!/bin/sh\nexec sudo /usr/local/bin/lynux-harness run {tool} -- "$@"\n')
        wrapper.chmod(0o755)
    Path("/usr/share/lynux/harness-versions.json").write_text(json.dumps(observed, indent=2) + "\n")


if __name__ == "__main__":
    install(Path(sys.argv[1]))
