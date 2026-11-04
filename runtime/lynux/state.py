"""Password-encrypted, allowlisted persistence; never formats a block device."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import sys
import time
import uuid

from .common import RUN, LynuxError, atomic_json, registry, root_required, run, session_lock

MAPPER = "lynux-state"
MOUNT = RUN / "state"
RECORD = RUN / "state.json"
PROC = Path("/proc")
GIB = 1024 ** 3
MIB = 1024 ** 2
SCOPE_PREFIX = "lynux-harness-"
# Filesystems that can never hold a container: virtual, read-only images or RAM.
UNSUITABLE = {"iso9660", "udf", "squashfs", "tmpfs", "ramfs", "overlay", "proc", "sysfs", "devtmpfs", "devpts",
              "cgroup2", "efivarfs", "securityfs", "debugfs", "tracefs", "configfs", "fusectl", "mqueue",
              "hugetlbfs", "bpf", "pstore", "autofs", "binfmt_misc", "nsfs"}
REMOVABLE_ROOTS = ("/run/media/", "/media/", "/mnt/")


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
    data = json.loads(run("findmnt", "--json", "--list", "-o", "SOURCE,TARGET,FSTYPE,OPTIONS,LABEL,MAJ:MIN",
                          capture=True))
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


def find_containers(mount):
    """Shallow look for containers in the usual places on one drive. Never follows symlinks."""
    found = []
    for folder in (Path(mount) / "Lynux", Path(mount)):
        try:
            if folder.is_symlink() or not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.luks")):
                if not path.is_symlink() and path.is_file():
                    found.append({"path": str(path), "size": path.stat().st_size})
        except OSError:
            continue
    return found


def locations(table=None, ventoy=()):
    """Mounted drives that could hold a container, with free space and any containers found."""
    ventoy_mounts = {item["mount"] for item in ventoy if item.get("mount")}
    result = []
    for entry in table if table is not None else mount_table():
        target = entry["target"]
        if entry.get("fstype") in UNSUITABLE or Path(target).is_relative_to(RUN):
            continue
        if target not in ventoy_mounts and not target.startswith(REMOVABLE_ROOTS):
            continue
        try:
            usage = shutil.disk_usage(target)
        except OSError:
            continue
        result.append({"mount": target, "device": entry.get("source"), "fstype": entry.get("fstype"),
                       "label": entry.get("label") or "", "writable": "rw" in entry.get("options", "").split(","),
                       "ventoy": target in ventoy_mounts, "free": usage.free, "total": usage.total,
                       "fat": entry.get("fstype") in ("vfat", "msdos"), "containers": find_containers(target)})
    return sorted(result, key=lambda item: (not item["ventoy"], item["mount"]))


def validate_container(path: Path, creating=False):
    if not path.is_absolute() or path.name in ("", ".", ".."):
        raise LynuxError("The container must be an absolute file path.", "bad_path")
    # Refuse symlink components, devices, and a container within its own mount.
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise LynuxError("The container path can't contain symlinks.", "symlink")
    if path.is_relative_to(MOUNT):
        raise LynuxError("The container can't live inside the encrypted storage itself.", "inside_storage")
    if path.exists():
        if creating:
            raise LynuxError("That file already exists. Lynux never overwrites files.", "exists", path=str(path))
        if not stat.S_ISREG(path.stat().st_mode):
            raise LynuxError("Only regular container files are accepted, not block devices.", "not_regular")
    elif not creating:
        raise LynuxError("The container file doesn't exist.", "not_found", path=str(path))


def check_capacity(path: Path, size: int, folder: Path | None = None):
    """`folder` is the existing directory to measure, when the container's own folder is still to be made."""
    folder = folder or path.parent
    if size < 256 * MIB:
        raise LynuxError("A container needs at least 256 MiB.", "too_small")
    if not folder.is_dir():
        raise LynuxError("The folder for the container doesn't exist.", "no_parent")
    details = json.loads(run("findmnt", "--json", "--target", folder,
                             "-o", "FSTYPE,OPTIONS", capture=True))["filesystems"][0]
    if "rw" not in details["options"].split(","):
        raise LynuxError("That drive is mounted read-only.", "read_only")
    if details["fstype"] in UNSUITABLE:
        raise LynuxError("Pick a real, writable external drive.", "unsuitable_fs")
    if details["fstype"] in ("vfat", "msdos") and size >= 4 * GIB:
        raise LynuxError("FAT32 can't hold files of 4 GiB or more. Pick a smaller size or another drive.",
                         "fat32_limit")
    if shutil.disk_usage(folder).free < size + 512 * MIB:
        raise LynuxError("Not enough space. At least 512 MiB must stay free after creating it.", "no_space")


