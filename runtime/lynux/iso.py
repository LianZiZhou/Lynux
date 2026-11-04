from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import RUN, LynuxError, atomic_json, digest, root_required, run


def source_path(value):
    path = Path(value).resolve(strict=True)
    if not path.is_file():
        raise LynuxError("请选择 ISO 文件。")
    return path


def main():
    parser = argparse.ArgumentParser(description="只读 ISO 检查与挂载")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("inspect", "mount"):
        item = sub.add_parser(name)
        item.add_argument("path", type=source_path)
        if name == "inspect":
            item.add_argument("--sha256", help="可选的预期 SHA-256")
    item = sub.add_parser("unmount")
    item.add_argument("id", help="mount 输出的 16 位挂载 ID")
    args = parser.parse_args()
    if args.action == "inspect":
        actual = digest(args.path)
        if args.sha256 and actual != args.sha256.lower():
            raise LynuxError("SHA-256 不匹配。")
        print(json.dumps({"path": str(args.path), "bytes": args.path.stat().st_size,
                          "sha256": actual}, ensure_ascii=False, indent=2))
        return
    root_required()
    import fcntl
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (RUN / "iso.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "mount":
            import hashlib
            key = hashlib.sha256(str(args.path).encode()).hexdigest()[:16]
            target = RUN / "iso" / key
            record = RUN / "iso" / f"{key}.json"
            if record.exists():
                raise LynuxError("此 ISO 已经挂载。")
            target.mkdir(parents=True, exist_ok=True)
            run("mount", "-t", "iso9660,udf", "-o", "loop,ro,nodev,nosuid,noexec", args.path, target)
            try:
                atomic_json(record, {"source": str(args.path), "target": str(target)})
            except Exception:
                run("umount", target)
                raise
            print(json.dumps({"id": key, "mount": str(target)}, ensure_ascii=False))
        else:
            if len(args.id) != 16 or any(c not in "0123456789abcdef" for c in args.id):
                raise LynuxError("无效挂载 ID。")
            record = RUN / "iso" / f"{args.id}.json"
            if not record.exists():
                raise LynuxError("没有对应的 Lynux ISO 挂载记录。")
            target = RUN / "iso" / args.id
            run("umount", target)
            record.unlink()
            target.rmdir()
