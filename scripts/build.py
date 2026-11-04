#!/usr/bin/env python3
"""Native-architecture Arch builder. See scripts/run-builder.sh for isolated execution."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def command(*args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def put(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def packages(arch):
    result = []
    for name in ("common", arch):
        for line in (ROOT / "config" / f"packages.{name}").read_text().splitlines():
            value = line.split("#", 1)[0].strip()
            if value and value not in result:
                result.append(value)
    return result


def prepare_profile(arch, version, profile, lockdir, test=False, template=Path("/usr/share/archiso/configs/releng")):
    shutil.copytree(template, profile, symlinks=True)
    rootfs = profile / "airootfs"
    # Replace releng's installation-only configuration rather than mixing passwd/login defaults.
    shutil.rmtree(rootfs)
    shutil.copytree(ROOT / "overlay", rootfs)
    # WSL/NTFS may report every source file as executable; normalize image metadata.
    for path in rootfs.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    shutil.copytree(ROOT / "runtime/lynux", rootfs / "usr/lib/lynux/lynux", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("state", "iso", "harness", "welcome"):
        target = rootfs / "usr/local/bin" / f"lynux-{name}"
        put(target, (ROOT / "runtime/entrypoint.py").read_text(), 0o755)
    put(rootfs / "usr/local/bin/lynux-browser", (ROOT / "overlay/usr/local/bin/lynux-browser").read_text(), 0o755)
    shared = rootfs / "usr/share/lynux"
    shared.mkdir(parents=True, exist_ok=True)
    put(shared / ".building", "Lynux image staging only\n")
    put(shared / "os-release", f'NAME="Lynux"\nPRETTY_NAME="Lynux {version}"\nID=lynux\nID_LIKE=arch\nVERSION_ID="{version}"\nIMAGE_ID=lynux\nIMAGE_VERSION="{version}"\n')
    shutil.copy2(ROOT / "config/harnesses.json", shared / "harnesses.json")
    shutil.copytree(lockdir, shared / "lock")
    put(rootfs / "usr/local/lib/lynux/install-harnesses.py", (ROOT / "scripts/install-harnesses.py").read_text(), 0o755)
    put(rootfs / "usr/local/lib/lynux/download.py", (ROOT / "scripts/download.py").read_text(), 0o644)
    put(rootfs / "usr/local/lib/lynux/check-kernel.py", (ROOT / "scripts/check-kernel.py").read_text())
    put(rootfs / "usr/local/lib/lynux/pacman-download", (ROOT / "scripts/pacman-download.sh").read_text(), 0o755)
    put(rootfs / "root/customize_airootfs.sh", (ROOT / "scripts/customize.sh").read_text(), 0o755)
    put(rootfs / "usr/local/lib/lynux/boot-report", (ROOT / "overlay/usr/local/lib/lynux/boot-report").read_text(), 0o755)
    put(rootfs / "usr/local/lib/lynux/test-mode", (ROOT / "overlay/usr/local/lib/lynux/test-mode").read_text(), 0o755)
    put(rootfs / "usr/local/lib/lynux/init-keyring", (ROOT / "overlay/usr/local/lib/lynux/init-keyring").read_text(), 0o755)
    put(rootfs / "usr/local/lib/lynux/ventoy-find.c", (ROOT / "boot/ventoy-find.c").read_text())
    put(rootfs / "usr/lib/initcpio/install/lynux_ventoy", (ROOT / "boot/install-lynux_ventoy").read_text())
    put(rootfs / "usr/lib/initcpio/hooks/lynux_ventoy", (ROOT / "boot/hook-lynux_ventoy").read_text())
    put(rootfs / "usr/share/doc/lynux/guide.html", (ROOT / "docs/guide.html").read_text())
    shutil.copy2(ROOT / "config" / f"pacman.{arch}.conf", profile / "pacman.conf")
    shutil.copy2(ROOT / "config" / f"pacman.{arch}.conf", rootfs / "etc/pacman.conf")
    put(profile / f"packages.{arch}", "\n".join(packages(arch)) + "\n")
    label = "LYNUX_" + hashlib.sha256(f"{version}-{arch}".encode()).hexdigest()[:16].upper()
    modes = "'bios.syslinux' 'uefi.systemd-boot'" if arch == "x86_64" else "'uefi.systemd-boot'"
    compression = ("'-comp' 'zstd' '-b' '1M' '-Xcompression-level' '15'" if arch == "x86_64"
                   else "'-comp' 'xz' '-b' '1M' '-Xdict-size' '1M'")
    # Archiso releases predating the combined EFI mode use two separate mode names.
    mkarchiso = Path(shutil.which("mkarchiso")).read_text()
    if "_make_bootmode_uefi.systemd-boot()" not in mkarchiso:
        if arch == "aarch64":
            raise RuntimeError("This archiso is too old for native aarch64; install the current archiso source.")
        modes = "'bios.syslinux.mbr' 'bios.syslinux.eltorito' 'uefi-x64.systemd-boot.esp' 'uefi-x64.systemd-boot.eltorito'"
    put(profile / "profiledef.sh", f'''#!/bin/bash
iso_name="lynux"
iso_label="{label}"
iso_publisher="Lynux"
iso_application="Lynux AI Operations Live Linux"
iso_version="{version}"
install_dir="arch"
arch="{arch}"
buildmodes=('iso')
bootmodes=({modes})
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=({compression})
file_permissions=(['/root']='0:0:700' ['/etc/sudoers.d/lynux-live']='0:0:440'
 ['/root/customize_airootfs.sh']='0:0:755' ['/usr/local/lib/lynux/boot-report']='0:0:755'
 ['/usr/local/lib/lynux/test-mode']='0:0:755' ['/usr/local/lib/lynux/pacman-download']='0:0:755'
 ['/usr/local/lib/lynux/init-keyring']='0:0:755'
 ['/usr/local/bin/lynux-state']='0:0:755' ['/usr/local/bin/lynux-iso']='0:0:755'
 ['/usr/local/bin/lynux-harness']='0:0:755' ['/usr/local/bin/lynux-welcome']='0:0:755'
 ['/usr/local/bin/lynux-browser']='0:0:755')
''')
    kernel = "linux" if arch == "x86_64" else "linux-aarch64"
    hooks = ["base", "udev"]
    if arch == "x86_64":
        hooks.append("microcode")
    hooks += ["modconf", "kms"]
    if arch == "x86_64":
        hooks.append("memdisk")  # Requires x86-only syslinux's memdiskfind.
    hooks += ["archiso", "archiso_loop_mnt", "lynux_ventoy", "block", "filesystems", "keyboard", "shutdown"]
    put(rootfs / "etc/mkinitcpio.conf", 'MODULES=(loop squashfs overlay dm_mod dm_crypt)\nBINARIES=()\nFILES=()\n'
        + f'HOOKS=({" ".join(hooks)})\nCOMPRESSION="zstd"\n')
    # Explicit presets also normalize Arch Linux ARM's Image/initramfs naming for archiso.
    # ALARM's kernel package owns its preset, so stage the override elsewhere
    # until customize_airootfs.sh runs after the package transaction.
    preset = (rootfs / "usr/share/lynux/linux-aarch64.preset" if arch == "aarch64"
              else rootfs / "etc/mkinitcpio.d/linux.preset")
    preset_kernel = 'ALL_kver="/boot/vmlinuz-linux"\n' if arch == "x86_64" else ""
    put(preset, f'''ALL_config="/etc/mkinitcpio.conf"
{preset_kernel}PRESETS=('default')
default_image="/boot/initramfs-{kernel}.img"
''')
    for path in (profile / "efiboot/loader/entries").glob("*.conf"):
        path.unlink()
    console = "ttyS0" if arch == "x86_64" else "ttyAMA0"
    cmdline = f"archisobasedir=arch archisolabel={label} cow_spacesize=50% console=tty0 console={console},115200"
    if test:
        cmdline += " lynux.test=1"
    put(profile / "efiboot/loader/loader.conf", "default lynux.conf\ntimeout 3\neditor no\n")
    put(profile / "efiboot/loader/entries/lynux.conf", f"title Lynux\nlinux /arch/boot/{arch}/vmlinuz-{kernel}\ninitrd /arch/boot/{arch}/initramfs-{kernel}.img\noptions {cmdline}\n")
    if arch == "x86_64":
        put(profile / "syslinux/syslinux.cfg", f"DEFAULT lynux\nPROMPT 0\nTIMEOUT 30\nLABEL lynux\n  LINUX /arch/boot/x86_64/vmlinuz-linux\n  INITRD /arch/boot/x86_64/initramfs-linux.img\n  APPEND {cmdline}\n")
        put(profile / "syslinux/isolinux.cfg", "INCLUDE syslinux.cfg\n")
    put(profile / "grub/loopback.cfg", f'''menuentry "Lynux" {{
    linux /arch/boot/{arch}/vmlinuz-{kernel} {cmdline} img_dev=$imgdevpath img_loop=$isofile
    initrd /arch/boot/{arch}/initramfs-{kernel}.img
}}
''')
    return {"label": label, "kernel": kernel, "cmdline": cmdline}


def iso(args):
    if os.geteuid() != 0 or platform.machine() != args.arch:
        raise RuntimeError("Run in a privileged native-architecture Arch builder (scripts/run-builder.sh).")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}", args.version):
        raise ValueError("Invalid version")
    if not args.lock.is_dir():
        raise ValueError("Resolve harnesses first: python scripts/resolve.py --out work/lock")
    args.work.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(args.work).free < args.min_free_gib * 1024 ** 3:
        raise RuntimeError(f"Need {args.min_free_gib} GiB free space in build directory")
    args.out.mkdir(parents=True, exist_ok=True)
    meta = prepare_profile(args.arch, args.version, args.work / "profile", args.lock, args.test)
    output = args.out / f"lynux-{args.version}-{args.arch}.iso"
    meta.update({"schema": 1, "arch": args.arch, "version": args.version, "iso": output.name,
                 "test": args.test, "signed": False})
    (args.work / "build.json").write_text(json.dumps(meta, indent=2) + "\n")
    # Make the profile cache explicit. Upstream archiso versions differ in how
    # they choose between an implicit profile default and the host cache.
    cache = subprocess.check_output(["pacman-conf", "CacheDir"], text=True).splitlines()[0]
    profile_config = args.work / "profile/pacman.conf"
    profile_config.write_text(profile_config.read_text().replace("[options]", f"[options]\nCacheDir = {cache}", 1))
    snapshot = args.work / "repo-snapshot"
    command("python", ROOT / "scripts/prefetch-packages.py", "--config", args.work / "profile/pacman.conf",
            "--packages", args.work / "profile" / f"packages.{args.arch}", "--snapshot", snapshot)
    command("mkarchiso", "-v", "-w", args.work / "archiso", "-o", args.out, args.work / "profile",
            env={**os.environ, "LYNUX_PACMAN_DB_SNAPSHOT": str(snapshot.resolve())})
    if not output.exists():
        raise RuntimeError("archiso did not produce the expected ISO")
    for name in ("packages.txt", "harness-versions.json", "node-version.txt", "python-version.txt"):
        shutil.copy2(args.work / "archiso" / args.arch / "airootfs/usr/share/lynux" / name,
                     args.out / f"{args.arch}-{name}")
    shutil.copy2(args.work / "build.json", args.out / f"{args.arch}-build.json")
    print(f"Built unsigned ISO: {output}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    item = sub.add_parser("iso")
    item.add_argument("--arch", choices=("x86_64", "aarch64"), required=True)
    item.add_argument("--version", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d"))
    item.add_argument("--lock", type=Path, default=ROOT / "work/lock")
    item.add_argument("--work", type=Path, required=True)
    item.add_argument("--out", type=Path, default=ROOT / "out")
    item.add_argument("--min-free-gib", type=int, default=35)
    item.add_argument("--test", action="store_true", help="Add guest boot-report service kernel parameter")
    item = sub.add_parser("board")
    item.add_argument("--profile", type=Path, required=True)
    item.add_argument("--rootfs", type=Path, required=True, help="Built aarch64 airootfs directory")
    item.add_argument("--work", type=Path, required=True)
    item.add_argument("--out", type=Path, default=ROOT / "out")
    args = parser.parse_args()
    for key in ("lock", "work", "out", "profile", "rootfs"):
        if hasattr(args, key):
            setattr(args, key, getattr(args, key).resolve())
    if args.action == "iso":
        iso(args)
    else:
        from board import build_board
        build_board(args)


if __name__ == "__main__":
    main()
