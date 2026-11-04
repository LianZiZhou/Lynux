from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import RUN, LynuxError, atomic_json, digest, root_required, run

# Records stay root-only under RUN; mount points are world-readable so the desktop user can browse them.
MOUNTS = Path("/run/lynux-iso")


def source_path(value):
    path = Path(value).resolve(strict=True)
    if not path.is_file():
        raise LynuxError("Pick an ISO file.", "not_file")
    return path


def mounted():
    folder = RUN / "iso"
    if not folder.is_dir():
        return []
    result = []
    for record in sorted(folder.glob("*.json")):
        data = json.loads(record.read_text())
        result.append({"id": record.stem, "source": data["source"], "mount": data["target"]})
    return result


def main():
    parser = argparse.ArgumentParser(description="Check and mount ISO files read-only")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("inspect", "mount"):
        item = sub.add_parser(name)
        item.add_argument("path", type=source_path)
        if name == "inspect":
            item.add_argument("--sha256", help="Expected SHA-256 (optional)")
    item = sub.add_parser("unmount")
    item.add_argument("id", help="The 16-character mount id printed by `mount`")
    sub.add_parser("list", help="Show ISOs mounted by Lynux")
    args = parser.parse_args()
    if args.action == "inspect":
        actual = digest(args.path)
        if args.sha256 and actual != args.sha256.strip().lower():
            raise LynuxError("SHA-256 doesn't match.", "mismatch")
        print(json.dumps({"path": str(args.path), "bytes": args.path.stat().st_size,
                          "sha256": actual}, ensure_ascii=False, indent=2))
        return
    root_required()
    if args.action == "list":
        print(json.dumps(mounted(), ensure_ascii=False, indent=2))
        return
    import fcntl
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (RUN / "iso.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "mount":
            import hashlib
            key = hashlib.sha256(str(args.path).encode()).hexdigest()[:16]
            target = MOUNTS / key
            record = RUN / "iso" / f"{key}.json"
            if record.exists():
                raise LynuxError("This ISO is already mounted.", "already_mounted")
            record.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            MOUNTS.mkdir(exist_ok=True, mode=0o755)
            target.mkdir(exist_ok=True, mode=0o755)
            run("mount", "-t", "iso9660,udf", "-o", "loop,ro,nodev,nosuid,noexec", args.path, target)
            try:
                atomic_json(record, {"source": str(args.path), "target": str(target)})
            except Exception:
                run("umount", target)
                raise
            print(json.dumps({"id": key, "mount": str(target)}, ensure_ascii=False))
        else:
            if len(args.id) != 16 or any(c not in "0123456789abcdef" for c in args.id):
                raise LynuxError("Invalid mount id.", "bad_id")
            record = RUN / "iso" / f"{args.id}.json"
            if not record.exists():
                raise LynuxError("Lynux has no record of that ISO mount.", "not_mounted")
            target = Path(json.loads(record.read_text())["target"])
            if target.parent not in (MOUNTS, RUN / "iso"):
                raise LynuxError("The ISO mount record is invalid.", "bad_record")
            run("umount", target)
            record.unlink()
            target.rmdir()
