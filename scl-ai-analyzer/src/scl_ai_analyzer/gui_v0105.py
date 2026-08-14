from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui_v0104 import MainWindow as BaseMainWindow


class MainWindow(BaseMainWindow):
    """V0.10.5 desktop shell prepared for standalone Windows EXE packaging."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.10.5")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    app.setApplicationDisplayName("SCL AI Analyzer")
    app.setApplicationVersion("0.10.5")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
