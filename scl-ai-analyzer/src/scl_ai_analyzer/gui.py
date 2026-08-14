from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .project import ProjectAnalyzer, ProjectResult, render_project_markdown
from .tia_adapter import TIAExportAdapter


class AnalysisWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object, str)
    failed = Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            self.progress.emit(10, "正在识别项目类型…")
            if self.path.is_dir() and any(self.path.rglob("*.xml")):
                self.progress.emit(30, "检测到 TIA 导出，正在解析…")
                tia = TIAExportAdapter().scan(self.path)
                project = tia.scl_project
            else:
                self.progress.emit(30, "正在扫描 SCL 项目…")
                project = ProjectAnalyzer().scan(self.path)

            self.progress.emit(70, "正在生成项目分析…")
            report = render_project_markdown(project)
            self.progress.emit(100, "分析完成")
            self.finished.emit(project, report)
        except Exception as exc:  # GUI boundary: surface parser/runtime errors to user.
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.10.0")
        self.resize(1500, 900)
        self.project_path: Path | None = None
        self.project: ProjectResult | None = None
        self.report_text = ""
        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None

        self._build_toolbar()
        self._build_ui()
        self.statusBar().showMessage("就绪")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        import_action = QAction("导入项目", self)
        import_action.triggered.connect(self.choose_project)
        toolbar.addAction(import_action)

        analyze_action = QAction("开始分析", self)
        analyze_action.triggered.connect(self.start_analysis)
        toolbar.addAction(analyze_action)

        export_action = QAction("导出报告", self)
        export_action.triggered.connect(self.export_report)
        toolbar.addAction(export_action)

        toolbar.addSeparator()
        self.path_label = QLabel("尚未导入项目")
        toolbar.addWidget(self.path_label)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self._build_project_tree_panel())
        main_splitter.addWidget(self._build_block_list_panel())
        main_splitter.addWidget(self._build_detail_panel())
        main_splitter.setSizes([280, 360, 860])

        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(main_splitter)
        vertical_splitter.addWidget(self._build_log_panel())
        vertical_splitter.setSizes([720, 180])

        layout.addWidget(vertical_splitter)
        self.setCentralWidget(central)

    def _build_project_tree_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("项目文件树"))
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["项目对象"])
        self.project_tree.itemClicked.connect(self.on_tree_item_clicked)
        layout.addWidget(self.project_tree)
        return panel

    def _build_block_list_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("FB / FC / OB / DB"))
        self.block_table = QTableWidget(0, 4)
        self.block_table.setHorizontalHeaderLabels(["类型", "名称", "变量", "调用"])
        self.block_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.block_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.block_table.cellClicked.connect(self.on_block_clicked)
        layout.addWidget(self.block_table)
        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("当前块分析结果"))

        self.detail_tabs = QTabWidget()
        self.detail_views: dict[str, QPlainTextEdit] = {}
        for title in (
            "概览",
            "变量",
            "调用关系",
            "状态机",
            "设备",
            "报警联锁",
            "标准块",
            "因果链",
            "源码",
        ):
            view = QPlainTextEdit()
            view.setReadOnly(True)
            if title == "源码":
                view.setFont(QFont("Consolas", 10))
            self.detail_tabs.addTab(view, title)
            self.detail_views[title] = view
        layout.addWidget(self.detail_tabs)
        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        top = QHBoxLayout()
        top.addWidget(QLabel("解析日志 / Warning / Error"))
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        top.addWidget(self.progress)
        layout.addLayout(top)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        layout.addWidget(self.log_view)
        return panel

    def choose_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 TIA/SCL 项目目录")
        if not path:
            return
        self.project_path = Path(path)
        self.path_label.setText(str(self.project_path))
        self.log("INFO", f"已导入项目：{self.project_path}")
        self.populate_file_tree(self.project_path)

    def start_analysis(self) -> None:
        if not self.project_path:
            QMessageBox.information(self, "SCL AI Analyzer", "请先导入项目目录。")
            return
        if self._thread and self._thread.isRunning():
            return

        self.progress.setValue(0)
        self.log("INFO", "开始项目分析")
        self._thread = QThread(self)
        self._worker = AnalysisWorker(self.project_path)
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

    def on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.statusBar().showMessage(message)
        self.log("INFO", message)

    def on_analysis_finished(self, project: object, report: str) -> None:
        self.project = project if isinstance(project, ProjectResult) else None
        self.report_text = report
        if self.project:
            self.populate_blocks(self.project)
            self.populate_project_object_tree(self.project)
            self.log("INFO", f"分析完成：识别 {len(self.project.blocks)} 个程序块")
        self.progress.setValue(100)
        self.statusBar().showMessage("分析完成")

    def on_analysis_failed(self, message: str) -> None:
        self.log("ERROR", message)
        self.progress.setValue(0)
        self.statusBar().showMessage("分析失败")
        QMessageBox.critical(self, "分析失败", message)

    def populate_file_tree(self, root: Path) -> None:
        self.project_tree.clear()
        root_item = QTreeWidgetItem([root.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(root))
        self.project_tree.addTopLevelItem(root_item)
        self._add_dir_children(root_item, root, depth=0, max_depth=3)
        root_item.setExpanded(True)

    def _add_dir_children(self, parent: QTreeWidgetItem, path: Path, *, depth: int, max_depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.casefold()))
        except OSError:
            return
        for child in children:
            if child.name.startswith("."):
                continue
            if child.is_file() and child.suffix.lower() not in {".scl", ".xml", ".udt", ".db", ".awl"}:
                continue
            item = QTreeWidgetItem([child.name])
            item.setData(0, Qt.ItemDataRole.UserRole, str(child))
            parent.addChild(item)
            if child.is_dir():
                self._add_dir_children(item, child, depth=depth + 1, max_depth=max_depth)

    def populate_project_object_tree(self, project: ProjectResult) -> None:
        root_name = project.root.name or str(project.root)
        self.project_tree.clear()
        root_item = QTreeWidgetItem([root_name])
        self.project_tree.addTopLevelItem(root_item)
        groups: dict[str, QTreeWidgetItem] = {}
        for kind in ("OB", "FB", "FC", "DB"):
            group = QTreeWidgetItem([kind])
            groups[kind] = group
            root_item.addChild(group)

        type_map = {
            "ORGANIZATION_BLOCK": "OB",
            "FUNCTION_BLOCK": "FB",
            "FUNCTION": "FC",
            "DATA_BLOCK": "DB",
        }
        for index, block in enumerate(project.blocks):
            kind = type_map.get(block.block_type, block.block_type)
            group = groups.get(kind)
            if not group:
                continue
            item = QTreeWidgetItem([block.name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("block", index))
            group.addChild(item)
        root_item.setExpanded(True)
        for group in groups.values():
            group.setExpanded(True)

    def populate_blocks(self, project: ProjectResult) -> None:
        self.block_table.setRowCount(len(project.blocks))
        type_map = {
            "ORGANIZATION_BLOCK": "OB",
            "FUNCTION_BLOCK": "FB",
            "FUNCTION": "FC",
            "DATA_BLOCK": "DB",
        }
        for row, block in enumerate(project.blocks):
            values = (
                type_map.get(block.block_type, block.block_type),
                block.name,
                str(len(block.analysis.variables)),
                str(len(block.analysis.calls)),
            )
            for col, value in enumerate(values):
                self.block_table.setItem(row, col, QTableWidgetItem(value))
        self.block_table.resizeColumnsToContents()

    def on_block_clicked(self, row: int, _column: int) -> None:
        if not self.project or row >= len(self.project.blocks):
            return
        self.show_block(row)

    def on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "block":
            self.show_block(int(data[1]))

    def show_block(self, index: int) -> None:
        if not self.project:
            return
        block = self.project.blocks[index]
        analysis = block.analysis
        self.detail_views["概览"].setPlainText(
            f"名称：{block.name}\n"
            f"类型：{block.block_type}\n"
            f"来源：{block.source_file}\n"
            f"变量：{len(analysis.variables)}\n"
            f"FB 实例：{len(analysis.instances)}\n"
            f"调用点：{len(analysis.calls)}"
        )
        self.detail_views["变量"].setPlainText(
            "\n".join(
                f"{v.section:<8} {v.name} : {v.data_type}"
                + (f" := {v.default}" if v.default else "")
                + (f" // {v.comment}" if v.comment else "")
                for v in analysis.variables
            ) or "未识别到变量"
        )
        self.detail_views["调用关系"].setPlainText(
            "\n".join(
                f"L{c.line_number}: {c.target} [{c.call_kind}]"
                + (f" -> {c.fb_type}" if c.fb_type else "")
                for c in analysis.calls
            ) or "未识别到调用关系"
        )
        self.detail_views["源码"].setPlainText(block.text)

        # V0.10.0 first shell: detailed semantic tabs are populated from the project report.
        for tab in ("状态机", "设备", "报警联锁", "标准块", "因果链"):
            self.detail_views[tab].setPlainText(
                "该模块的项目级分析结果已由核心解析器生成。\n"
                "下一小版本将把结果按当前功能块直接映射到本页，并支持点击跳转源码行。"
            )

    def export_report(self) -> None:
        if not self.report_text:
            QMessageBox.information(self, "SCL AI Analyzer", "请先完成项目分析。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出分析报告",
            "scl_project_report.md",
            "Markdown (*.md);;Text (*.txt)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.report_text, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self.log("INFO", f"报告已导出：{path}")

    def log(self, level: str, message: str) -> None:
        self.log_view.appendPlainText(f"[{level}] {message}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
