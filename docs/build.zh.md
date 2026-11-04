# 构建与发布

[English](build.md) | **中文**

## 构建输入

`scripts/resolve.py` 一次性解析五个 CLI，生成共享的 `manifest.json`、每个 npm 工具的完整依赖锁，以及 archiso 的精确提交。Claude 用的是官方签名的 manifest，脚本会核对发布密钥指纹，并记下两个平台原生二进制的哈希。

锁目录只对应一次构建，不复用旧的 `latest` 缓存，重新解析就换一个新目录。npm 的 tarball 先用 aria2 并发下载，按 integrity 校验后导入 npm 缓存，再用 `npm ci --offline` 安装（开启 engine 检查和平台可选依赖），装完检查每个工具的版本和帮助输出。上游删了文件或者出现不兼容，构建直接失败，不会跳过这个工具。

archiso 的 `customize_airootfs.sh` 钩子已被上游标为 deprecated。我们在锁里固定了上游提交。哪天上游删掉这个钩子，构建会失败，需要更新集成方式，绝不会发出没定制过的镜像。

## 下载

所有下载都走 `scripts/download.py`。默认每个文件 16 个连接、同时 8 个文件、最小分块 1 MiB，开启断点续传和 TLS 校验，不开 aria2 RPC。可以用 `LYNUX_DOWNLOAD_CONNECTIONS`（1–16）和 `LYNUX_DOWNLOAD_JOBS`（1–32）调整。服务器不支持 Range 的话，连接数可能会变少。

- **pacman** 的 XferCommand 用 aria2。构建前先解析完整的软件包列表，每次 8 个文件预取到包缓存里，每个包的签名仍由 pacman 校验。预取时也会保存仓库数据库里的包签名；没有内嵌签名的包，用 aria2 批量下载单独的签名文件。安装时固定用本轮解析的数据库快照，滚动镜像中途更新也不会导致版本变化。
- **CLI 二进制、npm tarball、ARM rootfs、Ventoy 和发布后的回读校验** 都用 aria2。小的元数据文件也走同一个入口，但每次都写到新的临时文件，避免把旧的和新的 `latest` 内容续传拼在一起。
- **Claude** 用 Anthropic 官方 npm 平台包里的原生二进制，解包后必须和已验签 manifest 里的 SHA-256 一致，所以就是官方原生版本。npm 平台包还没发出来时，改用 manifest 里的官方下载地址。
- **CI 的 Python 工具**：先用 pip 解析 wheel 列表，再用 aria2 下载并校验，最后离线安装。

不走 aria2 的：安装 aria2 本身（得靠宿主机包管理器）、Git、Docker 镜像、Actions artifacts，以及 npm/pip 的依赖解析。S3 上传用 SDK 的分段上传。加速从来不会关掉哈希、包签名或 TLS 校验。

超时：pacman 单个包 300 秒，签名 60 秒，其他单个文件 900 秒，批量下载 1200 秒。超时就构建失败，绝不接受没校验过的文件。

x86_64 在 Arch 官方容器里构建。ARM64 从清华 TUNA 的 HTTPS 镜像下载 Arch Linux ARM rootfs 并记录 SHA-256，装进镜像的包照样由 pacman 校验签名。原来的 GeoIP 镜像域名在开发环境里 HTTPS 证书校验不过，所以换了一个能通过校验的镜像，而不是关掉 TLS。可以用 `ALARM_ROOTFS_URL` 改引导包地址。记下的 rootfs 哈希只说明下载到的是什么，不是上游签名。也可以直接在验证过的原生 Arch Linux ARM 机器上构建。

## 本地构建

1. 生成共享的依赖锁。
2. 在原生架构的特权 Arch 容器里执行 `python /src/build iso --arch x86_64 --lock /src/work/lock --work /build/image --out /out`。
3. 在同一个构建 volume 里运行 `scripts/seal.py`，传入构建工作目录、未签名的 ISO、私钥和证书。
4. 用 `tests/image_matrix.py` 测签好名的 ISO，再跑 `tests/ventoy_boot.py`。
5. 把两种架构的签名 ISO、清单、证书和测试报告放到一起，先跑 `scripts/publish.py --dry-run` 确认发布条件都齐了。

私钥目录单独只读挂载，绝不要拷进 profile 或 rootfs。例子：

