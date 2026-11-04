"""Render the welcome window offscreen with sample data, one PNG per page and dialog.

Runs the real QML against a backend whose helper commands are stubbed out, so nothing
privileged happens. Needs PySide6, Kirigami, Kirigami Addons and qqc2-desktop-style:

    QT_QPA_PLATFORM=offscreen python tests/render_welcome.py --output out/welcome
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QEventLoop, QObject, QTimer  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from lynux import common, i18n, welcome  # noqa: E402

GIB = 1024 ** 3
CONTAINER = "/run/media/live/Ventoy/Lynux/state.luks"
LOCKED = {
    "active": None,
    "ventoy": [{"device": "/dev/mapper/VentoyPart", "mount": "/run/media/live/Ventoy", "writable": False}],
    "locations": [
        {"mount": "/run/media/live/Ventoy", "device": "/dev/mapper/VentoyPart", "fstype": "exfat", "label": "Ventoy",
         "writable": False, "ventoy": True, "free": 52 * GIB, "total": 115 * GIB, "fat": False,
         "containers": [{"path": CONTAINER, "size": 8 * GIB}]},
        {"mount": "/run/media/live/DATA", "device": "/dev/sdb1", "fstype": "vfat", "label": "DATA",
         "writable": True, "ventoy": False, "free": int(3.2 * GIB), "total": 32 * GIB, "fat": True, "containers": []},
    ],
    "sessions": 0,
}
WRITABLE = dict(LOCKED, ventoy=[dict(LOCKED["ventoy"][0], writable=True)],
                locations=[dict(LOCKED["locations"][0], writable=True), LOCKED["locations"][1]])
UNLOCKED = dict(WRITABLE, active={"container": CONTAINER, "used": int(2.3 * GIB), "total": int(7.8 * GIB),
                                "free": int(5.5 * GIB), "size": 8 * GIB, "bindings": []},
                ventoy=[{"device": "/dev/mapper/VentoyPart", "mount": "/run/media/live/Ventoy", "writable": True}])
HOLDERS = [
    {"id": "unit:lynux-harness-1.scope", "kind": "session", "tool": "claude", "title": "Claude Code",
     "unit": "lynux-harness-1.scope",
     "processes": [{"pid": 2101, "user": "root", "name": "claude", "command": "claude", "start": "1"},
                   {"pid": 2133, "user": "root", "name": "node", "command": "node mcp-server", "start": "1"}]},
    {"id": "pid:2456:9", "kind": "process", "tool": "", "title": "dolphin", "unit": "",
     "processes": [{"pid": 2456, "user": "live", "name": "dolphin", "command": "dolphin /workspace", "start": "9"}]},
]
VERSIONS = {"codex": "0.166.0", "claude": "2.1.317", "kimi": "2.4.1", "dsh": "0.2.1-rc.5", "opencode": "2.2.5"}


def settle(app, ms=400):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--languages", nargs="+", default=["en_US", "zh_CN"], choices=i18n.CODES)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    versions = Path(tempfile.mkdtemp()) / "harness-versions.json"
    versions.write_text(json.dumps({tool: {"version": value} for tool, value in VERSIONS.items()}))

    app = QApplication([sys.argv[0]])
    problems = []
    with patch.object(common, "CONFIG", ROOT / "config/harnesses.json"), \
         patch.object(welcome, "VERSIONS", versions), \
         patch.object(welcome.Backend, "_spawn", lambda *a, **k: None), \
         patch.object(welcome.Backend, "logout", lambda self: True):
        backend = welcome.Backend(check=True)
        backend._version = "2026.11.11.14.1"
        engine = QQmlApplicationEngine()
        engine.warnings.connect(lambda errors: problems.extend(error.toString() for error in errors))
        root = welcome.load(backend, engine)
        if root is None:
            raise SystemExit("Main.qml did not load:\n" + "\n".join(problems))
        root.setProperty("width", 1040)
        root.setProperty("height", 760)

        def shot(name):
            settle(app)
            path = args.output / f"{name}.png"
            if not root.grabWindow().save(str(path)):
                raise RuntimeError(f"Could not save {path}")
            print(path)

        def show(page, status=LOCKED):
            backend._status = status
            backend.statusChanged.emit()
            root.setProperty("currentPage", "home")
            root.setProperty("currentPage", page)
            settle(app, 200)
            found = [item for item in root.findChildren(QObject, f"currentPage-{page}")]
            if not found:
                raise RuntimeError(f"Page {page} is not loaded")
            return found[-1]

        def child(page, name):
            found = page.findChild(QObject, name)
            if found is None:
                raise RuntimeError(f"No {name} on page")
            return found

        for code in args.languages:
            backend.setLanguage(code)
            tag = code
            show("home")
            shot(f"{tag}-1-home")
            show("tools")
            shot(f"{tag}-2-tools")
            show("storage")
            shot(f"{tag}-3-storage-locked")
            page = show("storage", WRITABLE)
            dialog = child(page, "createDialog")
            dialog.open()
            settle(app)
            dialog.setProperty("running", True)
            backend.progress.emit("create", "allocate", 0.42)
            shot(f"{tag}-4-create-progress")
            dialog.setProperty("running", False)
            dialog.close()
            page = show("storage")
            dialog = child(page, "unlockDialog")
            dialog.setProperty("path", CONTAINER)
            dialog.open()
            settle(app)
            backend.finished.emit("unlock", {"ok": False, "code": "wrong_password", "message": "Wrong password."})
            shot(f"{tag}-5-unlock-error")
            dialog.close()
            page = show("storage", UNLOCKED)
            shot(f"{tag}-6-storage-unlocked")
            backend.finished.emit("lock", {"ok": False, "code": "busy", "holders": HOLDERS})
            shot(f"{tag}-7-lock-holders")
            child(page, "holdersDialog").close()
            page = show("images")
            page.setProperty("path", "/run/media/live/Ventoy/ISO/archlinux-2026.11.01-x86_64.iso")
            backend._isos = [{"id": "0123456789abcdef", "source": "/run/media/live/Ventoy/ISO/debian-13.2.0-amd64.iso",
                              "mount": "/run/lynux-iso/0123456789abcdef"}]
            backend.isosChanged.emit()
            backend.finished.emit("inspect", {"ok": True, "sha256": "ceef499ffe920f48a62c36fc1919f836fdc3302f6440cd123cc83b092d837068",
                                              "match": True})
            shot(f"{tag}-8-images")
            show("system")
            shot(f"{tag}-9-system")
        root.close()
    for problem in problems:
        print("QML:", problem, file=sys.stderr)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