def read_password(confirm=False):
    password = getpass.getpass("Storage password: ")
    if not password:
        raise LynuxError("The password can't be empty.", "empty_password")
    if confirm and password != getpass.getpass("Repeat the password: "):
        raise LynuxError("The passwords don't match.", "password_mismatch")
    return password


def read_password_stdin():
    """For the desktop app: the password arrives on a pipe, never in arguments or the environment."""
    password = sys.stdin.read()
    password = password[:-1] if password.endswith("\n") else password
    if not password:
        raise LynuxError("The password can't be empty.", "empty_password")
    return password


def crypt_open(path, password):
    result = run("cryptsetup", "open", "--type", "luks2", "--key-file", "-", path, MAPPER,
                 input=password, check=False, capture=True)
    if result.returncode == 2:
        raise LynuxError("Wrong password.", "wrong_password")
    if result.returncode:
        raise LynuxError(f"cryptsetup couldn't open the container (exit {result.returncode}).", "open_failed")


def ensure_inactive():
    if RECORD.exists() or Path(f"/dev/mapper/{MAPPER}").exists() or os.path.ismount(MOUNT):
        raise LynuxError("Encrypted storage is already open. Lock it first.", "already_open")


def ensure_safe_tree(path: Path, base: Path):
    """Never follow persisted symlinks while constructing privileged bind sources."""
    for component in (path, *path.parents):
        if component == base:
            break
        if component.is_symlink():
            raise LynuxError(f"The storage contains a symlink: {component}", "symlink")


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
        raise LynuxError("Unknown storage format. The file was left untouched.", "unknown_layout")
    mounted = []
    backups = []
    try:
        for source, target, kind in bindings():
            ensure_safe_tree(source, MOUNT)
            ensure_safe_tree(target, Path("/"))
            if not source.exists() or (kind == "directory") != source.is_dir():
                raise LynuxError(f"The storage layout is incomplete: {source}", "unknown_layout")
            if os.path.ismount(target):
                raise LynuxError(f"Already mounted: {target}", "already_open")
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
                    raise LynuxError(f"This session already has data in {target}. Move it somewhere else first, "
                                     "so unlocking doesn't hide it.", "session_has_data", path=str(target))
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


def activate(path, password, new=False, progress=lambda *_: None):
    progress("open")
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
        progress("bind")
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


def create(path, size, password, make_parent=False, progress=lambda *_: None):
    validate_container(path, creating=True)
    ensure_inactive()
    folder = path.parent
    if make_parent and not folder.exists():
        # Only one missing level, e.g. <drive>/Lynux; the drive itself must already be mounted.
        check_capacity(path, size, folder.parent)
        folder.mkdir(mode=0o755)
    check_capacity(path, size)
    # O_EXCL is essential: never truncate an existing user file, even after a race.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        # Allocate real blocks, including on exFAT; do not rely on sparse-file free space.
        with os.fdopen(fd, "wb") as stream:
            block = bytes(4 * MIB)
            remaining = size
            reported = 0
            while remaining:
                written = stream.write(block[:min(len(block), remaining)])
                remaining -= written
                if size - remaining - reported >= 64 * MIB or not remaining:
                    reported = size - remaining
                    progress("allocate", reported, size)
            stream.flush()
            os.fsync(stream.fileno())
        progress("format")
        run("cryptsetup", "luksFormat", "--batch-mode", "--type", "luks2", "--pbkdf", "argon2id",
            "--pbkdf-memory", "262144", "--iter-time", "2000", "--key-file", "-", path, input=password)
        activate(path, password, new=True, progress=progress)
    except Exception:
        # Preserve partial artifacts for diagnosis, never mistake them for a valid container.
        raise LynuxError(f"Creating the container failed. The file was kept for you to check: {path}. "
                         "Lynux won't delete or rebuild it.", "create_failed", path=str(path)) from None


