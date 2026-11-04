from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import uuid

from .common import LynuxError, registry, root_required, session_lock


def binary(tool):
    return Path("/opt/lynux/harnesses") / tool / "bin" / tool


def main():
    parser = argparse.ArgumentParser(description="Lynux AI 运维入口")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    sub.add_parser("doctor")
    start = sub.add_parser("run")
    start.add_argument("tool", choices=[*registry(), "shell"])
    start.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    specs = registry()
    if args.action == "list":
        print(json.dumps({k: v["name"] for k, v in specs.items()}, ensure_ascii=False, indent=2))
        return
    root_required()
    if args.action == "doctor":
        failed = []
        for tool in specs:
            for flag in ("--version", "--help"):
                try:
                    result = subprocess.run([binary(tool), flag], capture_output=True, text=True, timeout=45)
                    if result.returncode:
                        failed.append(f"{tool} {flag}: exit {result.returncode}")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    failed.append(f"{tool}: {exc}")
        if failed:
            raise LynuxError("\n".join(failed))
        print("五套 CLI 离线启动检查通过。")
        return
    if not os.environ.get("LYNUX_HARNESS_SCOPE"):
        # Each launch is a tracked system scope, including manually launched CLI wrappers.
        command = ["systemd-run", "--scope", "--quiet", "--collect",
                   f"--unit=lynux-harness-{uuid.uuid4().hex}", "env", "LYNUX_HARNESS_SCOPE=1",
                   "/usr/local/bin/lynux-harness", "run", args.tool, *args.args]
        os.execvp(command[0], command)
    with session_lock(shared=True):
        env = dict(os.environ)
        env.update({"HOME": "/root", "USER": "root", "LOGNAME": "root", "HISTFILE": "/dev/null",
                    "DISABLE_AUTOUPDATER": "1", "DISABLE_UPDATES": "1", "XDG_CONFIG_HOME": "/root/.config",
                    "XDG_DATA_HOME": "/root/.local/share", "XDG_STATE_HOME": "/root/.local/state"})
        env.update(specs.get(args.tool, {}).get("env", {}))
        env["XDG_CACHE_HOME"] = f"/run/lynux/cache/{args.tool}"
        env["npm_config_cache"] = "/run/lynux/cache/npm"
        env["BROWSER"] = "/usr/local/bin/lynux-browser"
        Path(env["HOME"]).mkdir(parents=True, exist_ok=True, mode=0o700)
        Path(env["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True, mode=0o700)
        Path("/workspace").mkdir(exist_ok=True)
        argv = args.args[1:] if args.args[:1] == ["--"] else args.args
        if not argv:
            argv = specs.get(args.tool, {}).get("default_args", [])
        cmd = ["/bin/bash", "--login"] if args.tool == "shell" else [str(binary(args.tool)), *argv]
        # Parent retains the lock while CLI runs. SIGTERM reaches every process through the scope.
        child = subprocess.Popen(cmd, cwd="/workspace", env=env, restore_signals=True)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, lambda *_: child.terminate())
        raise SystemExit(child.wait())
