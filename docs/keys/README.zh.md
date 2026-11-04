# Lynux 签名证书

[English](README.md) | **中文**

`lynux-2026.crt` 是 PEM 格式的公钥证书，`lynux-2026.cer` 是同一张证书的 DER 格式，固件导入 `db` 时一般用这个。私钥不在这里。

- Subject：`CN=Lynux Secure Boot 2026, O=Lynux`
- 密钥：RSA-3072
- 有效期：2026-11-04 02:37:26 UTC 至 2036-11-01 02:37:26 UTC（北京时间 10:37:26）
- SHA-256 指纹：`91:61:8C:6A:7F:66:88:2A:2C:4C:95:68:1A:12:2D:C4:A7:EF:E5:79:E8:8F:9A:1E:A8:40:A4:32:02:52:31:93`

信任之前，先确认 Release 附带的 `lynux.crt` 指纹和上面一致：

```sh
openssl x509 -in lynux-2026.crt -noout -subject -dates -fingerprint -sha256
```

然后把它加进固件的 `db`。原有的 PK、KEK 和厂商密钥都保留，别用这一张证书替换整个信任库。

自己构建镜像请用自己的密钥，项目私钥不对外提供。以后如果换密钥，会在这里发布新证书并另行通知。
