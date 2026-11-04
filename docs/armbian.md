# Armbian 板级适配

通用 ARM64 ISO 面向具有兼容 UEFI 固件的机器。已有 Armbian 适配并不意味着仅替换 DTB 就能启动：还涉及内核配置、模块、固件、U-Boot／SPL、存储布局和启动参数。

复制 `config/boards/template.json` 到新文件，填写：

- Armbian 仓库的完整 40 位提交、板型 ID、内核分支及 `userpatches` 目录。
- 内核、DTB、U-Boot `.deb` 文件匹配模式；每个模式必须唯一匹配。
- 提取产物中的内核文件名与 DTB 相对路径，以及额外固件目录。
- 镜像容量、引导保留区域、启动分区容量。
- 每个引导写入的 `source` 和 `offset_bytes`；source 相对 `.deb` 解包根目录。
- 实际串口及必要的内核参数。

使用已构建的 ARM64 rootfs 作为用户空间输入，在原生 ARM64 Linux 上执行：

```bash
python build board --profile config/boards/my-board.json \
  --rootfs /build/image/archiso/aarch64/airootfs \
  --work /build/my-board --out /out
```

宿主需要 Armbian 构建依赖、Docker（若使用其容器构建）、`dpkg-deb`、parted、mkfs 工具、arch-chroot、rsync 和 xz。构建框架调用 Armbian 的 kernel/uboot 目标，只提取其包内容，不执行 Debian maintainer scripts。

首版适配器采用 MBR、FAT 启动分区和 ext4 存储分区，以及 U-Boot extlinux 启动方式。需要 GPT、厂商分区表、FIT 或不同启动协议的设备需要扩展适配器，不能仅修改名字。模板故意不提供通用 bootloader offset；未填写的模板会直接拒绝构建。

`verified` 默认为 false。必须记录板型、硬件修订、构建提交、启动日志、显示／输入／网络／存储测试结果后，才可将它标记为已验证。仓库目前没有声称已实机支持的板型。
