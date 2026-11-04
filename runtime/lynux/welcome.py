"""Lynux welcome window: a Kirigami front end that runs as the desktop user.

Privileged steps go through `sudo -n` to the lynux-* helpers. Passwords are written to the
helper's standard input and never appear in arguments, the environment or logs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from . import i18n
from .common import registry

QML = Path(__file__).with_name("qml")
ICON = Path("/usr/share/icons/hicolor/scalable/apps/lynux.svg")
VERSIONS = Path("/usr/share/lynux/harness-versions.json")
OS_RELEASE = Path("/etc/os-release")
GUIDE = Path("/usr/share/doc/lynux/guide.html")
PROJECT = "https://github.com/LianZiZhou/Lynux"
TOOL_ORDER = ("codex", "claude", "kimi", "dsh", "opencode")


def last_json(lines):
    """The helper's result is its last JSON line; anything a child tool printed before it is ignored."""
    for line in reversed(lines):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


class Backend(QObject):
    stringsChanged = Signal()
    statusChanged = Signal()
    onlineChanged = Signal()
    isosChanged = Signal()
    autostartChanged = Signal()
    busyChanged = Signal()
    # kind, result: {"ok": bool, "code": str, "message": str, ...}
    finished = Signal(str, "QVariantMap")
    # kind, stage, fraction in 0..1 or -1 when unknown
    progress = Signal(str, str, float)
    languageApplied = Signal(str, "QVariantMap")

    def __init__(self, check=False):
        super().__init__()
        self._check = check
        self._language = i18n.detect()
        self._strings = i18n.strings(self._language)
        self._status = {"active": None, "ventoy": [], "locations": [], "sessions": 0}
        self._online = True
        self._isos = []
        self._busy = set()
        self._processes = set()
        self._tools = self._load_tools()
        self._version = self._load_version()
        if not check:
            self._network = QTimer(self)
            self._network.timeout.connect(self.refreshNetwork)
            self._network.start(10000)

    # ---- data exposed to QML -------------------------------------------------------------------
    def _load_tools(self):
        try:
            versions = json.loads(VERSIONS.read_text())
        except (OSError, ValueError):
            versions = {}
        names = registry()
        return [{"id": tool, "name": names[tool]["name"], "version": versions.get(tool, {}).get("version", "")}
                for tool in TOOL_ORDER if tool in names]

    def _load_version(self):
        try:
            for line in OS_RELEASE.read_text().splitlines():
                if line.startswith("VERSION_ID="):
                    return line.split("=", 1)[1].strip('"')
        except OSError:
            pass
        return ""

    def _autostart_file(self):
        return config_home() / "autostart" / "lynux.desktop"

    @Property("QVariantMap", notify=stringsChanged)
    def s(self):
        return self._strings

    @Property(str, notify=stringsChanged)
    def language(self):
        return self._language

    @Property("QVariantList", constant=True)
    def languages(self):
        return [{"code": code, "name": name} for code, name, *_ in i18n.LANGUAGES]

    @Property("QVariantMap", notify=statusChanged)
    def status(self):
        return self._status

    @Property(bool, notify=onlineChanged)
    def online(self):
        return self._online

    @Property("QVariantList", notify=isosChanged)
    def isos(self):
        return self._isos

    @Property("QVariantList", constant=True)
    def tools(self):
        return self._tools

    @Property(str, constant=True)
    def version(self):
        return self._version

    @Property(str, constant=True)
    def project(self):
        return PROJECT

    @Property(bool, notify=autostartChanged)
    def autostart(self):
        try:
            text = self._autostart_file().read_text()
        except OSError:
            return False
        return not re.search(r"^Hidden\s*=\s*true\s*$", text, re.M | re.I)

    @Property(bool, notify=busyChanged)
    def busy(self):
        return bool(self._busy)

    # ---- process plumbing ----------------------------------------------------------------------
    def _spawn(self, program, args, stdin=None, on_line=None, on_done=None):
        process = QProcess(self)
        buffer = bytearray()
        lines = []

        def read():
            buffer.extend(bytes(process.readAllStandardOutput()))
            while b"\n" in buffer:
                index = buffer.index(b"\n")
                text = buffer[:index].decode(errors="replace").strip()
                del buffer[:index + 1]
                lines.append(text)
                if on_line:
                    on_line(text)

        def done(code, _status=None):
            if process not in self._processes:
                return
            read()
            if buffer.strip():
                lines.append(buffer.decode(errors="replace").strip())
            error = bytes(process.readAllStandardError()).decode(errors="replace").strip()
            self._processes.discard(process)
            process.deleteLater()
            if on_done:
                on_done(code, lines, error)

        def failed(problem):
            if problem == QProcess.ProcessError.FailedToStart:
                done(-1)

        process.readyReadStandardOutput.connect(read)
        process.finished.connect(done)
        process.errorOccurred.connect(failed)
        self._processes.add(process)
        process.start(program, args)
        if stdin is not None:
            process.write(stdin.encode())
            process.closeWriteChannel()
        return process

    def _helper(self, kind, args, stdin=None, on_success=None, track=True):
        """Run a `sudo -n lynux-…` command that prints JSON progress and a final JSON result."""
        if track:
            self._busy.add(kind)
            self.busyChanged.emit()

        def line(text):
            data = last_json([text])
            if data and "progress" in data:
                done, total = data.get("done"), data.get("total")
                fraction = done / total if done is not None and total else -1.0
                self.progress.emit(kind, data["progress"], fraction)

        def done(code, lines, error):
            result = last_json(lines) or {"ok": code == 0, "code": "error",
                                          "message": error or f"exit {code}"}
            if not result.get("ok") and not result.get("message"):
                result["message"] = error or f"exit {code}"
            if track:
                self._busy.discard(kind)
                self.busyChanged.emit()
            if result.get("ok") and on_success:
                on_success(result)
            self.finished.emit(kind, result)

        self._spawn("sudo", ["-n", *args], stdin=stdin, on_line=line, on_done=done)

    @staticmethod
    def _detached(program, args):
        QProcess.startDetached(program, args)

    # ---- status --------------------------------------------------------------------------------
    @Slot()
    def refresh(self):
        if self._check:
            return

        def done(code, lines, _error):
            data = last_json(lines)
            if code == 0 and data and data.get("ok"):
                data.pop("ok")
                self._status = data
                self.statusChanged.emit()
        self._spawn("sudo", ["-n", "lynux-state", "status", "--json"], on_done=done)
        self.refreshNetwork()

    @Slot()
    def refreshNetwork(self):
        if self._check:
            return

        def done(code, lines, _error):
            online = code == 0 and bool(lines) and lines[0].startswith("connected")
            if online != self._online:
                self._online = online
                self.onlineChanged.emit()
        self._spawn("nmcli", ["-t", "-f", "STATE", "general"], on_done=done)

    @Slot()
    def refreshIsos(self):
        if self._check:
            return

        def done(code, lines, _error):
            try:
                self._isos = json.loads("\n".join(lines)) if code == 0 else []
            except ValueError:
                self._isos = []
            self.isosChanged.emit()
        self._spawn("sudo", ["-n", "lynux-iso", "list"], on_done=done)

    # ---- encrypted storage ---------------------------------------------------------------------
    @Slot(str, int, str)
    def createContainer(self, path, size_gib, password):
        self._helper("create", ["lynux-state", "create", path, "--size-gib", str(size_gib), "--make-parent",
                                "--password-stdin", "--json"], stdin=password, on_success=lambda _: self.refresh())

    @Slot(str, str)
    def unlockContainer(self, path, password):
        self._helper("unlock", ["lynux-state", "unlock", path, "--password-stdin", "--json"], stdin=password,
                     on_success=lambda _: self.refresh())

    @Slot("QVariantList", bool)
    def lock(self, ids, force):
        args = ["lynux-state", "lock", "--json"]
        if ids:
            args += ["--end", *[str(item) for item in ids]]
        if force:
            args.append("--force")
        self._helper("lock", args, on_success=lambda _: self.refresh())

    @Slot()
    def mountVentoy(self):
        candidates = self._status.get("ventoy") or []
        if not candidates:
            return
        item = candidates[0]
        if item.get("mount") and not item.get("writable"):
            self._helper("ventoy", ["mount", "-o", "remount,rw", "--", item["mount"]],
                         on_success=lambda _: self.refresh())
        elif not item.get("mount"):
            def done(code, _lines, error):
                self.finished.emit("ventoy", {"ok": code == 0, "code": "error", "message": error})
                self.refresh()
            # Let the Plasma polkit agent ask if udisks wants confirmation for a non-removable device.
            self._spawn("udisksctl", ["mount", "-b", item["device"]], on_done=done)

    # ---- disk images ---------------------------------------------------------------------------
    @Slot(str, str)
    def inspectIso(self, path, expected):
        expected = expected.strip().lower()

        def done(code, lines, error):
            self._busy.discard("inspect")
            self.busyChanged.emit()
            try:
                data = json.loads("\n".join(lines)) if code == 0 else None
            except ValueError:
                data = None
            if not data:
                self.finished.emit("inspect", {"ok": False, "code": "error", "message": error or f"exit {code}"})
                return
            data["ok"] = True
            data["match"] = (data["sha256"] == expected) if expected else None
            self.finished.emit("inspect", data)
        self._busy.add("inspect")
        self.busyChanged.emit()
        self._spawn("sudo", ["-n", "lynux-iso", "inspect", path], on_done=done)

    @Slot(str)
    def mountIso(self, path):
        def done(code, lines, error):
            self.finished.emit("mount_iso", {"ok": code == 0, "code": "error", "message": error})
            self.refreshIsos()
        self._spawn("sudo", ["-n", "lynux-iso", "mount", path], on_done=done)

    @Slot(str)
    def unmountIso(self, ident):
        def done(code, _lines, error):
            self.finished.emit("unmount_iso", {"ok": code == 0, "code": "error", "message": error})
            self.refreshIsos()
        self._spawn("sudo", ["-n", "lynux-iso", "unmount", ident], on_done=done)

    # ---- language ------------------------------------------------------------------------------
    @Slot(str)
    def setLanguage(self, code):
        if code not in i18n.CODES or code == self._language:
            return
        self._language = code
        self._strings = i18n.strings(code)
        self.stringsChanged.emit()
        if self._check:
            return
        locale, language = i18n.settings(code)
        writes = [("Translations", "LANGUAGE", language), ("Formats", "LANG", locale)]
        for group, key, value in writes:
            self._spawn("kwriteconfig6", ["--file", "plasma-localerc", "--group", group, "--key", key, value])

        def done(code_, _lines, error):
            self.languageApplied.emit(code, {"ok": code_ == 0, "message": error})
        self._spawn("sudo", ["-n", "localectl", "set-locale", f"LANG={locale}"], on_done=done)

    @Slot(result=bool)
    def logout(self):
        from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
        shutdown = QDBusInterface("org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown", QDBusConnection.sessionBus())
        if shutdown.isValid():
            reply = shutdown.call("logout")
            if reply.type() != QDBusMessage.MessageType.ErrorMessage:
                return True
        return False

    # ---- launchers -----------------------------------------------------------------------------
    @Slot(str)
    def launchTool(self, tool):
        if tool != "shell" and tool not in {item["id"] for item in self._tools}:
            return
        self._detached("konsole", ["--separate", "--hold", "-e", "sudo", "lynux-harness", "run", tool])

    @Slot()
    def openNetwork(self):
        self._detached("systemsettings", ["kcm_networkmanagement"])

    @Slot()
    def openSystemSettings(self):
        self._detached("systemsettings", [])

    @Slot()
    def openInputSettings(self):
        self._detached("fcitx5-configtool", [])

    @Slot()
    def openPartitionManager(self):
        self._detached("partitionmanager", [])

    @Slot(str)
    def openFolder(self, path):
        self._detached("dolphin", ["--new-window", path or "/run/media"])

    @Slot()
    def openGuide(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(GUIDE)))

    @Slot(str)
    def openUrl(self, url):
        QDesktopServices.openUrl(QUrl(url))

    @Slot(str)
    def copyText(self, text):
        QGuiApplication.clipboard().setText(text)

    @Slot(bool)
    def setAutostart(self, enabled):
        path = self._autostart_file()
        try:
            lines = path.read_text().splitlines()
        except OSError:
            lines = ["[Desktop Entry]", "Type=Application", "Name=Lynux", "Exec=lynux-welcome", "OnlyShowIn=KDE;"]
        lines = [line for line in lines if not re.match(r"^Hidden\s*=", line, re.I)]
        if not enabled:
            lines.append("Hidden=true")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        self.autostartChanged.emit()

    @Slot(str, result=str)
    def fileName(self, path):
        return Path(path).name

    @Slot(str, result=str)
    def localPath(self, url):
        return QUrl(url).toLocalFile() or url


