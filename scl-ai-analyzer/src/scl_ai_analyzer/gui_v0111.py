from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QMessageBox

from .gui import AnalysisWorker as BaseAnalysisWorker
from .gui_v0110 import MainWindow as BaseMainWindow
from .project import ProjectAnalyzer, render_project_markdown
from .secure_tia_adapter import TIAExportAdapter


class SecureAnalysisWorker(BaseAnalysisWorker):
    def run(self) -> None:
        try:
            self.progress.emit(10, "正在识别项目类型…")
            if self.path.is_dir() and any(self.path.rglob("*.xml")):
                self.progress.emit(25, "检测到 TIA XML，正在执行安全预检…")
                tia = TIAExportAdapter().scan(self.path)
                for warning in tia.warnings:
                    self.progress.emit(60, f"XML安全提示：{warning}")
                project = tia.scl_project
            elif self.path.is_file() and self.path.suffix.lower() == ".xml":
                self.progress.emit(25, "检测到 TIA XML，正在执行安全预检…")
                tia = TIAExportAdapter().scan(self.path)
                for warning in tia.warnings:
                    self.progress.emit(60, f"XML安全提示：{warning}")
                project = tia.scl_project
            else:
                self.progress.emit(30, "正在扫描 SCL 项目…")
                project = ProjectAnalyzer().scan(self.path)

            self.progress.emit(75, "正在生成项目分析…")
            report = render_project_markdown(project)
            self.progress.emit(100, "分析完成")
            self.finished.emit(project, report)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(BaseMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.11.1 — Secure XML Input")

    def start_analysis(self) -> None:
        if not self.project_path:
            QMessageBox.information(self, "SCL AI Analyzer", "请先导入项目目录。")
            return
        if self._thread and self._thread.isRunning():
            return

        self.progress.setValue(0)
        self.log("INFO", "开始项目分析（XML 文件先执行安全检查）")
        self._thread = QThread(self)
        self._worker = SecureAnalysisWorker(Path(self.project_path))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.on_progress)
        self._worker.finished.connect(self.on_analysis_finished)
        self._worker.failed.connect(self.on_analysis_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    app.setApplicationDisplayName("SCL AI Analyzer")
    app.setApplicationVersion("0.11.1")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
