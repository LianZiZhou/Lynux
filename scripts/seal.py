#!/usr/bin/env python3
"""Sign a direct-boot UKI and repack ISO while retaining BIOS/Ventoy boot metadata.

The rootfs hash is inserted only AFTER squashfs creation, avoiding a circular digest.
Normal initramfs is left intact for Ventoy; the signed UKI uses a separate initramfs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build import command, put


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_public_certificate(source, destination):
    # Signing inputs are mode 0600; public artifacts must be readable by the
    # unprivileged Actions uploader. Never apply this to the private key.
    shutil.copyfile(source, destination)
    destination.chmod(0o644)


def kernel_module_version(rootfs, kernel):
    markers = list((rootfs / "usr/lib/modules").glob("*/pkgbase"))
    matching = [path for path in markers if path.read_text().strip() == kernel]
    if len(matching) == 1:
        return matching[0].parent.name
    if matching:
        raise RuntimeError("Cannot uniquely identify the image kernel module version")
    # ALARM's linux-aarch64 package does not provide pkgbase. Query ownership
    # instead of guessing a directory or using the builder host's kernel version.
    files = subprocess.check_output(["arch-chroot", str(rootfs), "pacman", "-Qlq", kernel], text=True)
    versions = {match[1] for line in files.splitlines()
                if (match := re.match(r"^/usr/lib/modules/([^/]+)/", line))
                and (rootfs / "usr/lib/modules" / match[1]).is_dir()}
    if len(versions) != 1:
        raise RuntimeError(f"Cannot uniquely identify modules owned by {kernel}: {sorted(versions)}")
    return versions.pop()


def seal(work, iso, key, cert):
    meta = json.loads((work / "build.json").read_text())
    arch = meta["arch"]
    rootfs = work / "archiso" / arch / "airootfs"
    sfs = work / "archiso/iso/arch" / arch / "airootfs.sfs"
    if not sfs.exists():
        raise RuntimeError("Missing archiso squashfs build output")
    digest = sha(sfs)
    hooks = rootfs / "usr/lib/initcpio/hooks/archiso"
    original = hooks.read_text()
    marker = "_mnt_fs() {"
    if original.count(marker) != 1:
        raise RuntimeError("Upstream archiso mount hook changed; integrity integration needs review")
    # Fail closed before any rootfs mount. A failure must not open an interactive root shell.
    check = '''
    if [ "$(sha256sum "$1" | cut -d ' ' -f 1)" != "$(cat /etc/lynux-rootfs.sha256)" ]; then
        echo 'LYNUX_INTEGRITY_FAILED' >/dev/console
        poweroff -f
        while :; do sleep 3600; done
    fi
'''
    kernel_version = kernel_module_version(rootfs, meta["kernel"])
    secure = work / "secure"
    secure.mkdir(exist_ok=True)
    target_hash = rootfs / "etc/lynux-rootfs.sha256"
    cfg = rootfs / "etc/mkinitcpio-lynux-secure.conf"
    try:
        hooks.write_text(original.replace(marker, marker + check))
        target_hash.write_text(digest + "\n")
        put(cfg, (rootfs / "etc/mkinitcpio.conf").read_text() +
            '\nFILES+=(/etc/lynux-rootfs.sha256)\nBINARIES+=(sha256sum cut poweroff)\n')
        command("arch-chroot", rootfs, "mkinitcpio", "-c", "/etc/mkinitcpio-lynux-secure.conf",
                "-k", kernel_version, "-g", "/boot/lynux-secure.img")
        shutil.move(rootfs / "boot/lynux-secure.img", secure / "initramfs.img")
    finally:
        hooks.write_text(original)
        target_hash.unlink(missing_ok=True)
        cfg.unlink(missing_ok=True)
    kernel = work / "archiso/iso/arch/boot" / arch / f"vmlinuz-{meta['kernel']}"
    if not kernel.exists():
        raise RuntimeError(f"Missing kernel: {kernel}")
    efi_arch = "x64" if arch == "x86_64" else "aa64"
    uki = secure / "lynux.efi"
    command("ukify", "build", f"--linux={kernel}", f"--initrd={secure / 'initramfs.img'}",
            "--sign-kernel",
            f"--uname={kernel_version}",
            f"--cmdline={meta['cmdline']}", f"--os-release=@{rootfs / 'etc/os-release'}",
            f"--stub={rootfs / 'usr/lib/systemd/boot/efi' / ('linux' + efi_arch + '.efi.stub')}",
            f"--secureboot-private-key={key}", f"--secureboot-certificate={cert}", f"--output={uki}")
    loader = secure / f"BOOT{efi_arch.upper()}.EFI"
    command("sbsign", "--key", key, "--cert", cert, "--output", loader,
            rootfs / f"usr/lib/systemd/boot/efi/systemd-boot{efi_arch}.efi")
    command("sbverify", "--cert", cert, uki)
    command("sbverify", "--cert", cert, loader)
    esp = secure / "esp.img"
    # Build a new ESP rather than assuming the old FAT image has enough free space for a UKI.
    size = ((uki.stat().st_size + 96 * 1024 ** 2 + 1024 ** 2 - 1) // (1024 ** 2)) * 1024 ** 2
    with esp.open("wb") as stream:
        stream.truncate(size)
    command("mkfs.vfat", "-F", "32", "-n", "LYNUX_EFI", esp)
    for directory in ("::/EFI", "::/EFI/BOOT", "::/EFI/Linux", "::/loader", "::/loader/entries"):
        command("mmd", "-i", esp, directory)
    command("mcopy", "-i", esp, uki, "::/EFI/Linux/lynux.efi")
    command("mcopy", "-i", esp, loader, f"::/EFI/BOOT/BOOT{efi_arch.upper()}.EFI")
    put(secure / "loader.conf", "default lynux.efi\ntimeout 3\neditor no\n")
    command("mcopy", "-i", esp, secure / "loader.conf", "::/loader/loader.conf")
    command("openssl", "x509", "-in", cert, "-outform", "DER", "-out", secure / "lynux.cer")
    command("mcopy", "-i", esp, secure / "lynux.cer", "::/lynux.cer")
    output = iso.with_name(iso.stem + "-signed.iso")
    tree = work / "archiso/iso"
    (tree / "EFI/Linux").mkdir(parents=True, exist_ok=True)
    shutil.copy2(uki, tree / "EFI/Linux/lynux.efi")
    shutil.copy2(loader, tree / "EFI/BOOT" / loader.name)
    shutil.copy2(secure / "lynux.cer", tree / "lynux.cer")
    # Recreate the catalog with exactly one EFI entry. Replaying the old catalog would
    # leave an unsigned EFI image first on optical boot even if the USB ESP was replaced.
    options = []
    if arch == "x86_64":
        options = ["-b", "boot/syslinux/isolinux.bin", "-c", "boot/syslinux/boot.cat",
                   "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table",
                   "-isohybrid-mbr", tree / "boot/syslinux/isohdpfx.bin", "--mbr-force-bootable"]
    command("xorriso", "-as", "mkisofs", "-iso-level", "3", "-full-iso9660-filenames", "-J", "-joliet-long",
            "-r", "-V", meta["label"], *options, "-partition_offset", "16",
            "-append_partition", "2", "C12A7328-F81F-11D2-BA4B-00A0C93EC93B", esp,
            "-isohybrid-gpt-basdat" if arch == "x86_64" else "-appended_part_as_gpt",
            "-eltorito-alt-boot", "-e", "--interval:appended_partition_2:all::", "-no-emul-boot",
            "-o", output, tree)
    # Keep a machine-readable binding from the signing inputs to final bytes.
    meta.update({"signed": True, "iso": output.name, "sha256": sha(output), "rootfs_sha256": digest,
                 "uki_sha256": sha(uki), "certificate_sha256": sha(secure / "lynux.cer")})
    put(output.parent / f"{arch}-build.json", json.dumps(meta, indent=2) + "\n")
    copy_public_certificate(secure / "lynux.cer", output.parent / "lynux.cer")
    copy_public_certificate(cert, output.parent / "lynux.crt")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("work", "iso", "key", "cert"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(seal(args.work.resolve(), args.iso.resolve(), args.key.resolve(), args.cert.resolve()))
