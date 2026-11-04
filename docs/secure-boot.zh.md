# Secure Boot

[English](secure-boot.md) | **中文**

把 x86_64 或 ARM64 的 UEFI 镜像直接写进盘里，并且固件允许你往 `db` 里加证书，就能用 Secure Boot。BIOS 和 Ventoy 启动不走 Secure Boot。ARM64 上的 Ventoy 不支持 Secure Boot。

## 启动链

固件 → 签过名的 systemd-boot → 签过名的 UKI。UKI 里打包了内核、固定的启动参数和 initramfs。initramfs 在挂载只读系统镜像之前，会用 UKI 里写死的 SHA-256 校验它。校验不过就直接关机，不会进救援 shell。

Ventoy 启动用的是普通 initramfs，不在这条签名链里。能从 Ventoy 启动，不代表做过任何校验。

## 信任证书

先对照 [docs/keys](keys/README.zh.md) 或其他可信渠道核对证书指纹。然后在固件的证书导入界面里把 `lynux.cer` **添加**到 `db`。每家固件的菜单都不一样。我们不提供替换 PK、KEK 或删除厂商密钥的脚本。只支持 MOK、不让加 `db` 的机器用不了这条启动路径。

## 自己生成密钥

如果你要自己构建并签名镜像：

```bash
umask 077
openssl req -new -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
  -subj '/CN=Lynux Secure Boot/' -keyout db.key -out db.crt
openssl x509 -in db.crt -outform DER -out lynux.cer
openssl x509 -in db.crt -noout -fingerprint -sha256
```

私钥不要放在构建机上。Release 里只有证书和指纹。

## 校验下载

```bash
sha256sum --ignore-missing -c SHA256SUMS
openssl x509 -in lynux.crt -pubkey -noout > release.pub
openssl dgst -sha256 -verify release.pub -signature SHA256SUMS.sig SHA256SUMS
```

`SHA256SUMS.sig` 用的是和启动文件同一把长期密钥签的，跟微软的签名没有关系。

## 怎么测的

在 QEMU 里用 virt-firmware 把证书导入临时变量存储，要求来宾报告 `SecureBoot=1`。改过的 UKI 和错误的证书必须被 `sbverify` 拒绝，改过的根文件系统必须启动失败。

还没在真机上确认的：没导入证书时固件拒绝启动，以及固件拒绝改过的 UKI。见[测试说明](validation.zh.md)。
