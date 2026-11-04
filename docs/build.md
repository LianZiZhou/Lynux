# Building and releasing

**English** | [中文](build.zh.md)

## Inputs

`scripts/resolve.py` resolves all five CLIs in one go. It writes a shared `manifest.json`, a full npm dependency lock for each npm-based tool, and the exact archiso commit. For Claude it uses the official signed manifest. It checks the release key fingerprint and records the native binary hashes for both platforms.

The lock directory is the input for one build. It never reuses an old `latest` cache, so re-resolve into a new directory. npm tarballs are downloaded in parallel with aria2, checked against their integrity hashes and loaded into the npm cache. Then `npm ci --offline` installs them with engine checks and platform-specific optional dependencies, and each tool's version and help output are checked. If upstream removes a file or breaks compatibility, the build fails. It doesn't skip the tool.

archiso's `customize_airootfs.sh` hook is marked deprecated upstream. The exact upstream commit is pinned in the lock. If upstream removes the hook, the build fails and the integration has to be updated. An un-customized image is never published.

## Downloads

All downloads go through `scripts/download.py`. By default that's 16 connections per file, 8 files at once and 1 MiB minimum chunks, with resume and TLS verification on. aria2 RPC is never opened. Tune it with `LYNUX_DOWNLOAD_CONNECTIONS` (1–16) and `LYNUX_DOWNLOAD_JOBS` (1–32). Servers without Range support may get fewer connections.

- **pacman** uses aria2 as its XferCommand. Before building, the full package list is resolved and prefetched into the package cache 8 files at a time. pacman still checks every package signature. The prefetch also saves package signatures from the repo database. If a package has no embedded signature, aria2 fetches the detached ones. Installs use the database snapshot from this run, so a rolling mirror update can't change versions halfway through.
- **CLI binaries, npm tarballs, the ARM rootfs, Ventoy and post-release checks** all use aria2. Small metadata files go through the same path, but always into a fresh temp file, so a resume can't splice together old and new `latest` content.
- **Claude** comes from Anthropic's official npm platform packages. The unpacked binary must match the SHA-256 in the verified manifest, so it's the same official native build. If the npm platform package isn't out yet, it falls back to the official download URL from the manifest.
- **CI Python tools**: pip resolves the wheel list, aria2 downloads and checks the wheels, then they're installed offline.

Not via aria2: installing aria2 itself (that needs the host package manager), Git, Docker images, Actions artifacts and npm/pip dependency resolution. S3 uploads use the SDK's multipart upload. Speed-ups never turn off hashes, package signatures or TLS checks.

Timeouts: 300 seconds per pacman package, 60 seconds per signature, 900 seconds for other single files and 1200 seconds for batches. A timeout fails the build. Unverified files are never accepted.

x86_64 builds run in Arch's official container. ARM64 gets its Arch Linux ARM rootfs from the Tsinghua TUNA HTTPS mirror and records its SHA-256. Packages installed into the image are still checked by pacman. The GeoIP mirror's HTTPS certificate failed verification in our dev setup, so we use a mirror that passes instead of turning TLS off. Override the bootstrap URL with `ALARM_ROOTFS_URL`. The recorded rootfs hash only shows what was downloaded. It isn't an upstream signature. You can also build on a verified native Arch Linux ARM host.

## Building locally

1. Resolve the shared dependency lock.
2. In a privileged Arch container on the native architecture, run `python /src/build iso --arch x86_64 --lock /src/work/lock --work /build/image --out /out`.
3. In the same build volume, run `scripts/seal.py` with the build work directory, the unsigned ISO, and your private key and certificate.
4. Test the signed ISO with `tests/image_matrix.py`, then `tests/ventoy_boot.py`.
5. Gather both architectures' signed ISOs, manifests, certificates and test reports, then run `scripts/publish.py --dry-run` to check everything is in place.

Mount the private key directory separately and read-only. Never copy it into the profile or rootfs. Example:

