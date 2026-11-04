"""Password-encrypted, allowlisted persistence; never formats a block device."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import uuid

from .common import RUN, LynuxError, atomic_json, registry, root_required, run, session_lock

MAPPER = "lynux-state"
MOUNT = RUN / "state"
RECORD = RUN / "state.json"
GIB = 1024 ** 3


def bindings(arch=None):
    arch = arch or platform.machine()
    if arch not in ("x86_64", "aarch64"):
        raise LynuxError(f"Unsupported architecture: {arch}")
    result = []
    for tool, spec in registry().items():
        for index, item in enumerate(spec["state"]):
            result.append((MOUNT / "cli" / arch / tool / str(index), Path(item["path"]), item["type"]))
    result.append((MOUNT / "workspace", Path("/workspace"), "directory"))
    return result


def mount_table():
    data = json.loads(run("findmnt", "--json", "--list", "-o", "SOURCE,TARGET,FSTYPE,OPTIONS,MAJ:MIN", capture=True))
    return data.get("filesystems", [])


def discover():
    """Prefer the mapper; use checksummed EFI boot metadata to identify the physical partition."""
    boot = ventoy_boot_info()
    devices = []
    mapped = Path("/dev/mapper/VentoyPart")
    if mapped.exists():
        devices.append(mapped)
    if boot:
        disks = json.loads(run("lsblk", "--json", "-o", "PATH,TYPE,KNAME", capture=True))["blockdevices"]
        for disk in disks:
            if disk["type"] != "disk":
                continue
            try:
                with open(disk["path"], "rb", buffering=0) as stream:
                    sector = stream.read(512)
                if sector[384:400].hex() != boot["disk_guid"]:
                    continue
                for child in disk.get("children", []):
                    partno = Path("/sys/class/block") / child["kname"] / "partition"
                    if child["type"] == "part" and int(partno.read_text()) == boot["partition"]:
                        devices.append(Path(child["path"]))
            except (OSError, ValueError):
                continue
    mounts = mount_table() if devices else []
    found = []
    for device in devices:
        identity = f"{os.major(device.stat().st_rdev)}:{os.minor(device.stat().st_rdev)}"
        found.extend({"device": str(device), "mount": m["target"],
                      "writable": "rw" in m["options"].split(","), "boot": boot}
                     for m in mounts if m.get("maj:min") == identity)
    return found or ([{"device": str(devices[0]), "mount": None, "writable": None, "boot": boot}] if devices else [])


def parse_ventoy_param(data):
    signature = bytes.fromhex("20207777772e76656e746f792e6e6574")
    if len(data) != 512 or data[:16] != signature or sum(data) % 256:
        return None
    partition = int.from_bytes(data[41:43], "little")
    if not partition:
        return None
    return {"disk_guid": data[17:33].hex(), "partition": partition,
            "iso_path": data[45:429].split(b"\0", 1)[0].decode("utf-8", errors="replace")}


def ventoy_boot_info():
    efi = Path("/sys/firmware/efi/efivars/VentoyOsParam-77772020-2e77-6576-6e74-6f792e6e6574")
    for source, skip in ((efi, 4), (Path("/ventoy/ventoy_os_param"), 0),
                         (Path("/run/ventoy/ventoy_os_param"), 0)):
        try:
            value = parse_ventoy_param(source.read_bytes()[skip:skip + 512])
            if value:
                return value
        except OSError:
            pass
    return None


def validate_container(path: Path, creating=False):
    if not path.is_absolute() or path.name in ("", ".", ".."):
        raise LynuxError("容器必须是绝对文件路径。")
    # Refuse symlink components, devices, and a container within its own mount.
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise LynuxError("容器路径不能包含符号链接。")
    if path.is_relative_to(MOUNT):
        raise LynuxError("不能将容器放在加密存储内部。")
    if path.exists():
        if creating:
            raise LynuxError("文件已存在；不会覆盖。")
        if not stat.S_ISREG(path.stat().st_mode):
            raise LynuxError("只接受普通容器文件，不接受块设备。")
    elif not creating:
        raise LynuxError("容器不存在。")


def check_capacity(path: Path, size: int):
    if size < 256 * 1024 ** 2:
        raise LynuxError("容器至少需要 256 MiB。")
    if not path.parent.is_dir():
        raise LynuxError("请先创建容器所在目录。")
    details = json.loads(run("findmnt", "--json", "--target", path.parent,
                             "-o", "FSTYPE,OPTIONS", capture=True))["filesystems"][0]
    if "rw" not in details["options"].split(","):
        raise LynuxError("存储分区为只读。")
    if details["fstype"] in ("iso9660", "squashfs", "tmpfs", "overlay"):
        raise LynuxError("请选择真实、可写的外置存储分区。")
    if details["fstype"] in ("vfat", "msdos") and size >= 4 * GIB:
        raise LynuxError("FAT32 单文件必须小于 4 GiB；请选择更小容量或其他分区。")
    if shutil.disk_usage(path.parent).free < size + 512 * 1024 ** 2:
        raise LynuxError("空间不足：创建后必须至少保留 512 MiB。")


def read_password(confirm=False):
    password = getpass.getpass("加密存储密码：")
    if not password:
        raise LynuxError("密码不能为空。")
    if confirm and password != getpass.getpass("再次输入密码："):
        raise LynuxError("两次密码不同。")
    return password


def crypt_open(path, password):
    run("cryptsetup", "open", "--type", "luks2", "--key-file", "-", path, MAPPER, input=password)


def ensure_inactive():
    if RECORD.exists() or Path(f"/dev/mapper/{MAPPER}").exists() or os.path.ismount(MOUNT):
        raise LynuxError("已有存储处于打开状态；请先执行 lynux-state lock。")


def ensure_safe_tree(path: Path, base: Path):
    """Never follow persisted symlinks while constructing privileged bind sources."""
    for component in (path, *path.parents):
        if component == base:
            break
        if component.is_symlink():
            raise LynuxError(f"存储路径包含符号链接：{component}")


def initialize():
    atomic_json(MOUNT / "format.json", {"schema": 1, "product": "Lynux"})
    # Both architectures are provisioned at creation; unlock never repairs an unknown layout.
    for arch in ("x86_64", "aarch64"):
        for source, _, kind in bindings(arch):
            source.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if kind == "directory":
                source.mkdir(exist_ok=True, mode=0o700)
            elif not source.exists():
                source.write_text("{}\n")
                source.chmod(0o600)


def mount_bindings(import_session=False):
    metadata = MOUNT / "format.json"
    ensure_safe_tree(metadata, MOUNT)
    if json.loads(metadata.read_text()) != {"schema": 1, "product": "Lynux"}:
        raise LynuxError("未知持久化格式；原文件保持不变。")
    mounted = []
    backups = []
    try:
        for source, target, kind in bindings():
            ensure_safe_tree(source, MOUNT)
            ensure_safe_tree(target, Path("/"))
            if not source.exists() or (kind == "directory") != source.is_dir():
                raise LynuxError(f"存储布局不完整：{source}")
            if os.path.ismount(target):
                raise LynuxError(f"目标已经挂载：{target}")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if kind == "directory":
                target.mkdir(exist_ok=True, mode=0o700)
                has_data = any(target.iterdir())
            else:
                if not target.exists():
                    target.write_text("{}\n")
                    target.chmod(0o600)
                has_data = target.read_text().strip() not in ("", "{}")
            if has_data:
                if not import_session:
                    raise LynuxError(f"临时会话已有数据：{target}；请先另存，避免解锁后隐藏这些数据。")
                if kind == "directory":
                    shutil.copytree(target, source, dirs_exist_ok=True, symlinks=True)
                else:
                    shutil.copy2(target, source)
                # Preserve rollback copies on the same filesystem until all binds are committed.
                # An individual file bind would prevent atomic replacement; current adapters use directories.
                backup = target.with_name(target.name + ".lynux-import-" + uuid.uuid4().hex)
                target.rename(backup)
                backups.append((target, backup))
                if kind == "directory":
                    target.mkdir(mode=0o700)
                else:
                    target.touch(mode=0o600)
            run("mount", "--bind", source, target)
            mounted.append(str(target))
        return mounted, backups
    except Exception:
        for target in reversed(mounted):
            run("umount", target)
        for target, backup in reversed(backups):
            target.rmdir() if target.is_dir() else target.unlink()
            backup.rename(target)
        raise


def activate(path, password, new=False):
    crypt_open(path, password)
    mounted = False
    try:
        if new:
            run("mkfs.ext4", "-q", "-m", "0", f"/dev/mapper/{MAPPER}")
        MOUNT.mkdir(parents=True, exist_ok=True, mode=0o700)
        run("mount", "-o", "nodev,nosuid", f"/dev/mapper/{MAPPER}", MOUNT)
        mounted = True
        if new:
            initialize()
        bound, backups = mount_bindings(import_session=new)
        try:
            atomic_json(RECORD, {"schema": 1, "container": str(path), "bindings": bound})
        except Exception:
            for target in reversed(bound):
                run("umount", target)
            for target, backup in reversed(backups):
                target.rmdir() if target.is_dir() else target.unlink()
                backup.rename(target)
            raise
    except Exception:
        if mounted:
            run("umount", MOUNT)
        run("cryptsetup", "close", MAPPER)
        raise
    # Only discard temporary plaintext after encrypted copies and the activation record are committed.
    for _, backup in backups:
        shutil.rmtree(backup) if backup.is_dir() else backup.unlink()


def create(path, size, password):
    validate_container(path, creating=True)
    ensure_inactive()
    check_capacity(path, size)
    # O_EXCL is essential: never truncate an existing user file, even after a race.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        # Allocate real blocks, including on exFAT; do not rely on sparse-file free space.
        with os.fdopen(fd, "wb") as stream:
            block = bytes(4 * 1024 ** 2)
            remaining = size
            while remaining:
                written = stream.write(block[:min(len(block), remaining)])
                remaining -= written
            stream.flush()
            os.fsync(stream.fileno())
        run("cryptsetup", "luksFormat", "--batch-mode", "--type", "luks2", "--pbkdf", "argon2id",
            "--pbkdf-memory", "262144", "--iter-time", "2000", "--key-file", "-", path, input=password)
        activate(path, password, new=True)
    except Exception:
        # Preserve partial artifacts for diagnosis, never mistake them for a valid container.
        raise LynuxError(f"创建失败，已保留文件供检查：{path}；不会自动删除或重建。") from None


def close():
    if not RECORD.exists():
        if Path(f"/dev/mapper/{MAPPER}").exists():
            raise LynuxError("发现未登记的加密映射；请手动检查，避免卸载未知数据。")
        return
    record = json.loads(RECORD.read_text())
    allowed = {str(target) for _, target, _ in bindings()}
    if not set(record["bindings"]).issubset(allowed):
        raise LynuxError("存储挂载记录无效。")
    run("sync")
    # Persist progress so a busy mount can be released and the command retried safely.
    while record["bindings"]:
        target = record["bindings"][-1]
        run("umount", target)
        record["bindings"].pop()
        atomic_json(RECORD, record)
    if os.path.ismount(MOUNT):
        run("umount", MOUNT)
    if Path(f"/dev/mapper/{MAPPER}").exists():
        run("cryptsetup", "close", MAPPER)
    RECORD.unlink()


def main():
    parser = argparse.ArgumentParser(description="Lynux 加密 CLI 状态与工作区")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("create", "unlock"):
        item = sub.add_parser(name)
        item.add_argument("path", type=Path)
        if name == "create":
            item.add_argument("--size-gib", type=float, default=8)
    sub.add_parser("status")
    item = sub.add_parser("lock")
    item.add_argument("--shutdown", action="store_true")
    args = parser.parse_args()
    root_required()
    if args.action == "status":
        print(json.dumps({"active": json.loads(RECORD.read_text()) if RECORD.exists() else None,
                          "ventoy": discover()}, ensure_ascii=False, indent=2))
        return
    if args.action == "lock" and args.shutdown:
        run("systemctl", "stop", "lynux-harness-*.scope", check=False)
    with session_lock():
        active = run("systemctl", "list-units", "--type=scope", "--state=active", "--no-legend", "--plain",
                     "lynux-harness-*.scope", capture=True)
        if active:
            raise LynuxError("仍有运维 scope 在运行（可能包含后台进程），请退出后再切换存储。")
        if args.action == "create":
            create(args.path, int(args.size_gib * GIB), read_password(confirm=True))
        elif args.action == "unlock":
            validate_container(args.path)
            ensure_inactive()
            activate(args.path, read_password())
        else:
            close()
