# 测试说明

[English](validation.md) | **中文**

## 自动检查

| 检查项 | 入口 | 通过标准 |
|---|---|---|
| 静态检查和单元测试 | `tests/check.sh`、ruff | 校验、依赖锁、路径和发布失败处理都符合预期 |
| 加密存储 | `tests/integration_state.py` | 在一次性 loop 文件上跑通 LUKS2、ext4 和 bind mount |
| 模型 API 调用 | `scripts/check-providers.sh` | 在隔离网络命名空间里，五个 CLI 都能从模拟的 Responses、Chat Completions、Messages 服务拿到预期文本 |
| BIOS/UEFI 光盘和 USB | `tests/qemu_boot.py` | 来宾报告启动成功，CLI 离线帮助能用，Plasma 和 Fcitx 在运行 |
| Secure Boot | `tests/image_matrix.py` | `SecureBoot=1`，错误签名被拒绝，损坏的根文件系统无法启动 |
| 欢迎窗口 | 构建镜像时运行 `lynux-welcome --check` | 每种语言下每一页都能加载，没有 QML 错误 |
| 欢迎窗口翻译 | `tests/test_welcome_strings.py` | QML 用到的每个文本在所有语言里都有，占位符一致 |
| Ventoy | `tests/ventoy_boot.py` | ISO 能从一次性 Ventoy 盘启动，并记录 Ventoy 版本 |
| 发布 | `scripts/publish.py` | 报告和最终 ISO 哈希对得上，两种架构都齐，公开下载校验通过 |

QEMU 通过 fw_cfg 条目 `opt/lynux-test` 和 SMBIOS 产品名 `Lynux CI boot verification` 打开来宾内的检查，不改最终 ISO 的启动参数，也不用重新签名。没开 `CONFIG_FW_CFG_SYSFS` 的 ARM 内核靠 SMBIOS 标记。

超时算失败。没有 `/dev/kvm` 时用 TCG 软件模拟，单次启动上限 x86_64 600 秒、ARM64 1200 秒。ARM 虚拟机给 4 个 vCPU，并给模拟环境下的 CLI 离线检查和桌面启动多留时间。一旦出现明确的内核、挂载或检查失败，测试马上结束。

WSL 默认用 TCG，因为有 `/dev/kvm` 不代表嵌套虚拟化真能用。确认 KVM 能用的话，设置 `LYNUX_QEMU_ACCEL=kvm`。

Arch ARM 仓库里的 EDK2 固件不支持 Secure Boot。CI 用固定的 EDK2 stable 提交编译了一个带 Secure Boot 的 ArmVirt 测试固件。它只给 QEMU 测试用，不作为物理 ARM 设备的固件发布。

## 首次发布或改桌面前的人工检查

自动化的进程检查替代不了下面这些：

1. 在 Konsole、Qt 编辑器和 Firefox 里实际打字：简体拼音、台湾注音、香港仓颉/速成/粤拼、日语。看候选框、上屏和切换是否正常。
2. 五个 CLI 各自初始化，并用真实账号登录。CI 只连模拟服务，输出里的费用是客户端按模拟 token 估出来的，不是真实花费。
3. 在欢迎窗口里走一遍：选 ISO、只读挂载、创建并解锁容器、改工作区文件、重启后确认还在。在 `/workspace` 里开着一个 AI 工具和一个 Dolphin 窗口时点锁定：两者都应该被列出来，结束它们后锁定能完成。
4. 在欢迎窗口切换语言并注销，确认 Plasma 和新开的 Konsole 都换成了那种语言。再切回英文。
5. 在一块一次性的目标盘上做一次 Arch 示例安装、chroot 进去、修复引导，记下用的是哪块盘。千万别在开发机的系统盘上做。
6. 两种架构的 UEFI 真机：没信任证书时拒绝启动、导入后能启动、改过的 UKI 被拒绝，显示、Wi-Fi 和输入设备都正常。
7. 突然断电、磁盘写满、拔掉 U 盘、跨周升级、从另一种架构打开共享工作区之后，能不能恢复。

每份报告要写清版本、ISO SHA-256、环境和具体操作步骤。仓库里目前还没有真机测试结果，所以 CI 通过不代表所有硬件都能用。

