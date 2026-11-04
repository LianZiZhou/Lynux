# Armbian 板子

[English](armbian.md) | **中文**

通用 ARM64 ISO 只能在有正常 UEFI 固件的机器上启动。大多数开发板没有这个条件，光把 Armbian 的 DTB 拿过来也不够：内核配置、模块、固件、U-Boot/SPL、分区布局和启动参数都得对上。

所以针对具体板子，要用 Armbian 的板型配置单独做一个磁盘镜像。

## 添加板子

复制 `config/boards/template.json` 到新文件，填好：

- Armbian 仓库的提交（完整 40 位哈希）、板型 ID、内核分支和 `userpatches` 目录。
- 内核、DTB、U-Boot 的 `.deb` 文件匹配规则，每条规则必须正好匹配一个文件。
- 解包后的内核文件名、DTB 路径，以及需要额外带上的固件目录。
- 镜像大小、引导程序保留区和启动分区大小。
- 每个要写入的引导程序文件的 `source` 和 `offset_bytes`。`source` 是相对于 `.deb` 解包根目录的路径。
- 串口，以及板子需要的内核参数。

模板故意没写默认的引导偏移。没填完就构建，会直接报错退出。

## 构建

在原生 ARM64 Linux 上，用已经构建好的 ARM64 rootfs 执行：

```bash
python build board --profile config/boards/my-board.json \
  --rootfs /build/image/archiso/aarch64/airootfs \
  --work /build/my-board --out /out
```

宿主机需要 Armbian 的构建依赖（用它的容器构建的话还要 Docker），以及 `dpkg-deb`、parted、mkfs 工具、arch-chroot、rsync 和 xz。脚本调用 Armbian 的内核和 U-Boot 构建目标，只解包生成的软件包，不会执行 Debian 的 maintainer 脚本。

## 限制

目前只支持一种布局：MBR、FAT 启动分区、ext4 根分区、U-Boot extlinux 启动。需要 GPT、厂商分区表、FIT 镜像或其他启动方式的板子，得改适配器代码，光改配置文件是不行的。

## 标记为已验证

`verified` 默认是 false。记录下板型、硬件版本、构建提交、启动日志，以及显示、输入、网络、存储的测试结果之后，才能改成 true。目前还没有验证过的板子。
