# 构建与发布

## 构建输入

`scripts/resolve.py` 在一个任务中解析五套工具，生成共享的 `manifest.json`、每套 npm 工具的传递依赖锁和 archiso 的精确源码提交。Claude 使用官方签名 manifest，核对发行密钥指纹后记录两个平台的原生二进制摘要。

锁目录是一次构建的输入，不复用旧 `latest` 缓存；重新解析时使用新目录。npm 的锁定 tarball 先由 aria2 并发下载，按 integrity 校验并导入 npm 缓存，再使用 `npm ci --offline`，启用 engine 检查和平台可选依赖，安装后验证版本与帮助命令。上游删除资产或发生不兼容时构建失败，不跳过工具。

## 下载加速

通用下载入口为 `scripts/download.py`，默认每文件 16 个连接、8 个文件并发、1 MiB 最小分块，启用断点续传及 TLS 校验，不开放 aria2 RPC。可通过 `LYNUX_DOWNLOAD_CONNECTIONS`（1–16）和 `LYNUX_DOWNLOAD_JOBS`（1–32）调整。服务器不支持 Range 时连接数可能自动减少。

pacman 使用 aria2 的 XferCommand；镜像构建还会先解析完整软件包清单，以 8 文件并发方式预取到包缓存，随后仍由 pacman 校验软件包签名。CLI 原生二进制、npm 锁定 tarball、ARM rootfs、Ventoy 和发布后回读校验均使用 aria2。小型元数据也经同一入口，但每次新建临时文件，防止续传到更新后的 `latest` 内容。

Claude 优先使用 Anthropic 官方 npm 平台包提供的原生二进制，解包后必须匹配已验签 manifest 中的 SHA-256；它仍是官方原生版本。npm 平台包尚未发布时使用 manifest 对应的官方下载地址。

CI 的 Python 工具也先用 pip 解析 wheel 清单，再用 aria2 下载并校验，最后离线安装。初次安装 aria2 自身仍需宿主包管理器；Git、Docker 镜像、Actions artifacts 及 npm/pip 的依赖解析使用各自协议客户端。不会为加速关闭摘要、包签名或 TLS 校验。S3 上传继续使用 SDK 的分段上传。

x86_64 使用 Arch 官方容器作为构建宿主；ARM64 从清华 TUNA HTTPS 镜像获取 Arch Linux ARM rootfs 并记录 SHA-256，目标包仍通过 pacman 签名校验。原 GeoIP 镜像域名的 HTTPS 证书在开发环境中未能通过检查，因此使用可验证的 HTTPS 镜像，不关闭 TLS 或包签名校验。`ALARM_ROOTFS_URL` 可覆盖引导包地址。引导 rootfs 的摘要是下载记录，不声称它是上游签名认证；也可使用已经验证的原生 Arch Linux ARM 宿主。

archiso 的 `customize_airootfs.sh` 接口当前被上游标记为 deprecated。这里将上游精确提交锁在清单中；如果上游移除此接口，构建必须失败并更新集成，不能发布未定制的镜像。

## 本地流程

1. 解析共享依赖锁。
2. 在原生架构的特权 Arch 容器执行 `python /src/build iso --arch x86_64 --lock /src/work/lock --work /build/image --out /out`。
3. 在同一构建 volume 中使用 `scripts/seal.py`，传入 build 工作目录、unsigned ISO、外部私钥和证书。
4. 使用 `tests/image_matrix.py` 检查最终 signed ISO，再运行 `tests/ventoy_boot.py`。
5. 汇集两种架构的 signed ISO、清单、证书及测试报告，先运行 `scripts/publish.py --dry-run` 检查发布条件。

私钥目录应另行只读挂载，不能复制到 profile 或 rootfs。`seal.py` 的例子：

```bash
python scripts/seal.py --work /build/image \
  --iso /out/lynux-2026.11.03.local-x86_64.iso --key /keys/db.key --cert /keys/db.crt
```

`build iso` 不自动覆盖已有工作目录。旧工作目录保留用于诊断；重新构建使用新路径。

模型请求检查可在构建容器内执行 `bash /src/scripts/check-providers.sh x86_64 /build/image /out`。它为五套 CLI 创建临时配置，隔离到只有 loopback 的网络命名空间，对本地模拟服务发送请求，并将结果绑定到 rootfs 摘要；不需要真实模型账号。

## GitHub 配置

变量：

| 名称 | 用途 |
|---|---|
| `S3_ENDPOINT` | HTTPS S3 API endpoint |
| `S3_REGION` | AWS region；R2 可用 `auto` |
| `S3_BUCKET` | 已创建的 bucket |
| `S3_PREFIX` | 对象前缀，建议 `lynux` |
| `DOWNLOAD_BASE_URL` | 对应 bucket 根路径的公开 HTTPS 下载域名，不包含前缀 |
| `X86_RUNNER` / `ARM_RUNNER` | 可选的 runner 标签覆盖；分别需要原生 x86_64 / ARM64、特权 Docker |
| `DOWNLOAD_CONNECTIONS` / `DOWNLOAD_JOBS` | aria2 每文件连接数／并发文件数，默认 16／8 |

Secrets：

| 名称 | 用途 |
|---|---|
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | 仅限发布 bucket 的上传权限 |
| `SECURE_BOOT_KEY_B64` | PEM 私钥的 base64 编码 |
| `SECURE_BOOT_CERT_B64` | 对应 PEM X.509 证书的 base64 编码 |

下载域名需要真实公开读取权限和正确的内容服务；脚本不创建 bucket、不修改公开策略、不部署 DNS。S3 服务必须支持条件创建 `If-None-Match: *`，用于防止同名版本被覆盖。

PR 只执行源代码及一次性存储测试，不运行带发布凭据的任务。定时发布或 `publish=true` 缺少长期密钥时失败。手动 `publish=false` 使用临时证书，产物仅保存在 Actions artifacts。

GitHub 临时托管 runner 会先清理预装的 Android、.NET、GHC 和 hosted tool cache 以释放空间；35 GiB 预检仍失败时请配置有足够空间的 runner。这一步只在 `github-hosted` 执行，不清理自托管 runner 上的工具或项目。

## 发布事务

两个架构成功后，发布任务验证最终 ISO 与启动报告的摘要绑定、五套 CLI 版本一致，以及 BIOS、Ventoy 和签名完整性测试结果。先用条件写入占用独立版本目录，再上传并通过公开 HTTPS 逐个下载校验，然后创建 GitHub Release，最后更新 `latest.json`。

失败的版本目录保留诊断，重跑使用新的 run-attempt 版本号；不会覆盖原目录。若 Release 成功但 latest 更新失败，旧 latest 仍可用，日志会明确失败。历史版本不自动删除。

镜像是滚动快照，清单可追踪版本，但不承诺未来能够从已变化的上游仓库逐字节重建。若要长期可重建，需另行归档软件包仓库和全部下载资产。
