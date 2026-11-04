"""Build board-specific disk images without assuming bootloader offsets or DTB names."""
import glob
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

from build import command, put
from loop_devices import wait_partitions


def validate(profile):
    if profile.get("schema") != 1 or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", profile["id"]):
        raise ValueError("Invalid board profile")
    arm = profile["armbian"]
    if not re.fullmatch(r"[a-f0-9]{40}", arm["commit"]):
        raise ValueError("Pin an exact Armbian commit; template is not a supported device")
    if any("REPLACE" in str(profile[k]) for k in ("dtb", "kernel_image")) or "REPLACE" in arm["board"]:
        raise ValueError("Fill board, kernel and DTB fields")
    if not profile["bootloader_writes"]:
        raise ValueError("Explicit bootloader offsets required; consult the board's Armbian layout")
    if profile["partition_start_mib"] < 1 or profile["boot_mib"] < 128:
        raise ValueError("Invalid disk layout")
    for write in profile["bootloader_writes"]:
        path = Path(write["source"])
        if path.is_absolute() or ".." in path.parts or write["offset_bytes"] < 0:
            raise ValueError("Invalid bootloader write")
    if profile["image_mib"] <= profile["partition_start_mib"] + profile["boot_mib"] + 1024:
        raise ValueError("Image too small")


def one(pattern):
    found = list(glob.glob(str(pattern)))
    if len(found) != 1:
        raise ValueError(f"Expected exactly one artifact for {pattern}; got {len(found)}")
    return Path(found[0])


