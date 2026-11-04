# Lynux 正式签名证书

`lynux-2026.crt` 是 PEM 公钥证书；`lynux-2026.cer` 是相同证书的 DER 形式，可用于固件 `db` 导入。这里不保存私钥。

- Subject：`CN=Lynux Secure Boot 2026, O=Lynux`
- 公钥：RSA-3072
- 有效期：北京时间 2026-11-04 10:37:26 至 2036-11-01 10:37:26
- SHA-256 指纹：`91:61:8C:6A:7F:66:88:2A:2C:4C:95:68:1A:12:2D:C4:A7:EF:E5:79:E8:8F:9A:1E:A8:40:A4:32:02:52:31:93`

核对发布附带的 `lynux.crt` 与此指纹一致后，再向固件 `db` 添加信任。保留机器原有 PK、KEK 和厂商密钥；不要用此证书替换整套信任数据库。

```sh
openssl x509 -in lynux-2026.crt -noout -subject -dates -fingerprint -sha256
```

自编译镜像可使用自己的密钥，不应使用或请求项目的私钥。私钥轮换时需要发布新证书并明确通知使用者。
