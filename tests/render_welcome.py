"""Offscreen UI smoke test. Does not execute privileged runtime commands."""
import argparse
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from lynux import common, welcome  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    if args.font:
        ident = QFontDatabase.addApplicationFont(str(args.font))
        families = QFontDatabase.applicationFontFamilies(ident)
        if not families:
            raise RuntimeError("Cannot load supplied preview font")
        app.setFont(QFont(families[0], 10))

    def capture(*_):
        app = QApplication.instance()
        app.processEvents()
        window = next(w for w in app.topLevelWidgets() if w.windowTitle().startswith("Lynux"))
        if not window.grab().save(str(args.output)):
            raise RuntimeError("Could not capture welcome window")
        window.close()
        return 0

    with patch.object(common, "CONFIG", ROOT / "config/harnesses.json"), \
         patch("PySide6.QtCore.QTimer.singleShot"), patch.object(QApplication, "exec", capture):
        welcome.main()


if __name__ == "__main__":
    main()
