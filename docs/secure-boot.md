# Secure Boot

**English** | [中文](secure-boot.zh.md)

Secure Boot works when you write the x86_64 or ARM64 UEFI image straight to a drive and your firmware lets you add a certificate to `db`. BIOS and Ventoy boots skip Secure Boot. On ARM64, Ventoy with Secure Boot isn't supported.

## How the chain works

Firmware → signed systemd-boot → signed UKI. The UKI bundles the kernel, a fixed command line and the initramfs. Before mounting the read-only system image, the initramfs checks it against the SHA-256 baked into the UKI. If the check fails, the machine powers off. It doesn't drop to a rescue shell.

The Ventoy boot path uses a normal initramfs and is not covered by this chain. A successful Ventoy boot doesn't mean anything was verified.

## Trusting the certificate

Check the certificate fingerprint against [docs/keys](keys/README.md) or another channel you trust. Then use your firmware's certificate import screen to **add** `lynux.cer` to `db`. Every firmware's menu looks different. We don't ship scripts that replace PK or KEK or remove vendor keys. Machines that only support MOK and won't let you add to `db` can't use this boot path.

## Making your own key

If you build and sign your own images:

```bash
umask 077
openssl req -new -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
  -subj '/CN=Lynux Secure Boot/' -keyout db.key -out db.crt
openssl x509 -in db.crt -outform DER -out lynux.cer
openssl x509 -in db.crt -noout -fingerprint -sha256
```

Keep the private key off the build machine. A release only includes the certificate and its fingerprint.

## Checking a download

```bash
sha256sum -c SHA256SUMS
openssl x509 -in lynux.crt -pubkey -noout > release.pub
openssl dgst -sha256 -verify release.pub -signature SHA256SUMS.sig SHA256SUMS
```

`SHA256SUMS.sig` is signed with the same long-term key as the boot files. It has nothing to do with Microsoft's signing.

## How it's tested

In QEMU, virt-firmware imports the certificate into a temporary variable store, and the guest has to report `SecureBoot=1`. `sbverify` has to reject a modified UKI and a wrong certificate, and a modified root filesystem has to fail to boot.

Not yet checked on real hardware: that firmware refuses to boot before the certificate is imported, and that it refuses a modified UKI. See [Testing](validation.md).
