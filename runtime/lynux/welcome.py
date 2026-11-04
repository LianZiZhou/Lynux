"""Unprivileged desktop frontend. Password entry stays in a root terminal."""
import json
import os
from pathlib import Path

from .common import registry


def main():
    from PySide6.QtCore import QEvent, QObject, QProcess, QTimer
    from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                                  QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget)

    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.setWindowTitle("Lynux · vibe your system")
    window.resize(900, 650)
    class Painted(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint:
                runtime = os.environ.get("XDG_RUNTIME_DIR")
                if runtime:
                    (Path(runtime) / "lynux-welcome-ready").touch(mode=0o600, exist_ok=True)
                watched.removeEventFilter(self)
            return False
    painted = Painted(window)
    window._ready_probe = painted
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(12)
    title = QLabel("<h1 style='font-size:36px'>Lynux</h1><p>选择工具，连接模型，开始运维。</p>")
    title.installEventFilter(painted)
    layout.addWidget(title)
    status = QLabel("默认临时会话。可先解锁加密存储，再启动 AI 工具。")
    status.setWordWrap(True)
    layout.addWidget(status)
    processes = []
    candidates = []

    def launch(program, args):
        QProcess.startDetached(program, args)

    def terminal(args):
        launch("konsole", ["--separate", "--hold", "-e", "sudo", *args])

    def button(text, fn, row=None):
        item = QPushButton(text)
        item.setMinimumHeight(38)
        item.clicked.connect(fn)
        (row or layout).addWidget(item)

    tools_row = QHBoxLayout()
    for tool, spec in registry().items():
        button(spec["name"], lambda _=False, t=tool: terminal(["lynux-harness", "run", t]), tools_row)
    layout.addLayout(tools_row)
    button("root 运维终端", lambda: terminal(["lynux-harness", "run", "shell"]))

    def refresh():
        process = QProcess(window)
        processes.append(process)

        def finished(code, _):
            if code == 0:
                try:
                    data = json.loads(bytes(process.readAllStandardOutput()))
                    candidates[:] = data["ventoy"]
                    if data["active"]:
                        status.setText("已解锁：" + data["active"]["container"] + "\n工作区：/workspace")
                    elif candidates:
                        status.setText("临时会话 · 检测到 Ventoy 数据分区，可创建或解锁加密存储。")
                    else:
                        status.setText("临时会话 · 可在其他已挂载存储中选择加密容器。")
                except (ValueError, KeyError):
                    status.setText("无法读取存储状态，请在终端运行 lynux-state status。")
            processes.remove(process)
            process.deleteLater()
        process.finished.connect(finished)
        process.start("sudo", ["lynux-state", "status"])

    def choose_container(create=False):
        base = next((c["mount"] for c in candidates if c["mount"]), "/run/media/live")
        default = str(Path(base) / "Lynux" / "state.luks")
        if create:
            path, _ = QFileDialog.getSaveFileName(window, "新建加密容器（默认 8 GiB；可在文件窗口创建目录）",
                                                 default, "LUKS container (*.luks)")
            if path and Path(path).exists():
                QMessageBox.warning(window, "文件已存在", "请选择新文件名；已有文件不会覆盖。")
                return
        else:
            path, _ = QFileDialog.getOpenFileName(window, "解锁加密容器", default,
                                                 "LUKS container (*.luks);;All files (*)")
        if path:
            terminal(["lynux-state", "create" if create else "unlock", path])

    storage = QHBoxLayout()
    button("创建加密存储", lambda: choose_container(True), storage)
    button("解锁", lambda: choose_container(False), storage)
    button("锁定", lambda: terminal(["lynux-state", "lock"]), storage)
    button("刷新状态", refresh, storage)
    layout.addLayout(storage)
    def mount_ventoy():
        if not candidates:
            QMessageBox.information(window, "未检测到 Ventoy", "请在 Dolphin 中选择并挂载存储分区。")
            return
        if candidates[0]["mount"]:
            if candidates[0]["writable"]:
                launch("dolphin", [candidates[0]["mount"]])
            else:
                terminal(["mount", "-o", "remount,rw", "--", candidates[0]["mount"]])
        else:
            launch("konsole", ["--hold", "-e", "udisksctl", "mount", "-b", candidates[0]["device"]])
    button("挂载 Ventoy 数据分区", mount_ventoy)

    def iso(action):
        path, _ = QFileDialog.getOpenFileName(window, "选择任意位置的 ISO", "/run/media", "ISO (*.iso);;All files (*)")
        if path:
            terminal(["lynux-iso", action, path])
    images = QHBoxLayout()
    button("检查 ISO / SHA-256", lambda: iso("inspect"), images)
    button("只读挂载 ISO", lambda: iso("mount"), images)
    layout.addLayout(images)
    utilities = QHBoxLayout()
    button("网络连接", lambda: launch("systemsettings", ["kcm_networkmanagement"]), utilities)
    button("文件与磁盘", lambda: launch("dolphin", ["/run/media"]), utilities)
    button("本地使用说明", lambda: launch("xdg-open", ["/usr/share/doc/lynux/guide.html"]), utilities)
    layout.addLayout(utilities)
    layout.addWidget(QLabel("模型账号由你配置。其他发行版的 ISO 无需复制到固定目录。"))
    layout.addStretch()
    window.setCentralWidget(panel)
    window.show()
    QTimer.singleShot(0, refresh)
    app.exec()
