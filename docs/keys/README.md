# Lynux signing certificate

**English** | [中文](README.zh.md)

`lynux-2026.crt` is the public certificate in PEM format. `lynux-2026.cer` is the same certificate in DER format, which is what firmware `db` import screens usually want. The private key is not stored here.

- Subject: `CN=Lynux Secure Boot 2026, O=Lynux`
- Key: RSA-3072
- Valid: 2026-11-04 02:37:26 UTC to 2036-11-01 02:37:26 UTC
- SHA-256 fingerprint: `91:61:8C:6A:7F:66:88:2A:2C:4C:95:68:1A:12:2D:C4:A7:EF:E5:79:E8:8F:9A:1E:A8:40:A4:32:02:52:31:93`

Before you trust it, check that the `lynux.crt` attached to a release has this fingerprint:

```sh
openssl x509 -in lynux-2026.crt -noout -subject -dates -fingerprint -sha256
```

Add it to your firmware's `db`. Keep the existing PK, KEK and vendor keys. Don't replace your whole trust database with this one certificate.

If you build your own images, use your own key. The project's private key isn't shared. If the key is ever rotated, a new certificate will be published here and announced.