def close():
    if not RECORD.exists():
        if Path(f"/dev/mapper/{MAPPER}").exists():
            raise LynuxError("Found an encrypted mapping Lynux didn't record. Check it by hand, so unknown "
                             "data isn't unmounted.", "unknown_mapping")
        return
    record = json.loads(RECORD.read_text())
    allowed = {str(target) for _, target, _ in bindings()}
    if not set(record["bindings"]).issubset(allowed):
        raise LynuxError("The storage mount record is invalid.", "bad_record")
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


def storage_roots():
    if not RECORD.exists():
        return []
    record = json.loads(RECORD.read_text())
    return [MOUNT, *(Path(target) for target in record["bindings"])]


def _process_paths(folder: Path):
    for name in ("cwd", "root", "exe"):
        try:
            yield os.readlink(folder / name)
        except OSError:
            pass
    try:
        for entry in os.scandir(folder / "fd"):
            try:
                yield os.readlink(entry.path)
            except OSError:
                pass
    except OSError:
        pass
    try:
        for line in (folder / "maps").read_text(errors="replace").splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) == 6:
                yield fields[5]
    except OSError:
        pass


def _uses(path, roots):
    if not path.startswith("/"):
        return False
    candidate = Path(path.removesuffix(" (deleted)"))
    return any(candidate == root or candidate.is_relative_to(root) for root in roots if root != Path("/"))