```bash
python scripts/seal.py --work /build/image \
  --iso /out/lynux-2026.11.03.local-x86_64.iso --key /keys/db.key --cert /keys/db.crt
```

`build iso` won't overwrite an existing work directory. Old ones are kept for debugging, so use a new path for each build.

To test the CLIs' model requests, run `bash /src/scripts/check-providers.sh x86_64 /build/image /out` inside the build container. It gives each CLI a temporary config, isolates them in a loopback-only network namespace, sends requests to local mock servers and ties the results to the rootfs hash. You don't need real model accounts.

Build speed:

- The build profile points pacstrap at the same cache the prefetch filled, so packages aren't downloaded twice. Build-tool dependencies are prefetched the same way.
- The ARM test firmware is built in its own step and cached by the pinned EDK2 commit and build script. On restore the commit and file hashes are checked. No keys or CLI logins are ever cached.
- x86_64 compresses the read-only system with Zstd level 15 and 1 MiB blocks, which builds and boots faster. ARM64 uses XZ with a 1 MiB dictionary, because that's the SquashFS decompressor the Arch Linux ARM kernel has. The build checks the target kernel's config for this. Zstd support in the initramfs doesn't mean SquashFS supports it too. Zstd images are usually bigger than XZ ones. The full ISO is published on S3, and each release's manifest has the actual size.

## GitHub setup

### Environments

Create three GitHub Environments:

- `Main`: used only by the release job. Under Deployment branches and tags pick **Selected branches and tags** and add one rule of type **Branch** named `main`. Add no tag or wildcard rules. Turn off **Allow administrators to bypass configured protection rules**.
- `Signing`: used to build images signed with the real key. Same branch rule and no-bypass setting as `Main`. No S3 credentials here.
- `Testing`: used for test builds. Any branch is allowed. **Don't put any secrets here.**

You don't need required reviewers or a wait timer, so the weekly build can run on its own. Real signing and publishing only happen for scheduled runs on `refs/heads/main`, or manual runs on `main` with `publish=true`. On any other branch, `publish=true` still only produces a test build with a throwaway certificate, and the release job is skipped.

Keep the S3 keys **only** in **Main → Environment secrets**. Don't also add them as repository secrets or share them through organization secrets. If you do, workflows on other branches can read those copies. A workflow `if` condition doesn't replace environment branch protection. PR checks don't use any environment. Don't add `pull_request_target` or similar workflows that would run untrusted PR code in `Main`. Anyone who can change environment rules or workflows on `main` is inside the trust boundary anyway.

### Variables and secrets

`Main → Environment variables`:

| Name | Purpose |
|---|---|
| `S3_ENDPOINT` | HTTPS S3 API endpoint |
| `S3_REGION` | AWS region. Use `auto` for R2 |
| `S3_BUCKET` | An existing bucket |
| `S3_PREFIX` | Object prefix. `lynux` is a good default |
| `DOWNLOAD_BASE_URL` | Public HTTPS URL for the bucket root, without the prefix |

`Settings → Secrets and variables → Actions → Variables` (repository level):

| Name | Purpose |
|---|---|
| `X86_RUNNER` / `ARM_RUNNER` | Optional runner label overrides. Each needs native x86_64 / ARM64 and privileged Docker |
| `DOWNLOAD_CONNECTIONS` / `DOWNLOAD_JOBS` | aria2 connections per file / files at once. Defaults 16 / 8 |

Environment secrets (never at repository level):