def mark_ready(window):
    """The boot test waits for this file: it proves the window painted on the real desktop."""
    def touch():
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if runtime:
            (Path(runtime) / "lynux-welcome-ready").touch(mode=0o600, exist_ok=True)
        window.frameSwapped.disconnect(touch)
    window.frameSwapped.connect(touch)


def load(backend, engine):
    from PySide6.QtQuickControls2 import QQuickStyle
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        QQuickStyle.setStyle("org.kde.desktop")
    engine.rootContext().setContextProperty("app", backend)
    engine.load(QUrl.fromLocalFile(str(QML / "Main.qml")))
    return engine.rootObjects()[0] if engine.rootObjects() else None


def check():
    """Build-time self test: load every page in every language and fail on any QML warning."""
    from PySide6.QtQml import QQmlApplicationEngine
    app = QApplication.instance() or QApplication([sys.argv[0]])
    problems = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda errors: problems.extend(error.toString() for error in errors))
    backend = Backend(check=True)
    root = load(backend, engine)
    if root is None:
        problems.append("Main.qml did not load")
    else:
        for code in i18n.CODES:
            backend.setLanguage(code)
            for page in ("home", "tools", "storage", "images", "system"):
                root.setProperty("currentPage", page)
                app.processEvents()
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def main():
    if "--check" in sys.argv[1:]:
        raise SystemExit(check())
    from PySide6.QtQml import QQmlApplicationEngine
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("lynux-welcome")
    app.setApplicationDisplayName("Lynux")
    app.setDesktopFileName("lynux")
    if ICON.is_file():
        app.setWindowIcon(QIcon(str(ICON)))
    engine = QQmlApplicationEngine()
    backend = Backend()
    root = load(backend, engine)
    if root is None:
        raise SystemExit("Lynux: the welcome window failed to load.")
    mark_ready(root)
    QTimer.singleShot(0, backend.refresh)
    raise SystemExit(app.exec())
