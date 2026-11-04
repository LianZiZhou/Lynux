# 验证与发布边界

## 自动化层次

| 检查 | 入口 | 判定依据 |
|---|---|---|
| Python、shell 与单元测试 | `tests/check.sh`、ruff | 校验、锁、路径和发布失败语义 |
| 真实加密存储 | `tests/integration_state.py` | 一次性 loop 文件上的 LUKS2、ext4、bind mounts |
| 模型请求协议 | `scripts/check-providers.sh` | 隔离网络命名空间中的 Responses、Chat Completions、Messages 模拟服务；五套 CLI 都必须返回预期文本 |
| BIOS／UEFI 光驱与 USB | `tests/qemu_boot.py` | 来宾启动标记、CLI 离线帮助、Plasma/Fcitx 进程 |
| Secure Boot | `tests/image_matrix.py` | SecureBoot=1、签名负例、根文件系统损坏启动拒绝 |
| Ventoy | `tests/ventoy_boot.py` | 一次性 Ventoy 磁盘实际启动，记录 Ventoy 版本 |
| 发布 | `scripts/publish.py` | 报告绑定最终 ISO 摘要、双架构齐全、公开下载校验 |

QEMU 的 `opt/lynux-test` fw_cfg 标记启用来宾检查，不需要修改最终 ISO 的命令行或重新签名。超时算失败，不算启动成功。没有 `/dev/kvm` 时使用 TCG，可能需要提高超时。

WSL 默认使用 TCG，避免把设备节点存在误认为嵌套虚拟化已验证；已确认可用的环境可用 `LYNUX_QEMU_ACCEL=kvm` 显式覆盖。

ARM 的仓库版 EDK2 固件默认未声明 Secure Boot 支持；CI 用锁定的 EDK2 stable 提交编译启用 Secure Boot 的 ArmVirt 测试固件。该固件仅用于 QEMU 验证，不作为所有物理 ARM 设备的固件发布。

## 首次发行及桌面变更的人工验收

自动进程检查不能替代以下交互验收：

1. Konsole、Qt 编辑器、Firefox 内实际输入简体拼音、台湾注音、香港仓颉／速成／粤拼和日语，检查候选窗、文字提交及切换。
2. 五套 CLI 的交互初始化及真实账号登录；CI 使用模拟服务，不访问真实模型账号。输出中的成本字段是客户端按模拟 token 计算的估值，不是实际消费。
3. 欢迎窗口完成 ISO 选择、只读挂载、创建／解锁容器、工作区编辑和重启恢复。
4. 在一次性目标磁盘完成 Arch 示例安装、chroot 和引导修复，记录目标磁盘；不在开发机系统盘执行。
5. 两种架构的物理 UEFI 机器验证证书未信任拒绝、导入后启动、改动 UKI 拒绝，以及显示、Wi-Fi 和输入设备。
6. 异常断电、满盘、介质拔出、跨周升级和不同架构访问共享工作区的恢复表现。

报告应注明版本、ISO SHA-256、环境和实际步骤。源码仓库未附带这些实机验收结果，不能将自动化测试通过宣传为所有硬件都兼容。

## 本次开发环境

Windows + WSL2 x86_64；使用隔离 Arch 容器构建，在 QEMU 中验证。

### 2026-11-04 本地验收记录

候选版本：`2026.11.03.local7`（版本日期沿用开始构建的日期）。签名 ISO 为
`lynux-2026.11.03.local7-x86_64-signed.iso`，使用临时测试证书。

已执行并通过：

- 32 项单元测试、Python 静态检查、ShellCheck、GitHub Actions actionlint。
- 真实 LUKS2/ext4/loop/bind-mount 测试，包括错误密码、重新解锁、格式拒绝和临时明文清理。
- 五套 CLI 的离线帮助／版本检查，以及隔离网络中的模拟模型请求；没有使用真实模型账号。
- x86_64 BIOS 光驱／模拟 USB 启动；UEFI Secure Boot 光驱／模拟 USB 启动，来宾报告 SecureBoot=1。
- Ventoy 1.1.18 普通 UEFI 启动，ISO 放在包含空格和中文的多级目录中。
- 错误证书与修改后的 UKI 被签名检查拒绝；被改动的 rootfs 在启动时拒绝挂载。
- 输入法预配置所用的引擎 ID 均对应镜像内实际安装的配置文件；欢迎窗口在真实来宾桌面完成绘制。

ISO SHA-256：`9251571949ca24d3857dd868e8441bd18bd0ed62b75bfcdadd35b760f8e1dd36`。
逐项报告和截图保存在本地 `out/`；报告绑定最终 ISO/rootfs 摘要。

尚未完成：ARM64 ISO 的实际构建和启动验收、具体 Armbian 板型实机验证、真实账号登录、四类输入法在所有目标应用中的逐项实操，以及目标发行版完整安装验收。S3/GitHub 正式发布已配置，但尚未成功发布。ARM64 软件包清单已完成仓库可用性检查，但这不等于 ARM64 镜像已通过构建。

### 2026-11-04 GitHub runner 复验

候选版本 `2026.11.04.5.1` 使用长期正式证书，x86_64 ISO SHA-256 为
`8eaf26e840253b4d2b3ac515bba69514c84356bc2e82125b28beee95826148da`。

- [直接启动复验](https://github.com/LianZiZhou/Lynux/actions/runs/41775115851)中的 BIOS 光驱／USB、UEFI Secure Boot 光驱／USB，以及损坏根文件系统拒绝启动报告全部通过；该次运行的 Ventoy 项失败，整体运行未通过。
- 修正测试介质写入后，[Ventoy 单项复验](https://github.com/LianZiZhou/Lynux/actions/runs/41783213425)通过。使用 Ventoy 1.1.18、包含中文和空格的 ISO 路径；EFI 分区与官方原始镜像一致，来宾返回 `LYNUX_BOOT_OK`。

这两轮使用同一个 ISO，仅重验测试工具与介质制作过程；不等于双架构正式发布已完成。