| Environment | Name | Purpose |
|---|---|---|
| `Main` | `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Upload access to the release bucket only |
| `Main` and `Signing` | `SECURE_BOOT_KEY_B64` | Base64 of the same PEM private key. Signs the release manifest in `Main` and the images in `Signing` |
| `Signing` | `SECURE_BOOT_CERT_B64` | Base64 of the matching PEM X.509 certificate |

The download domain must really serve the bucket publicly. The scripts don't create buckets, change access policies or set up DNS. The S3 service must support conditional writes with `If-None-Match: *`, which stops a version from being overwritten.

### What each kind of run does

- **PRs** run source checks and throwaway storage tests only. Nothing with release credentials.
- **Scheduled runs, or `publish=true` on `main`** fail if the long-term keys are missing.
- **Manual runs with `publish=false`** use a throwaway certificate and keep only logs and the run summary. No ISO or diagnostics are kept as Artifacts. If you want to keep a test image, build it locally.

GitHub-hosted runners first delete the preinstalled Android, .NET and GHC SDKs and the hosted tool cache to free space. If the 35 GiB check still fails, use a runner with more disk. This cleanup only runs on `github-hosted` runners and never touches self-hosted ones.

Image, firmware and boot-test steps log processes, CPU, memory, disk use and log size every minute. Setup, ARM firmware and image builds time out after 20, 35 and 60 minutes. When QEMU fails, the exit code and the end of its log are printed right away.

### Actions Artifacts

Artifacts are only used inside the weekly pipeline, to pass the dependency lock and the release images and reports between jobs. Failed runs and test builds upload no diagnostics. Verification reports from a successful release are saved with the Release and on S3.

The `Delete CI artifacts` workflow deletes them as soon as each workflow finishes, whether it passed, failed or was cancelled. It also sweeps all finished runs every hour as a backup, and skips runs still in progress. The 1-day retention set at upload is only a last resort in case cleanup breaks. It doesn't mean files normally stay for a day. The cleanup workflow never runs code from the triggering branch and has no S3 access. It doesn't touch S3 images, Release files, Actions logs or build caches.

Since intermediate files are gone once a run ends, start a new full manual run to rebuild. Don't try to re-run just the failed job.

## QEMU and Ventoy tests

The test tools explicitly install `qemu-hw-display-virtio-gpu` and `qemu-hw-display-virtio-gpu-pci`, plus `qemu-hw-display-virtio-vga` on x86. A device self-check runs before the image build. Don't install only the PCI package and expect it to pull in the base module. x86 uses a single VGA-compatible virtio GPU, ARM uses a virtio PCI GPU.

To re-test a published image, run the `Verify existing image` workflow by hand. Give it a release tag and pick an architecture. It downloads the ISO, certificate and dependency lock from the Release/S3 with aria2, checks the certificate against the ones in this repo, verifies the manifest signature and file hashes, then re-runs the tests. You can choose to re-test only Ventoy. It doesn't use old Artifacts or the signing key, and it doesn't upload or publish anything. Results go to the log and the run summary. In debug runs, a QEMU segfault captures a time-limited GDB backtrace. Crashes and guest boot failures still fail the test.

The Ventoy test only writes to fresh temporary disk files. The fixture installer's `dd` pipe uses `iflag=fullblock` so a short read can't truncate the EFI partition. After install, the EFI image is compared byte for byte against the one in the official archive, and the ISO copied to the data partition is hash-checked. Drive setup failures and guest boot failures are reported separately, so a broken test drive can't be mistaken for an incompatible ISO.

## How a release is published

Once both architectures pass, the release job checks that the boot reports are tied to the final ISO hashes, that all five CLI versions match across architectures, and that the BIOS, Ventoy and signing tests passed. Then it:

1. Claims a new version directory on S3 with a conditional write.
2. Uploads everything and downloads each file back over public HTTPS to check it.
3. Creates the GitHub Release.
4. Updates `latest.json`.

A failed version directory is kept for debugging. A re-run gets a new version number from the run attempt and never overwrites the old directory. If the Release is created but updating `latest` fails, the old `latest` still works and the log shows the failure. Old versions are never deleted automatically.

Each image is a snapshot of rolling repos. The manifest tells you exactly what went in, but rebuilding it byte for byte later won't work once upstream has moved on. For that you'd need to archive the package repos and every downloaded file yourself.
