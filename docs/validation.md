# Testing

**English** | [中文](validation.zh.md)

## Automated checks

| Check | Run by | Passes when |
|---|---|---|
| Lint and unit tests | `tests/check.sh`, ruff | Checksums, locks, paths and release failure handling behave as expected |
| Encrypted storage | `tests/integration_state.py` | LUKS2, ext4 and bind mounts work on throwaway loop files |
| Model API calls | `scripts/check-providers.sh` | All five CLIs return the expected text from mock Responses, Chat Completions and Messages servers in an isolated network namespace |
| BIOS/UEFI, CD and USB | `tests/qemu_boot.py` | The guest reports boot success, CLI help works offline, Plasma and Fcitx are running |
| Secure Boot | `tests/image_matrix.py` | `SecureBoot=1`, bad signatures are rejected, a damaged root filesystem refuses to boot |
| Welcome window | `lynux-welcome --check` during the image build | Every page loads in every language with no QML errors |
| Welcome translations | `tests/test_welcome_strings.py` | Every key the QML uses exists in all languages, with matching placeholders |
| Ventoy | `tests/ventoy_boot.py` | The ISO boots from a throwaway Ventoy disk. The Ventoy version is logged |
| Release | `scripts/publish.py` | Reports match the final ISO hash, both architectures are present, public downloads verify |

QEMU turns on the in-guest checks with an `opt/lynux-test` fw_cfg entry and the SMBIOS product name `Lynux CI boot verification`. The final ISO's command line isn't changed and nothing is re-signed. ARM kernels without `CONFIG_FW_CFG_SYSFS` rely on the SMBIOS marker.

A timeout counts as a failure. Without `/dev/kvm` the tests use TCG emulation, with a per-boot limit of 600 seconds on x86_64 and 1200 seconds on ARM64. ARM VMs get 4 vCPUs and extra time for the offline CLI checks and desktop startup under emulation. A clear kernel, mount or check failure ends the test right away.

WSL uses TCG by default, because `/dev/kvm` existing doesn't prove nested virtualization works. If you know KVM works there, set `LYNUX_QEMU_ACCEL=kvm`.

The EDK2 firmware in Arch's ARM repo doesn't support Secure Boot. CI builds an ArmVirt test firmware with Secure Boot from a pinned EDK2 stable commit. That firmware is only for QEMU tests. We don't ship it as firmware for physical ARM devices.

## Manual checks before a first release or desktop change

Automated process checks don't replace these:

1. Type Simplified Pinyin, Taiwan Zhuyin, Hong Kong Cangjie/Quick/Jyutping and Japanese in Konsole, a Qt editor and Firefox. Check the candidate window, committing text and switching between methods.
2. Set up each of the five CLIs and log in with a real account. CI only talks to mock servers. Any cost it prints is the client's estimate for mock tokens, not real spending.
3. In the welcome window: pick an ISO, mount it read-only, create and unlock a container, edit the workspace, reboot and check it's all still there. Lock while an AI tool and a Dolphin window are open in `/workspace`: both should be listed, and ending them should let the lock finish.
4. Switch the language in the welcome window, log out, and check Plasma and new Konsole windows come back in that language. Switch back to English.
5. On a throwaway target disk, do an example Arch install, chroot in and repair the bootloader. Write down which disk you used. Never do this on your development machine's system disk.
6. On physical UEFI machines of both architectures: untrusted certificate is refused, boot works after importing it, a modified UKI is refused, and display, Wi-Fi and input devices work.
7. Recovery after power loss, a full disk, pulling the drive, upgrading across weekly releases, and opening the shared workspace from the other architecture.

Each report should list the version, ISO SHA-256, environment and the steps you took. The repo doesn't contain any hardware test results yet, so passing CI doesn't mean Lynux works on all hardware.

## Results so far

Development setup: Windows + WSL2 on x86_64, builds in an isolated Arch container, tests in QEMU.

### 2026-11-04: local x86_64 test build

Version `2026.11.03.local7` (named after the day the build started). Signed ISO `lynux-2026.11.03.local7-x86_64-signed.iso`, with a temporary test certificate.

Passed:

- 32 unit tests, Python lint, ShellCheck and actionlint.
- Real LUKS2/ext4/loop/bind-mount tests, including wrong password, re-unlock, format rejection and cleanup of temporary plaintext.
- Offline help and version checks for all five CLIs, plus mock model requests on an isolated network. No real accounts were used.
- x86_64 BIOS boot from CD and emulated USB. UEFI Secure Boot from CD and emulated USB, with the guest reporting `SecureBoot=1`.
- Plain UEFI boot from Ventoy 1.1.18, with the ISO in nested folders whose names contain spaces and Chinese characters.
- Wrong certificate and modified UKI rejected by signature checks. Modified rootfs refused at boot.
- Every input method ID in the preset config matches an engine installed in the image. The welcome window drew correctly on a real guest desktop.

ISO SHA-256: `9251571949ca24d3857dd868e8441bd18bd0ed62b75bfcdadd35b760f8e1dd36`. Per-test reports and screenshots are in the local `out/` folder, tied to the final ISO and rootfs hashes.

ARM64 boot tests and a real release weren't done at this stage. Both were done later in CI (see below).

### 2026-11-04: re-test on GitHub runners

Version `2026.11.04.5.1`, signed with the long-term certificate. x86_64 ISO SHA-256: `8eaf26e840253b4d2b3ac515bba69514c84356bc2e82125b28beee95826148da`.

- [Direct boot re-test](https://github.com/LianZiZhou/Lynux/actions/runs/41775115851): BIOS CD/USB, UEFI Secure Boot CD/USB and the damaged-rootfs check all passed. The Ventoy test failed in this run, so the run as a whole failed.
- After fixing how the test drive was written, the [Ventoy-only re-test](https://github.com/LianZiZhou/Lynux/actions/runs/41783213425) passed. It used Ventoy 1.1.18 and an ISO path with spaces and Chinese characters. The EFI partition matched the official image byte for byte, and the guest returned `LYNUX_BOOT_OK`.

Both runs used the same ISO. Only the test tools and drive setup changed. This wasn't a release.

### 2026-11-04: first dual-architecture release

The [full pipeline](https://github.com/LianZiZhou/Lynux/actions/runs/41804923096) passed and published [2026.11.04.13.1](https://github.com/LianZiZhou/Lynux/releases/tag/v2026.11.04.13.1). Both architectures passed signing, offline CLI checks in the guest, mock model requests, UEFI Secure Boot from CD and USB, the tamper tests and plain UEFI boot from Ventoy. x86_64 also passed BIOS boot from CD and USB.

| Arch | Release ISO SHA-256 |
|---|---|
| x86_64 | `ceef499ffe920f48a62c36fc1919f836fdc3302f6440cd123cc83b092d837068` |
| aarch64 | `6944c35ae798b51cd26baa294edb2b132ea88697f655fe0d5bbd363d4f9ecbda` |

Both ISOs are on S3, and their hashes were checked after downloading them back over public HTTPS. The [latest index](https://lynux.lzz.moe/lynux/latest.json) is updated. The release is signed with the long-term certificate. Its fingerprint is in [docs/keys](keys/README.md).

The ARM GitHub runner uses TCG emulation, so each of the three full boot tests took about 9 minutes. Real ARM hardware will be faster.

Still not done: testing on real Armbian boards, logging in with real accounts, trying every input method in every target app, and full installs of other distros. These are QEMU results only and don't replace the manual checks above.