```bash
python scripts/seal.py --work /build/image \
  --iso /out/lynux-2026.11.03.local-x86_64.iso --key /keys/db.key --cert /keys/db.crt
```

`build iso` 不会覆盖已有的工作目录。旧目录留着方便排查，每次构建换个新路径。

想测 CLI 的模型请求，在构建容器里执行 `bash /src/scripts/check-providers.sh x86_64 /build/image /out`。它给每个 CLI 建临时配置，关进只有 loopback 的网络命名空间，向本地模拟服务发请求，并把结果和 rootfs 哈希绑定。不需要真实的模型账号。

构建速度：

- 构建 profile 让 pacstrap 用预取时填好的那个缓存，包不会下两遍。构建工具的依赖也是同样先预取。
- ARM 测试固件单独一步编译，按固定的 EDK2 提交和编译脚本缓存。恢复缓存时会核对提交和文件哈希。私钥和 CLI 登录信息从不进缓存。
- x86_64 的只读系统用 Zstd level 15、1 MiB 块压缩，构建和启动都更快。ARM64 用 XZ（1 MiB 字典），因为 Arch Linux ARM 内核的 SquashFS 只带了这个解压器，构建时会检查目标内核配置。initramfs 支持 Zstd 不代表 SquashFS 也支持。Zstd 镜像一般比 XZ 大一些。完整 ISO 发布在 S3 上，实际大小看每期的清单。

## GitHub 配置

### Environments

建三个 GitHub Environment：

- `Main`：只给发布任务用。Deployment branches and tags 选 **Selected branches and tags**，只加一条类型为 **Branch**、名称为 `main` 的规则，不加 tag 或通配符规则。关掉 **Allow administrators to bypass configured protection rules**。
- `Signing`：构建正式签名镜像用。分支规则和禁止绕过的设置跟 `Main` 一样。这里不放 S3 凭据。
- `Testing`：测试构建用，允许所有分支。**这里不放任何 secret。**

不需要设置 required reviewers 或 wait timer，周更可以自动跑。只有 `refs/heads/main` 上的定时运行，或者 `main` 上 `publish=true` 的手动运行，才会做正式签名和发布。其他分支就算设了 `publish=true`，也只出临时证书签名的测试构建，发布任务会跳过。

S3 密钥**只**放在 **Main → Environment secrets** 里。不要再存一份到仓库级 secrets，也不要通过组织级 secrets 授权给这个仓库，否则其他分支的工作流也能读到这些副本。工作流里的 `if` 条件替代不了环境的分支保护。PR 检查不使用任何环境。不要加 `pull_request_target` 之类会把不可信 PR 代码带进 `Main` 的工作流。能改环境规则或 `main` 上工作流的管理员，本来就在信任范围之内。

### 变量和密钥

`Main → Environment variables`：

| 名称 | 用途 |
|---|---|
| `S3_ENDPOINT` | HTTPS 的 S3 API 地址 |
| `S3_REGION` | AWS region，R2 填 `auto` |
| `S3_BUCKET` | 已经建好的 bucket |
| `S3_PREFIX` | 对象前缀，建议用 `lynux` |
| `DOWNLOAD_BASE_URL` | bucket 根目录对应的公开 HTTPS 下载地址，不带前缀 |

`Settings → Secrets and variables → Actions → Variables`（仓库级）：

| 名称 | 用途 |
|---|---|
| `X86_RUNNER` / `ARM_RUNNER` | 可选，覆盖 runner 标签。分别需要原生 x86_64 / ARM64 和特权 Docker |
| `DOWNLOAD_CONNECTIONS` / `DOWNLOAD_JOBS` | aria2 每个文件的连接数 / 同时下载的文件数，默认 16 / 8 |

Environment secrets（都不要放在仓库级）：