## 已有结果

开发环境：x86_64 的 Windows + WSL2，在隔离的 Arch 容器里构建，在 QEMU 里测试。

### 2026-11-04：本地 x86_64 测试构建

版本 `2026.11.03.local7`（按开始构建那天命名）。签名 ISO 为 `lynux-2026.11.03.local7-x86_64-signed.iso`，用的是临时测试证书。

通过的项目：

- 32 个单元测试、Python 静态检查、ShellCheck 和 actionlint。
- 真实的 LUKS2/ext4/loop/bind mount 测试，包括密码错误、重新解锁、拒绝格式化和临时明文清理。
- 五个 CLI 的离线帮助和版本检查，以及隔离网络里的模拟模型请求。没用真实账号。
- x86_64 BIOS 从光盘和模拟 USB 启动；UEFI Secure Boot 从光盘和模拟 USB 启动，来宾报告 `SecureBoot=1`。
- Ventoy 1.1.18 普通 UEFI 启动，ISO 放在多层目录里，目录名带空格和中文。
- 错误证书和改过的 UKI 被签名检查拒绝，改过的 rootfs 启动时被拒绝挂载。
- 输入法预设里的每个引擎 ID 在镜像里都有对应的安装文件；欢迎窗口在真实的来宾桌面上正常显示。

ISO SHA-256：`9251571949ca24d3857dd868e8441bd18bd0ed62b75bfcdadd35b760f8e1dd36`。每项测试的报告和截图在本地 `out/` 目录，都和最终 ISO、rootfs 的哈希绑定。

这一阶段还没做 ARM64 启动测试和正式发布，这两项后来在 CI 里完成了，见下文。

### 2026-11-04：GitHub runner 复测

版本 `2026.11.04.5.1`，用长期证书签名。x86_64 ISO SHA-256：`8eaf26e840253b4d2b3ac515bba69514c84356bc2e82125b28beee95826148da`。

- [直接启动复测](https://github.com/LianZiZhou/Lynux/actions/runs/41775115851)：BIOS 光盘/USB、UEFI Secure Boot 光盘/USB 和损坏 rootfs 检查都通过了。这次的 Ventoy 测试失败，所以整次运行算失败。
- 修好测试盘的写入方式后，[单独的 Ventoy 复测](https://github.com/LianZiZhou/Lynux/actions/runs/41783213425)通过。用的是 Ventoy 1.1.18，ISO 路径带空格和中文。EFI 分区和官方镜像逐字节一致，来宾返回 `LYNUX_BOOT_OK`。

两次用的是同一个 ISO，只改了测试工具和测试盘的制作方式，不算正式发布。

### 2026-11-04：首个双架构正式版

[完整流水线](https://github.com/LianZiZhou/Lynux/actions/runs/41804923096)通过，发布了 [2026.11.04.13.1](https://github.com/LianZiZhou/Lynux/releases/tag/v2026.11.04.13.1)。两种架构都通过了签名、来宾内 CLI 离线检查、模拟模型请求、光盘和 USB 的 UEFI Secure Boot 启动、防篡改测试，以及 Ventoy 普通 UEFI 启动。x86_64 另外通过了 BIOS 光盘和 USB 启动。

| 架构 | 正式版 ISO SHA-256 |
|---|---|
| x86_64 | `ceef499ffe920f48a62c36fc1919f836fdc3302f6440cd123cc83b092d837068` |
| aarch64 | `6944c35ae798b51cd26baa294edb2b132ea88697f655fe0d5bbd363d4f9ecbda` |

两个 ISO 都在 S3 上，并且通过公开 HTTPS 下载回来核对过哈希。[最新版本索引](https://lynux.lzz.moe/lynux/latest.json)已更新。这个版本用长期证书签名，指纹见 [docs/keys](keys/README.zh.md)。

GitHub 的 ARM runner 用 TCG 软件模拟，三个完整启动测试每个约 9 分钟，真机会快得多。

还没做的：真实 Armbian 板子测试、真实账号登录、每种输入法在每个目标应用里逐一试用，以及其他发行版的完整安装。以上都只是 QEMU 结果，替代不了上面的人工检查。
