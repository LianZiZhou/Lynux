# 加密持久化

系统默认运行在临时可写层。容器仅持久化显式登记的 CLI 状态和 `/workspace`，不保存系统升级、桌面设置或普通缓存。

## 建立与解锁

先在 Dolphin 中挂载外置分区。Ventoy 1.1.18+ 可通过 `/dev/mapper/VentoyPart` 访问数据分区，欢迎窗口提供挂载入口；找不到映射时不会按卷标猜测磁盘，也不会尝试格式化设备。

通过 UKI 启动时，Lynux 会使用 Ventoy 的 EFI 启动记录定位并只读挂载 ISO 所在分区。如果该分区已按只读方式挂载，点击工作台的“挂载 Ventoy 数据分区”会请求将同一挂载切换为可写，然后可创建加密容器；不会重复挂载底层设备。

```bash
sudo mkdir -p /run/media/live/Ventoy/Lynux
sudo lynux-state create /run/media/live/Ventoy/Lynux/state.luks --size-gib 8
sudo lynux-state status
sudo lynux-state lock
sudo lynux-state unlock /run/media/live/Ventoy/Lynux/state.luks
```

以上路径仅为示例，实际挂载路径由桌面环境决定。密码在终端中交互输入，不作为命令参数或环境变量传入。

这些存储命令从普通 Konsole 配合 sudo 执行，或使用欢迎窗口按钮。先关闭 AI CLI 和受管理的 root 运维终端，再切换存储；否则会被会话锁拒绝，以免把正在使用的工作区隐藏在另一个挂载下面。

使用 LUKS2、Argon2id（256 MiB 内存成本，约 2 秒校准）及内部 ext4。容器预分配实际空间，创建后保留至少 512 MiB 宿主剩余容量。FAT32 不接受 4 GiB 或更大的容器；欢迎窗口默认 8 GiB，需要较小容器时使用命令行。

首次创建可以导入当前尚未运行的 CLI 状态和工作区。解锁已有容器时如果临时目标目录已有数据，会拒绝隐藏这些文件；请先另存并清空冲突目录，再解锁。CLI 或运维 shell 正在运行时不能切换存储。正常关机停止相关 scope 后同步、卸载、关闭映射。

## 数据布局

- `format.json`：格式版本，不认识的版本拒绝自动迁移。
- `cli/x86_64/` 与 `cli/aarch64/`：架构独立的 CLI 配置、凭据和会话。
- `workspace/`：两种架构共享的工作文件。

Claude 使用独立 HOME `/root/.lynux/claude`，因为它会原子替换 `.claude.json`，不能将该文件单独 bind mount。其他工具的状态目录见 `config/harnesses.json`。临时缓存重定向到 `/run/lynux/cache`。

若升级后的 CLI 自行改变其数据格式，旧版本 CLI 未必还能读取它；Lynux 不会自动降级用户数据。替换周更 ISO 前，可在锁定状态下备份整个容器文件。

容器损坏、只读、空间不足、错误密码或未知布局不会触发自动格式化或覆盖。创建中断留下的文件也保留，检查确认后由用户自行处理。加密不等于备份；明文工作区只有在解锁期间可用。
