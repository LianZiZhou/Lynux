# Secure Boot

首版范围：直接烧录的 x86_64／ARM64 UEFI 镜像，固件允许用户向 `db` 添加证书。BIOS 和 Ventoy 使用普通启动；ARM64 Ventoy 不承诺 Secure Boot。

## 证书与签名

```bash
umask 077
openssl req -new -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
  -subj '/CN=Lynux Secure Boot/' -keyout db.key -out db.crt
openssl x509 -in db.crt -outform DER -out lynux.cer
openssl x509 -in db.crt -noout -fingerprint -sha256
```

将私钥安全保存在构建系统外部；Release 只包含证书和指纹。用户确认指纹后，通过固件的证书导入界面将 `lynux.cer` **添加**到 `db`。不同固件界面不同，不提供自动替换 PK、KEK 或清除厂商密钥的脚本。只支持 MOK 而不允许添加 db 的机器不属于这一直接启动路径。

启动链为固件 → 签名 systemd-boot → 签名 UKI。UKI 包含内核、固定命令行和 initramfs；initramfs 在挂载只读系统镜像前核对嵌入的 SHA-256。校验失败关机，不进入救援 shell。

普通 Ventoy initramfs 保留，未把它描述为受完整签名链保护。仅能通过 Ventoy 启动，不等于 Secure Boot 验证已通过。

## 验证下载

```bash
sha256sum -c SHA256SUMS
openssl x509 -in lynux.crt -pubkey -noout > release.pub
openssl dgst -sha256 -verify release.pub -signature SHA256SUMS.sig SHA256SUMS
```

应通过可信渠道核对证书指纹。这里的清单签名使用同一长期证书对应私钥，并非 Microsoft 官方签名。

QEMU 测试使用 virt-firmware 在临时变量存储中导入证书，要求来宾明确报告 SecureBoot=1。修改 UKI 和错误证书通过 `sbverify` 验证拒绝；修改根文件系统通过启动测试验证拒绝。真实固件对“未导入证书”和被修改 UKI 的拒绝行为还需按验收表实机检查。
