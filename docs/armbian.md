# Armbian boards

**English** | [中文](armbian.zh.md)

The generic ARM64 ISO only boots on machines with working UEFI firmware. Most SBCs don't have that, and swapping in a DTB from Armbian isn't enough. A board also needs the right kernel config, modules, firmware, U-Boot/SPL, disk layout and boot arguments.

So for a specific board you build a separate disk image from an Armbian board profile.

## Adding a board

Copy `config/boards/template.json` to a new file and fill in:

- The Armbian repo commit (full 40-character hash), board ID, kernel branch and `userpatches` directory.
- Patterns for the kernel, DTB and U-Boot `.deb` files. Each pattern must match exactly one file.
- The kernel file name and DTB path inside the extracted packages, plus any extra firmware directories.
- Image size, the reserved bootloader area and the boot partition size.
- A `source` and `offset_bytes` for every bootloader blob to write. `source` is relative to the unpacked `.deb` root.
- The serial console and any kernel arguments the board needs.

The template deliberately has no default bootloader offset. If you leave it unfilled, the build refuses to run.

## Building

Run this on native ARM64 Linux, using an ARM64 rootfs you've already built:

```bash
python build board --profile config/boards/my-board.json \
  --rootfs /build/image/archiso/aarch64/airootfs \
  --work /build/my-board --out /out
```

The host needs Armbian's build dependencies (and Docker if you use its container build), `dpkg-deb`, parted, mkfs tools, arch-chroot, rsync and xz. The script runs Armbian's kernel and U-Boot targets and only unpacks the resulting packages. It never runs Debian maintainer scripts.

## Limits

The adapter currently produces one layout: MBR, a FAT boot partition, an ext4 root partition and U-Boot extlinux. Boards that need GPT, a vendor partition table, FIT images or a different boot protocol need code changes in the adapter. Renaming things in the profile won't make them work.

## Marking a board verified

`verified` is false by default. Only set it to true after you've recorded the board, hardware revision, build commit, boot log and results for display, input, network and storage. No board is verified yet.