| 环境 | 名称 | 用途 |
|---|---|---|
| `Main` | `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | 只有发布 bucket 的上传权限 |
| `Main` 和 `Signing` | `SECURE_BOOT_KEY_B64` | 同一把 PEM 私钥的 base64。在 `Main` 里签发布清单，在 `Signing` 里签镜像 |
| `Signing` | `SECURE_BOOT_CERT_B64` | 对应 PEM X.509 证书的 base64 |

下载域名必须真的能公开访问这个 bucket。脚本不会建 bucket、改访问策略或配 DNS。S3 服务必须支持 `If-None-Match: *` 条件写入，防止同一个版本被覆盖。

### 各种运行分别做什么

- **PR**：只跑源码检查和一次性的存储测试，不碰任何发布凭据。
- **定时运行，或 `main` 上 `publish=true`**：缺长期密钥就失败。
- **手动运行且 `publish=false`**：用临时证书，只留日志和运行摘要，不把 ISO 或诊断文件存成 Artifacts。想留测试镜像请在本地构建。

GitHub 托管的 runner 会先删掉预装的 Android、.NET、GHC 和 hosted tool cache 腾空间。35 GiB 检查还是不过，就换一个磁盘更大的 runner。这一步只在 `github-hosted` 上执行，不会动自托管 runner。

镜像、固件和启动测试阶段每分钟记录一次进程、CPU、内存、磁盘占用和日志大小。环境准备、ARM 固件和镜像构建的超时分别是 20、35、60 分钟。QEMU 失败时会马上打印退出码和日志末尾。

### Actions Artifacts

Artifacts 只在周更流水线内部用，用来在任务之间传依赖锁和正式发布要用的镜像、报告。失败的运行和测试构建不上传诊断文件。正式发布成功后的验证报告随 Release 和 S3 一起保存。

`Delete CI artifacts` 工作流会在每个工作流结束后马上删掉它的 Artifacts，不管成功、失败还是取消。另外每小时扫一遍所有已结束的运行兜底，还在跑的会跳过。上传时设的 1 天保留期只是清理坏掉时的最后保险，不是说正常情况下会留一天。清理工作流不执行触发分支的代码，也碰不到 S3。S3 上的镜像、Release 附件、Actions 日志和构建缓存都不在清理范围内。

运行结束后中间文件就没了，想重新构建请重新手动跑一次完整流程，不要只重跑失败的那个 job。

## QEMU 和 Ventoy 测试

测试工具会明确安装 `qemu-hw-display-virtio-gpu` 和 `qemu-hw-display-virtio-gpu-pci`，x86 另外装 `qemu-hw-display-virtio-vga`，并在构建镜像前先做一次设备自检。不要只装 PCI 包然后指望它自动带上基础模块。x86 用一块兼容 VGA 的 virtio 显卡，ARM 用 virtio PCI 显卡。

想复测已发布的镜像，手动运行 `Verify existing image` 工作流，填入 Release tag 并选架构。它会用 aria2 从 Release/S3 下载 ISO、证书和依赖锁，先核对证书是不是仓库里登记过的那张，再验证清单签名和文件哈希，然后重跑测试。可以选择只测 Ventoy。它不用旧的 Artifacts，也不用签名私钥，不上传也不发布任何东西，结果写在日志和运行摘要里。调试运行中如果 QEMU 段错误，会抓一份限时的 GDB 回溯。崩溃和来宾启动失败照样算测试失败。

Ventoy 测试只写新建的临时磁盘文件。夹具安装器的 `dd` 管道用了 `iflag=fullblock`，防止读不满导致 EFI 分区被截断。装完之后会把 EFI 镜像和官方压缩包里的原版逐字节比对，并校验拷到数据分区的 ISO 哈希。测试盘制作失败和来宾启动失败分开报告，不会把坏掉的测试盘误判成 ISO 不兼容。

## 发布流程

两种架构都通过后，发布任务会检查：启动报告和最终 ISO 哈希对得上，五个 CLI 在两种架构上版本一致，BIOS、Ventoy 和签名测试都通过了。然后：

1. 用条件写入在 S3 上占一个新的版本目录。
2. 上传所有文件，再通过公开 HTTPS 逐个下载回来校验。
3. 创建 GitHub Release。
4. 更新 `latest.json`。

失败的版本目录留着方便排查。重跑会根据 run attempt 生成新的版本号，不会覆盖旧目录。如果 Release 建好了但 `latest` 更新失败，旧的 `latest` 依然可用，日志里会写明失败。历史版本不会自动删除。

每个镜像都是滚动仓库的一个快照。清单能告诉你具体装了什么，但上游变了之后，没法再逐字节重建出一模一样的镜像。要做到这一点，得自己把软件包仓库和所有下载过的文件都存档下来。
