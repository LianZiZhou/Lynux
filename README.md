# Lynux

**English** | [中文](README.zh.md)

**vibe your system.** Lynux is a live Arch Linux + KDE system for fixing, installing and maintaining machines with AI coding agents.

It ships with five CLIs installed at build time: Codex, Claude Code, Kimi Code, DeepSeek Harness and OpenCode. You bring your own accounts and API keys.

Builds:

- x86_64 ISO, boots on BIOS and UEFI
- ARM64 ISO for machines with standard UEFI firmware
- A framework for building images for specific Armbian boards (no board is verified yet)

The system starts in English with the clock on UTC. Chinese (Simplified, Taiwan and Hong Kong input methods) and Japanese input are set up out of the box through Fcitx5.

## Status

The first dual-architecture release, [v2026.11.04.13.1](https://github.com/LianZiZhou/Lynux/releases/tag/v2026.11.04.13.1), passed the full CI pipeline in QEMU. Nothing has been tested on real hardware yet, and no ARM board is marked as supported. See [Testing](docs/validation.md) for what has and hasn't been checked.

## Using it

- Drop the ISO anywhere on a Ventoy drive, next to any other ISOs you have. Ventoy boots don't need Secure Boot.
- Or write the ISO straight to a USB stick. Keep other distro ISOs on any drive you can reach from the live system.
- KDE logs in as the normal `live` user. The admin terminal and the CLIs open a root session. SSH is off by default.
- Everything is lost on reboot unless you set up an encrypted LUKS2 file from the welcome window. That file keeps CLI logins and `/workspace`.
- A directly written UEFI image can boot with Secure Boot once you add our certificate. See [Secure Boot](docs/secure-boot.md).

"Installing other distros" means you and the AI use that distro's own tools and ISO. Lynux doesn't include a universal installer.

## Building

You need Linux on the same architecture you're building for, plus Docker. On Windows, use WSL2. Keep the build directory on a Linux filesystem, not NTFS. Plan for at least 35 GiB of free disk and 8 GiB of RAM.

```bash
# Resolve the dependency lock once. Needs aria2, Python >= 3.11, Node.js >= 22.19, npm, Git and GnuPG.
python3 scripts/resolve.py --out work/lock

# Build from that lock. Run each architecture on a native host.
bash scripts/run-builder.sh x86_64 iso --arch x86_64 \
  --version 2026.11.03.local --lock /src/work/lock --work /build/image --out /out
```

Use `aarch64` for ARM64. The script keeps the Docker volume with the output so you can sign it later, and prints the volume name.

GitHub Actions runs `Weekly Lynux images` every Monday at 00:17 UTC. You can also start it by hand. A manual run builds a test image signed with a throwaway certificate and doesn't publish anything unless you ask it to.

More docs:

- [Building and CI setup](docs/build.md)
- [Encrypted storage](docs/persistence.md)
- [Armbian boards](docs/armbian.md)
- [Testing](docs/validation.md)

## Development checks

```bash
bash tests/check.sh
ruff check runtime scripts tests
```

The LUKS2 test runs in a throwaway privileged container and only touches loop files it creates:

```bash
docker run --rm --privileged -e LYNUX_DISPOSABLE_TEST=1 \
  -v "$PWD:/src:ro" -w /src archlinux:base-devel bash -c \
  'bash scripts/setup-downloads.sh && pacman -S --noconfirm cryptsetup e2fsprogs util-linux && python tests/integration_state.py'
```

Layout: build config lives in `config/`, files copied into the image in `overlay/`, and the welcome app and helpers in `runtime/`. Never put API keys, S3 credentials or signing keys in any of them.