def _process(folder: Path):
    stat_line = (folder / "stat").read_text()
    start = stat_line.rsplit(")", 1)[1].split()[19]
    uid = next(int(line.split()[1]) for line in (folder / "status").read_text().splitlines()
               if line.startswith("Uid:"))
    import pwd  # Unix only; imported here so the module still loads in Windows unit tests.
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    command = (folder / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
    unit = ""
    for line in (folder / "cgroup").read_text().splitlines():
        leaf = line.rsplit("/", 1)[-1]
        if leaf.startswith(SCOPE_PREFIX) and leaf.endswith(".scope"):
            unit = leaf
    return {"pid": int(folder.name), "start": start, "user": user, "unit": unit,
            "name": (folder / "comm").read_text().strip(), "command": command[:300]}


def holders(roots=None):
    """What keeps the storage busy: open AI sessions, plus any process with files under the storage.

    Each group has an id that `end_holders` re-checks before signalling, so a reused PID is never hit.
    """
    roots = storage_roots() if roots is None else roots
    names = {tool: spec["name"] for tool, spec in registry().items()}
    sessions = {}
    others = []
    for folder in PROC.iterdir():
        if not folder.name.isdigit() or int(folder.name) == os.getpid():
            continue
        try:
            info = _process(folder)
            if info["unit"]:
                sessions.setdefault(info["unit"], []).append(info)
            elif roots and any(_uses(path, roots) for path in _process_paths(folder)):
                others.append(info)
        except (OSError, IndexError, StopIteration, ValueError):
            continue  # The process exited while being read.
    groups = []
    for unit, processes in sorted(sessions.items()):
        tool = "shell"
        for info in processes:
            words = info["command"].split()
            if "lynux-harness" in " ".join(words[:2]) and "run" in words:
                index = words.index("run")
                tool = words[index + 1] if index + 1 < len(words) else tool
                break
        groups.append({"id": f"unit:{unit}", "kind": "session", "tool": tool,
                       "title": names.get(tool, "Root terminal"), "unit": unit,
                       "processes": sorted(processes, key=lambda item: item["pid"])})
    for info in sorted(others, key=lambda item: item["pid"]):
        groups.append({"id": f"pid:{info['pid']}:{info['start']}", "kind": "process", "tool": "",
                       "title": info["name"], "unit": "", "processes": [info]})
    return groups


def end_holders(ids, force=False, wait=5.0):
    """Signal only groups that are still holders right now. Returns ids still running after `wait`."""
    wanted = set(ids)
    for group in holders():
        if group["id"] not in wanted:
            continue
        if group["kind"] == "session":
            run("systemctl", "kill", "--signal", "KILL" if force else "TERM", group["unit"], check=False)
        else:
            try:
                os.kill(group["processes"][0]["pid"], signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + wait
    while True:
        remaining = [group["id"] for group in holders() if group["id"] in wanted]
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(0.25)


def active_scopes():
    return run("systemctl", "list-units", "--type=scope", "--state=active", "--no-legend", "--plain",
               f"{SCOPE_PREFIX}*.scope", capture=True)


def status():
    active = None
    if RECORD.exists():
        active = json.loads(RECORD.read_text())
        container = Path(active["container"])
        try:
            active["size"] = container.stat().st_size
        except OSError:
            active["size"] = None
        usage = shutil.disk_usage(MOUNT)
        active.update({"used": usage.used, "total": usage.total, "free": usage.free})
    ventoy = discover()
    return {"active": active, "ventoy": ventoy, "locations": locations(ventoy=ventoy),
            "sessions": sum(1 for group in holders([]) if group["kind"] == "session")}


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def ensure_no_sessions():
    sessions = [group for group in holders([]) if group["kind"] == "session"]
    if sessions or active_scopes():
        raise LynuxError("An AI CLI or root terminal is still running. Close it first.", "busy", holders=sessions)


def dispatch(args):
    if args.action == "status":
        return status()
    if args.action == "holders":
        return {"holders": holders()}
    if args.action == "lock" and args.shutdown:
        run("systemctl", "stop", f"{SCOPE_PREFIX}*.scope", check=False)
        with session_lock():
            close()
        return {}
    if args.action == "lock":
        if args.end:
            remaining = end_holders(args.end, args.force)
            if remaining:
                raise LynuxError("Some programs are still running.", "still_running", remaining=remaining)
        busy = holders()
        if busy:
            raise LynuxError("Programs are still using the encrypted storage.", "busy", holders=busy)
    else:
        ensure_no_sessions()

    def progress(stage, done=None, total=None):
        if args.json:
            emit({"progress": stage, "done": done, "total": total})
        elif stage == "allocate":
            print(f"\rAllocating space: {done * 100 // total}%", end="" if done < total else "\n",
                  file=sys.stderr, flush=True)
        else:
            print({"format": "Encrypting…", "open": "Opening…", "bind": "Mounting…"}[stage], file=sys.stderr)

    with session_lock():
        if active_scopes():
            raise LynuxError("An AI CLI or root terminal is still running. Close it first.", "busy")
        if args.action == "create":
            password = read_password_stdin() if args.password_stdin else read_password(confirm=True)
            create(args.path, int(args.size_gib * GIB), password, args.make_parent, progress)
        elif args.action == "unlock":
            validate_container(args.path)
            ensure_inactive()
            activate(args.path, read_password_stdin() if args.password_stdin else read_password(),
                     progress=progress)
        else:
            close()
    return {}


def main():
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="Machine-readable output for the desktop app")
    parser = argparse.ArgumentParser(description="Lynux encrypted CLI state and workspace")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("create", "unlock"):
        item = sub.add_parser(name, parents=[shared])
        item.add_argument("path", type=Path)
        item.add_argument("--password-stdin", action="store_true", help="Read the password from standard input")
        if name == "create":
            item.add_argument("--size-gib", type=float, default=8)
            item.add_argument("--make-parent", action="store_true", help="Create the container's folder")
    sub.add_parser("status", parents=[shared])
    sub.add_parser("holders", parents=[shared], help="List programs keeping the storage busy")
    item = sub.add_parser("lock", parents=[shared])
    item.add_argument("--shutdown", action="store_true")
    item.add_argument("--end", nargs="+", default=[], metavar="ID", help="End these holders (ids from `holders`)")
    item.add_argument("--force", action="store_true", help="With --end, kill instead of asking to quit")
    args = parser.parse_args()
    try:
        root_required()
        result = dispatch(args)
    except (LynuxError, OSError, ValueError, KeyError) as exc:
        if not args.json:
            raise
        code = exc.code if isinstance(exc, LynuxError) else "error"
        details = exc.details if isinstance(exc, LynuxError) else {}
        emit({"ok": False, "code": code, "message": str(exc), **details})
        raise SystemExit(1) from None
    if args.json:
        emit({"ok": True, **result})
    elif args.action == "holders":
        for group in result["holders"]:
            for info in group["processes"]:
                print(f"{group['id']}\t{info['pid']}\t{info['user']}\t{info['command'] or info['name']}")
    elif args.action == "status":
        print(json.dumps(result, ensure_ascii=False, indent=2))
