# 加密存储

[English](persistence.md) | **中文**

Live 系统默认写在临时层里，重启就没了。想留下东西，就在 U 盘或硬盘上建一个加密容器文件。它只存两样：各个 CLI 的登录和配置，以及 `/workspace`。系统更新、桌面设置和缓存都不保存。

## 创建和解锁

先在 Dolphin 里挂载要存放容器文件的盘。

Ventoy 盘（1.1.18 及以上）的数据分区会出现在 `/dev/mapper/VentoyPart`，点欢迎窗口里的 **挂载 Ventoy 数据分区** 就能挂上。找不到这个映射时，Lynux 不会按卷标去猜是哪块盘，也绝不会格式化任何东西。

通过 UKI 从 Ventoy 启动时，Lynux 会找到 ISO 所在的分区并以只读方式挂载。这时再点同一个按钮，会把它切换成可写，然后就能创建容器，不会重复挂载同一个设备。

```bash
sudo mkdir -p /run/media/live/Ventoy/Lynux
sudo lynux-state create /run/media/live/Ventoy/Lynux/state.luks --size-gib 8
sudo lynux-state status
sudo lynux-state lock
sudo lynux-state unlock /run/media/live/Ventoy/Lynux/state.luks
```

路径只是举例，以桌面实际挂载的位置为准。密码在提示时手动输入，不会作为命令参数或环境变量传进去。

这些命令在普通 Konsole 里加 sudo 执行，或者直接用欢迎窗口的按钮。操作前先关掉所有 AI CLI 和 root 运维终端，否则会被拒绝，免得正在用的会话的工作区被新挂载盖住。

## 细节

- 容器是 LUKS2 + Argon2id（256 MiB 内存，解锁约 2 秒），里面是 ext4。
- 空间是一次性分配好的，创建后盘上至少还会剩 512 MiB。
- FAT32 放不下 4 GiB 及以上的文件。欢迎窗口默认建 8 GiB，FAT32 盘请用命令行建小一点的。
- 第一次创建时，可以把当前的 CLI 状态和工作区导进去，前提是没有 CLI 在运行。
- 解锁时，如果要挂载的目录里已经有文件，会拒绝解锁，不会把它们盖住。先把文件挪走、清空目录，再解锁。
- 正常关机时会先停掉 CLI 会话，然后同步、卸载、关闭容器。

## 容器里有什么

- `format.json`：格式版本号。不认识的版本直接拒绝，不会自动迁移。
- `cli/x86_64/` 和 `cli/aarch64/`：CLI 的配置、登录和会话，两种架构分开存。
- `workspace/`：你的工作文件，两种架构共用。

Claude 用的是单独的 HOME `/root/.lynux/claude`。它会整体替换 `.claude.json`，没法只把这一个文件 bind mount 进去。其他工具的状态目录写在 `config/harnesses.json` 里。临时缓存放在 `/run/lynux/cache`。

## 注意

- 新版 CLI 可能会改自己的数据格式，旧版不一定读得回来。Lynux 不会帮你降级数据。换新的周更 ISO 之前，可以在锁定状态下把整个容器文件备份一份。
- 容器损坏、只读、空间满了、密码错了或布局不认识，都不会触发格式化或覆盖。创建到一半中断留下的文件也会原样保留，你检查之后自己决定怎么处理。
- 加密不等于备份。工作区只有在解锁时才能读到。
