# Lynux

**vibe your system** — Arch + KDE 的 AI 运维 Live Linux。

提供 x86_64 BIOS/UEFI 镜像、ARM64 UEFI 主线镜像构建，以及 Armbian 板级适配框架。五套 CLI 在镜像构建时安装完成：Codex、Claude Code、Kimi Code、DeepSeek Harness、OpenCode。模型账号和 API 凭据由使用者配置。

## 当前实现状态

仓库包含镜像构建、CLI 版本锁定、KDE 配置、中文／繁体中文／日语输入法、欢迎窗口、LUKS2 持久化、Secure Boot 签名、QEMU 测试和 S3/GitHub 发布流水线。

**源代码和运行时测试通过不等于发行版已经验收。** 首次正式发布必须通过双架构镜像构建和最终镜像测试。未经过实机验证的 ARM 板型不标记为支持；完整验证状态记录在 [验证说明](docs/validation.md)。

本地已生成并验证 x86_64 候选镜像；构建过程的可替换文件下载统一使用 aria2（默认每文件 16 连接、8 文件并发）。正式发布仍需配置目标仓库、S3 存储和长期签名密钥。

## 使用方式

- 将 ISO 放入 Ventoy 数据分区任意目录；其他发行版 ISO 也可自由放置。Ventoy 路径无需启用 Secure Boot。
- 或将 ISO 原样烧录到 U 盘；其他 ISO 可放在任何可访问的存储设备中。
- KDE 使用普通 `live` 用户，运维终端和 CLI 通过入口进入 root 会话。SSH 服务默认不启动。
- 默认会话临时存储；欢迎窗口可创建或解锁外置 LUKS2 文件，保存 CLI 状态和 `/workspace`。
- 直接烧录的 UEFI 镜像提供手动导入证书的 Secure Boot 路径，详见 [签名说明](docs/secure-boot.md)。

这里的“安装其他发行版”是用户与 AI 配合使用该发行版的原生工具和 ISO 内容；不提供任意 ISO 通用安装器。

## 构建与发布

使用原生架构 Linux 和 Docker；Windows 开发机可通过 WSL2 运行。构建目录必须在 Linux 文件系统，建议至少 35 GiB 可用空间和 8 GiB 内存。

```bash
# 在装有 aria2、Python >= 3.11、Node.js >= 22.19、npm、Git、GnuPG 的 Linux 环境解析一次
python3 scripts/resolve.py --out work/lock

# 从同一个锁目录构建两种架构；在各自原生主机上执行
bash scripts/run-builder.sh x86_64 iso --arch x86_64 \
  --version 2026.11.03.local --lock /src/work/lock --work /build/image --out /out
```

ARM64 对应使用 `aarch64`。构建脚本保留输出所需的 Docker volume，便于签名；命令会输出 volume 名称。不要在 NTFS 上直接执行 pacstrap 或生成 rootfs。

每周一北京时间 08:17 运行 `Weekly Lynux images`；支持手动构建。手动运行默认仅生成带临时测试证书的候选镜像，不发布。配置 S3 和长期签名密钥后可启用正式发布。

- [本地构建与 CI 配置](docs/build.md)
- [加密持久化](docs/persistence.md)
- [Armbian 板级适配](docs/armbian.md)
- [测试与验收](docs/validation.md)

## 开发检查

```bash
bash tests/check.sh
ruff check runtime scripts tests
```

实际 LUKS2 测试在一次性特权容器中运行，仅使用测试创建的 loop 文件：

```bash
docker run --rm --privileged -e LYNUX_DISPOSABLE_TEST=1 \
  -v "$PWD:/src:ro" -w /src archlinux:base-devel bash -c \
  'bash scripts/setup-downloads.sh && pacman -S --noconfirm cryptsetup e2fsprogs util-linux && python tests/integration_state.py'
```

配置位于 `config/`，镜像覆盖文件在 `overlay/`，运行时在 `runtime/`。不要将 API Key、S3 凭据或签名私钥写进这些目录。
