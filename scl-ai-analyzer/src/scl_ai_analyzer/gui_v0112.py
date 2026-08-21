from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui_v0111 import MainWindow as BaseMainWindow


class MainWindow(BaseMainWindow):
    """V0.11.2 desktop shell with export SHA-256 integrity support."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.11.2 — Export Integrity / SHA-256")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    app.setApplicationDisplayName("SCL AI Analyzer")
    app.setApplicationVersion("0.11.2")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
