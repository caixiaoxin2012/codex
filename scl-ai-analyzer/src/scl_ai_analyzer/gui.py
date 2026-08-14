from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QAction, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
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

from .alarm_logic import AlarmLogicAnalyzer
from .causal_chain import CausalChainAnalyzer
from .device_logic import DeviceLogicAnalyzer
from .project import ProjectAnalyzer, ProjectResult, SourceBlock, render_project_markdown
from .standard_library import StandardLibraryAnalyzer
from .state_machine import StateMachineAnalyzer
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
        self.setWindowTitle("SCL AI Analyzer V0.10.1")
        self.resize(1500, 900)
        self.project_path: Path | None = None
        self.project: ProjectResult | None = None
        self.report_text = ""
        self.current_block_index: int | None = None
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
        layout.addWidget(QLabel("当前块分析结果（双击分析条目跳转源码）"))

        self.detail_tabs = QTabWidget()
        self.detail_views: dict[str, QPlainTextEdit] = {}
        self.detail_tables: dict[str, QTableWidget] = {}

        for title in ("概览", "变量"):
            view = QPlainTextEdit()
            view.setReadOnly(True)
            self.detail_tabs.addTab(view, title)
            self.detail_views[title] = view

        self._add_result_table("调用关系", ["行号", "目标", "类型", "FB 类型"])
        self._add_result_table("状态机", ["行号", "状态变量", "当前状态", "下一状态", "条件"])
        self._add_result_table("设备", ["行号", "实例/对象", "设备类型", "FB 类型", "置信度", "依据"])
        self._add_result_table("报警联锁", ["行号", "等级", "类别", "信号", "条件/表达式"])
        self._add_result_table("标准块", ["行号", "标准块", "家族", "功能", "接口角色"])
        self._add_result_table("因果链", ["行号", "当前状态", "动作", "设备", "标准块", "完成条件", "下一状态", "报警/联锁"])

        source_view = QPlainTextEdit()
        source_view.setReadOnly(True)
        source_view.setFont(QFont("Consolas", 10))
        self.detail_tabs.addTab(source_view, "源码")
        self.detail_views["源码"] = source_view

        layout.addWidget(self.detail_tabs)
        return panel

    def _add_result_table(self, title: str, headers: list[str]) -> None:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.cellDoubleClicked.connect(lambda row, _col, name=title: self._jump_from_table(name, row))
        self.detail_tabs.addTab(table, title)
        self.detail_tables[title] = table

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
            if self.project.blocks:
                self.block_table.selectRow(0)
                self.show_block(0)
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
            index = int(data[1])
            self.block_table.selectRow(index)
            self.show_block(index)

    def show_block(self, index: int) -> None:
        if not self.project:
            return
        self.current_block_index = index
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
        self.detail_views["源码"].setPlainText(block.text)

        self._populate_calls(block)
        self._populate_states(block)
        self._populate_devices(block)
        self._populate_alarms(block)
        self._populate_standard_blocks(block)
        self._populate_causal_chains(block)
        self.statusBar().showMessage(f"当前块：{block.name}")

    def _populate_calls(self, block: SourceBlock) -> None:
        rows = [
            (call.line_number, call.target, call.call_kind, call.fb_type or "-")
            for call in block.analysis.calls
        ]
        self._fill_table("调用关系", rows)

    def _populate_states(self, block: SourceBlock) -> None:
        rows: list[tuple[object, ...]] = []
        for machine in StateMachineAnalyzer().analyze(block.text):
            if machine.transitions:
                for transition in machine.transitions:
                    rows.append((
                        transition.line_number,
                        machine.selector,
                        transition.source,
                        transition.target,
                        transition.condition or "无条件",
                    ))
            else:
                rows.append((machine.start_line, machine.selector, "-", "-", "未识别到跳转"))
        self._fill_table("状态机", rows)

    def _populate_devices(self, block: SourceBlock) -> None:
        rows: list[tuple[object, ...]] = []
        for device in DeviceLogicAnalyzer().analyze_block(block):
            line = next((item.line_number for item in device.evidence if item.line_number), 1)
            evidence = "; ".join(
                f"{item.kind}:{item.value}" + (f"@L{item.line_number}" if item.line_number else "")
                for item in device.evidence
            )
            rows.append((
                line,
                device.instance_name or device.block_name,
                device.device_type,
                device.fb_type or "-",
                device.confidence,
                evidence,
            ))
        self._fill_table("设备", rows)

    def _populate_alarms(self, block: SourceBlock) -> None:
        rows = [
            (item.line_number, item.severity, item.category, item.symbol, item.expression)
            for item in AlarmLogicAnalyzer().analyze(block.text)
        ]
        self._fill_table("报警联锁", rows)

    def _populate_standard_blocks(self, block: SourceBlock) -> None:
        rows = [
            (
                item.line_number,
                item.canonical_name,
                item.family,
                item.purpose,
                ", ".join(item.interface_roles) or "-",
            )
            for item in StandardLibraryAnalyzer().analyze_block(block)
        ]
        self._fill_table("标准块", rows)

    def _populate_causal_chains(self, block: SourceBlock) -> None:
        rows: list[tuple[object, ...]] = []
        for chain in CausalChainAnalyzer().analyze_block(block):
            actions = "; ".join(f"{item.action_kind}:{item.target}" for item in chain.actions) or "-"
            devices = ", ".join(chain.device_names) or "-"
            standards = ", ".join(chain.standard_blocks) or "-"
            alarms = "; ".join(f"{item.category}:{item.symbol}" for item in chain.alarms) or "-"
            rows.append((
                chain.transition_line,
                chain.source_state,
                actions,
                devices,
                standards,
                chain.completion_condition or "无条件",
                chain.target_state,
                alarms,
            ))
        self._fill_table("因果链", rows)

    def _fill_table(self, title: str, rows: list[tuple[object, ...]]) -> None:
        table = self.detail_tables[title]
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index == 0:
                    try:
                        item.setData(Qt.ItemDataRole.UserRole, int(value))
                    except (TypeError, ValueError):
                        pass
                table.setItem(row_index, col_index, item)
        table.resizeColumnsToContents()

    def _jump_from_table(self, title: str, row: int) -> None:
        table = self.detail_tables.get(title)
        if not table or row < 0:
            return
        item = table.item(row, 0)
        if item is None:
            return
        line = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(line, int):
            try:
                line = int(item.text())
            except ValueError:
                return
        self.jump_to_source_line(line)

    def jump_to_source_line(self, line_number: int) -> None:
        source = self.detail_views["源码"]
        line_number = max(1, line_number)
        cursor = source.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        if line_number > 1:
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.MoveAnchor,
                line_number - 1,
            )
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        source.setTextCursor(cursor)
        source.centerCursor()
        self.detail_tabs.setCurrentWidget(source)
        self.statusBar().showMessage(f"已定位到源码第 {line_number} 行")
        self.log("INFO", f"源码定位：L{line_number}")

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
