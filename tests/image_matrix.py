#!/usr/bin/env python3
"""Native QEMU matrix and cryptographic negative tests for final signed ISO bytes."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from qemu_boot import boot, sha


def firmware(arch, secure=True, directories=None):
    fallback = None
    for directory in directories or (Path("/usr/share/qemu/firmware"), Path("/etc/qemu/firmware")):
        for filename in sorted(directory.glob("*.json")):
            data = json.loads(filename.read_text())
            features = data.get("features", [])
            capable = "secure-boot" in features
            if secure and not capable:
                continue
            # Secure Boot capability does not mean enforcement is enabled. An
            # un-enrolled ArmVirt template can also boot ordinary Ventoy media.
            if not secure and "enrolled-keys" in features:
                continue
            if not any(t.get("architecture") == arch for t in data.get("targets", [])):
                continue
            if "ia32" in filename.name:
                continue
            mapping = data["mapping"]
            if mapping.get("device") != "flash" or "executable" not in mapping or "nvram-template" not in mapping:
                continue
            code = Path(mapping["executable"]["filename"])
            template = Path(mapping["nvram-template"]["filename"])
            if code.exists() and template.exists():
                if not secure and capable:
                    fallback = fallback or (code, template)
                    continue
                return code, template
    if fallback:
        return fallback
    raise RuntimeError(f"No matching QEMU firmware descriptor for {arch}, secure={secure}")


def matrix(iso, arch, cert, report_dir, secure_work):
    code, template = firmware(arch)
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lynux-matrix-") as folder:
        temp = Path(folder)
        trusted = temp / "trusted.fd"
        subprocess.run(["virt-fw-vars", "--input", str(template), "--output", str(trusted),
                        "--enroll-cert", str(cert), "--no-microsoft", "--microsoft-kek", "none",
                        "--add-db", "3114b388-2195-4e83-8ac7-f72b8c020c7a", str(cert),
                        "--secure-boot"], check=True)
        for media in ("cdrom", "usb"):
            boot(iso, arch, "uefi", media, code, trusted, secure=True,
                 report=report_dir / f"{arch}-secure-{media}.json")
        if arch == "x86_64":
            for media in ("cdrom", "usb"):
                boot(iso, arch, "bios", media, report=report_dir / f"{arch}-bios-{media}.json")
        # Wrong certificates and modified PE executables must fail cryptographic verification.
        key, other = temp / "other.key", temp / "other.crt"
        subprocess.run(["openssl", "req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-subj", "/CN=Lynux negative test/", "-days", "1", "-keyout", str(key), "-out", str(other)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        uki = secure_work / "lynux.efi"
        if subprocess.run(["sbverify", "--cert", str(other), str(uki)], capture_output=True).returncode == 0:
            raise RuntimeError("Wrong certificate accepted")
        bad_uki = temp / "bad.efi"
        shutil.copy2(uki, bad_uki)
        # Change a byte in a PE section, not the DOS header or Authenticode-excluded checksum.
        with bad_uki.open("r+b") as stream:
            stream.seek(4096)
            value = stream.read(1)
            stream.seek(4096)
            stream.write(bytes([value[0] ^ 1]))
        if subprocess.run(["sbverify", "--cert", str(cert), str(bad_uki)], capture_output=True).returncode == 0:
            raise RuntimeError("Modified UKI signature accepted")
        # Mutate one byte in the on-disk squashfs extent without changing the signed boot chain.
        listing = subprocess.run(["xorriso", "-indev", str(iso), "-find", f"/arch/{arch}/airootfs.sfs",
                                  "-exec", "report_lba", "--"], text=True, capture_output=True, check=True)
        match = re.search(r"File data lba:\s*\d+\s*,\s*(\d+)\s*,", listing.stdout + listing.stderr)
        if not match:
            raise RuntimeError("Cannot locate the rootfs extent for integrity negative test")
        bad_iso = temp / "bad-rootfs.iso"
        shutil.copy2(iso, bad_iso)
        with bad_iso.open("r+b") as stream:
            stream.seek(int(match.group(1)) * 2048 + 4096)
            value = stream.read(1)
            stream.seek(-1, 1)
            stream.write(bytes([value[0] ^ 1]))
        result = boot(bad_iso, arch, "uefi", "usb", code, trusted, secure=True,
                      expect="LYNUX_INTEGRITY_FAILED", report=report_dir / f"{arch}-integrity-negative.json")
        result["baseline_sha256"] = sha(iso)
        result["wrong_certificate_rejected"] = True
        result["modified_uki_rejected"] = True
        (report_dir / f"{arch}-integrity-negative.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--secure-work", type=Path, required=True)
    matrix(**vars(parser.parse_args()))
