# Lynux

[English](README.md) | **中文**

**vibe your system.** Lynux 是一个基于 Arch Linux + KDE 的 Live 系统，用来配合 AI 编程助手修电脑、装系统、做日常运维。

镜像里预装了五个 CLI：Codex、Claude Code、Kimi Code、DeepSeek Harness 和 OpenCode。账号和 API Key 需要你自己配置。

提供这几种镜像：

- x86_64 ISO，BIOS 和 UEFI 都能启动
- ARM64 ISO，适用于带标准 UEFI 固件的机器
- 针对具体 Armbian 板子的镜像构建框架（目前还没有验证过的板子）

系统默认英文界面，时区为 UTC。Fcitx5 已经配好简体拼音、台湾注音、香港仓颉/速成/粤拼和日语输入法，开机就能用。

## 现状

第一个双架构版本 [v2026.11.04.13.1](https://github.com/LianZiZhou/Lynux/releases/tag/v2026.11.04.13.1) 已经在 QEMU 里跑通了完整 CI。还没有在真机上测过，也没有把任何 ARM 板子标为支持。哪些测过、哪些没测，见[测试说明](docs/validation.zh.md)。

## 怎么用

- 把 ISO 丢进 Ventoy 盘的任意目录，和其他发行版的 ISO 放一起就行。走 Ventoy 启动不需要开 Secure Boot。
- 也可以直接把 ISO 写进 U 盘，其他 ISO 放在任何能访问到的盘上。
- KDE 以普通用户 `live` 登录，运维终端和各个 CLI 会进入 root 会话。SSH 默认不开。
- 默认重启就清空。想保留数据，在欢迎窗口里建一个 LUKS2 加密文件，CLI 登录状态和 `/workspace` 会存进去。
- 直接写盘的 UEFI 镜像，导入我们的证书后可以开 Secure Boot 启动，见 [Secure Boot](docs/secure-boot.zh.md)。

“装其他发行版”的意思是你和 AI 一起用那个发行版自己的工具和 ISO 来装。Lynux 没有通用安装器。

## 构建

需要和目标架构一致的 Linux 加 Docker，Windows 上用 WSL2。构建目录要放在 Linux 文件系统里，不要放 NTFS。留至少 35 GiB 磁盘和 8 GiB 内存。

```bash
# 先生成一次依赖锁。需要 aria2、Python >= 3.11、Node.js >= 22.19、npm、Git、GnuPG。
python3 scripts/resolve.py --out work/lock

# 用这份锁构建。每种架构在对应的原生机器上跑。
bash scripts/run-builder.sh x86_64 iso --arch x86_64 \
  --version 2026.11.03.local --lock /src/work/lock --work /build/image --out /out
```

ARM64 把参数换成 `aarch64`。脚本会保留装着输出的 Docker volume 方便之后签名，并打印 volume 名称。

GitHub Actions 每周一 UTC 00:17（北京时间 08:17）跑 `Weekly Lynux images`，也可以手动触发。手动跑默认只出一个临时证书签名的测试镜像，不会发布。

其他文档：

- [构建与 CI 配置](docs/build.zh.md)
- [加密存储](docs/persistence.zh.md)
- [Armbian 板子](docs/armbian.zh.md)
- [测试说明](docs/validation.zh.md)

## 开发检查

```bash
bash tests/check.sh
ruff check runtime scripts tests
```

LUKS2 测试在一次性的特权容器里跑，只动它自己创建的 loop 文件：

```bash
docker run --rm --privileged -e LYNUX_DISPOSABLE_TEST=1 \
  -v "$PWD:/src:ro" -w /src archlinux:base-devel bash -c \
  'bash scripts/setup-downloads.sh && pacman -S --noconfirm cryptsetup e2fsprogs util-linux && python tests/integration_state.py'
```

目录：构建配置在 `config/`，拷进镜像的文件在 `overlay/`，欢迎窗口和辅助程序在 `runtime/`。API Key、S3 凭据和签名私钥都不要放进这些目录。
