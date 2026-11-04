from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

CONFIG = Path("/usr/share/lynux/harnesses.json")
RUN = Path("/run/lynux")


class LynuxError(Exception):
    pass


def run(*args, capture=False, input=None, check=True, **kwargs):
    result = subprocess.run([str(a) for a in args], check=False, text=True, input=input,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None, **kwargs)
    if check and result.returncode:
        # Do not include stdin (passwords) or arbitrary CLI output in error logs.
        raise LynuxError(f"{args[0]} failed (exit {result.returncode})")
    return result.stdout.strip() if capture and check else result


def root_required():
    if os.geteuid() != 0:
        raise LynuxError("此操作需要 root 权限，请使用 sudo 运行。")


def registry():
    return json.loads(CONFIG.read_text())["harnesses"]


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("x", encoding="utf-8") as stream:
        os.chmod(temp, 0o600)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


@contextlib.contextmanager
def session_lock(shared=False):
    import fcntl
    RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (RUN / "session.lock").open("a") as lock:
        try:
            fcntl.flock(lock, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LynuxError("CLI 或存储操作仍在运行；请先退出所有运维终端与 CLI。") from exc
        yield lock


def digest(path: Path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main_guard(fn):
    try:
        fn()
    except (LynuxError, OSError, ValueError, KeyError) as exc:
        print(f"Lynux: {exc}", file=sys.stderr)
        raise SystemExit(1)