def build_board(args):
    profile = json.loads(args.profile.read_text())
    validate(profile)
    if os.geteuid() != 0 or platform.machine() != "aarch64":
        raise ValueError("Board image assembly requires root on native ARM64 Linux")
    args.work.mkdir(parents=True, exist_ok=False)
    args.out.mkdir(parents=True, exist_ok=True)
    arm = profile["armbian"]
    source = args.work / "armbian"
    command("git", "clone", "--no-checkout", arm["repository"], source)
    command("git", "-C", source, "checkout", "--detach", arm["commit"])
    patches = args.profile.parent / arm["userpatches"]
    if patches.exists():
        shutil.copytree(patches, source / "userpatches", dirs_exist_ok=True)
    for kind in ("kernel", "uboot"):
        command(source / "compile.sh", kind, f"BOARD={arm['board']}", f"BRANCH={arm['branch']}",
                "KERNEL_CONFIGURE=no", "SHARE_LOG=no", cwd=source)
    extracted = args.work / "extracted"
    extracted.mkdir()
    for field in ("kernel_package_glob", "dtb_package_glob", "uboot_package_glob"):
        package = one(source / "output/debs" / profile[field])
        command("dpkg-deb", "--extract", package, extracted)
    modules = list((extracted / "lib/modules").glob("*")) + list((extracted / "usr/lib/modules").glob("*"))
    if len(modules) != 1:
        raise ValueError("Ambiguous or missing kernel modules")
    kernel_version = modules[0].name
    kernel = one(extracted / "boot" / profile["kernel_image"])
    dtbs = [p for p in (extracted / "boot").rglob("*.dtb") if p.as_posix().endswith("/" + profile["dtb"])]
    if len(dtbs) != 1:
        raise ValueError("DTB does not uniquely match kernel output")
    stage = args.work / "rootfs"
    stage.mkdir()
    command("rsync", "-aHAX", "--numeric-ids", str(args.rootfs) + "/", str(stage) + "/")
    shutil.rmtree(stage / "usr/lib/modules")
    shutil.copytree(modules[0], stage / "usr/lib/modules" / kernel_version, symlinks=True)
    for filename in profile["firmware"]:
        path = (args.profile.parent / filename).resolve(strict=True)
        shutil.copytree(path, stage / "usr/lib/firmware", dirs_exist_ok=True)
    put(stage / "etc/mkinitcpio.conf", 'MODULES=(loop squashfs overlay)\nHOOKS=(base udev modconf archiso archiso_loop_mnt block filesystems keyboard shutdown)\n')
    command("arch-chroot", stage, "depmod", "-a", kernel_version)
    command("arch-chroot", stage, "mkinitcpio", "-k", kernel_version, "-g", "/boot/board-initramfs.img")
    initramfs = args.work / "initramfs.img"
    shutil.move(stage / "boot/board-initramfs.img", initramfs)
    put(stage / "usr/share/lynux/board.json", json.dumps(profile, indent=2) + "\n")
    # The board image is still a Live system: store a squashfs, not a writable installed root.
    squashfs = args.work / "airootfs.sfs"
    command("mksquashfs", stage, squashfs, "-noappend", "-comp", "xz", "-b", "1M")
    label = "LYNX" + hashlib.sha256(profile["id"].encode()).hexdigest()[:12].upper()
    image = args.out / f"lynux-{profile['id']}.img"
    with image.open("xb") as stream:
        stream.truncate(profile["image_mib"] * 1024 ** 2)
    start = profile["partition_start_mib"]
    boot_end = start + profile["boot_mib"]
    # MBR is intentional: many SBC boot ROMs occupy GPT metadata sectors.
    command("parted", "-s", image, "mklabel", "msdos", "mkpart", "primary", "fat32", f"{start}MiB",
            f"{boot_end}MiB", "mkpart", "primary", "ext4", f"{boot_end}MiB", "100%")
    intervals = []
    with image.open("r+b") as stream:
        for write in profile["bootloader_writes"]:
            binary = (extracted / write["source"]).resolve(strict=True)
            if not binary.is_relative_to(extracted.resolve()) or not binary.is_file():
                raise ValueError("Bootloader source escapes extracted package")
            begin, end = write["offset_bytes"], write["offset_bytes"] + binary.stat().st_size
            if end > start * 1024 ** 2 or (begin < 512 and end > 440):
                raise ValueError("Bootloader would overwrite partition table or filesystem")
            if any(begin < b and end > a for a, b in intervals):
                raise ValueError("Bootloader writes overlap")
            intervals.append((begin, end))
            stream.seek(begin)
            with binary.open("rb") as payload:
                shutil.copyfileobj(payload, stream)
    loop = subprocess.check_output(["losetup", "--find", "--show", "--partscan", str(image)], text=True).strip()
    mount = args.work / "mount"
    mount.mkdir()
    mounted = []
    created_nodes = []
    try:
        command("udevadm", "settle")
        created_nodes = wait_partitions(loop)
        command("mkfs.vfat", "-F", "32", loop + "p1")
        command("mkfs.ext4", "-F", "-L", label, loop + "p2")
        command("mount", loop + "p2", mount)
        mounted.append(mount)
        (mount / "arch/aarch64").mkdir(parents=True)
        shutil.copy2(squashfs, mount / "arch/aarch64/airootfs.sfs")
        (mount / "boot").mkdir(exist_ok=True)
        command("mount", loop + "p1", mount / "boot")
        mounted.append(mount / "boot")
        shutil.copy2(kernel, mount / "boot/Image")
        shutil.copy2(initramfs, mount / "boot/initramfs.img")
        (mount / "boot/dtbs" / Path(profile["dtb"]).parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(dtbs[0], mount / "boot/dtbs" / profile["dtb"])
        put(mount / "boot/extlinux/extlinux.conf", f"DEFAULT lynux\nLABEL lynux\n LINUX /Image\n INITRD /initramfs.img\n FDT /dtbs/{profile['dtb']}\n APPEND archisobasedir=arch archisolabel={label} cow_spacesize=50% {profile['kernel_args']}\n")
        command("sync")
    finally:
        for target in reversed(mounted):
            command("umount", target)
        command("losetup", "-d", loop)
        for node in created_nodes:
            node.unlink(missing_ok=True)
    command("xz", "-T0", "-6", image)
    print(f"Created {image}.xz; hardware verification: {profile['verified']}")
