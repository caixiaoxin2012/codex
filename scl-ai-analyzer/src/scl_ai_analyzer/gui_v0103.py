from __future__ import annotations

import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidget, QTableWidgetItem

from .gui_v0102 import MainWindow as BaseMainWindow
from .variable_xref import VariableCrossReferenceAnalyzer


class MainWindow(BaseMainWindow):
    def __init__(self) -> None:
        self._xref_cache = {}
        self._xref_analyzer = VariableCrossReferenceAnalyzer()
        self._current_xref_variable: str | None = None
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.10.3")

    def _build_detail_panel(self):
        panel = super()._build_detail_panel()
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            ["访问", "程序块", "类型", "文件", "行号", "关联工程对象", "源码"]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.cellDoubleClicked.connect(self._jump_from_xref)
        self.detail_tabs.addTab(table, "变量交叉引用")
        self.detail_tables["变量交叉引用"] = table
        return panel

    def on_analysis_finished(self, project: object, report: str) -> None:
        super().on_analysis_finished(project, report)
        if self.project:
            self._xref_cache = self._xref_analyzer.build(self.project)
            self.log("INFO", f"变量交叉引用索引完成：{len(self._xref_cache)} 个符号")

    def show_block(self, index: int) -> None:
        super().show_block(index)
        self._clear_xref()

    def _on_source_cursor_changed(self) -> None:
        super()._on_source_cursor_changed()
        if self.current_block_index is None or not self.project:
            return
        source = self.detail_views["源码"]
        cursor = source.textCursor()
        line_number = cursor.blockNumber() + 1
        position_in_line = cursor.positionInBlock()
        block = self.project.blocks[self.current_block_index]
        variable = self._variable_under_cursor(block.text, line_number, position_in_line)
        if variable is None:
            variables = self._xref_analyzer.variables_at(block, line_number)
            variable = variables[0] if variables else None
        if variable:
            self._populate_xref(variable)

    def _variable_under_cursor(
        self,
        text: str,
        line_number: int,
        position_in_line: int,
    ) -> str | None:
        lines = text.splitlines()
        if line_number < 1 or line_number > len(lines):
            return None
        line = lines[line_number - 1]
        pattern = re.compile(r'#?"?[A-Za-z_][\w\.]*"?')
        for match in pattern.finditer(line):
            if match.start() <= position_in_line <= match.end():
                token = match.group(0).strip().strip('"').lstrip("#")
                normalized = token.casefold()
                if normalized in self._xref_cache or "." in token or match.group(0).startswith("#"):
                    return token
        return None

    def _populate_xref(self, variable: str) -> None:
        if not self.project:
            return
        if not self._xref_cache:
            self._xref_cache = self._xref_analyzer.build(self.project)
        xref = self._xref_cache.get(variable.strip().strip('"').lstrip("#").casefold())
        if xref is None:
            self._clear_xref()
            return

        self._current_xref_variable = xref.variable
        table = self.detail_tables["变量交叉引用"]
        table.clearContents()
        table.setRowCount(len(xref.all_references))
        for row, ref in enumerate(xref.all_references):
            related = "; ".join(
                f"{kind}:{name}"
                for kind, name in zip(ref.related_kinds, ref.related_objects)
            )
            values = (
                ref.access,
                ref.block_name,
                ref.block_type,
                ref.source_file,
                str(ref.line_number),
                related or "-",
                ref.source_line,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        (ref.block_name, ref.source_file, ref.line_number),
                    )
                table.setItem(row, col, item)

        table.resizeColumnsToContents()
        tab_index = self.detail_tabs.indexOf(table)
        if tab_index >= 0:
            self.detail_tabs.setTabText(
                tab_index,
                f"变量交叉引用 · {xref.variable} ({len(xref.all_references)})",
            )
        self.statusBar().showMessage(
            f"{xref.variable}：声明 {len(xref.declarations)} / 读取 {len(xref.reads)} / 写入 {len(xref.writes)}"
        )

    def _clear_xref(self) -> None:
        table = self.detail_tables.get("变量交叉引用")
        if table is None:
            return
        table.clearContents()
        table.setRowCount(0)
        tab_index = self.detail_tabs.indexOf(table)
        if tab_index >= 0:
            self.detail_tabs.setTabText(tab_index, "变量交叉引用")
        self._current_xref_variable = None

    def _jump_from_xref(self, row: int, _column: int) -> None:
        table = self.detail_tables.get("变量交叉引用")
        if table is None or row < 0:
            return
        first = table.item(row, 0)
        if first is None:
            return
        target = first.data(Qt.ItemDataRole.UserRole)
        if not isinstance(target, tuple) or len(target) != 3 or not self.project:
            return
        block_name, source_file, line_number = target
        target_index = next(
            (
                index
                for index, block in enumerate(self.project.blocks)
                if block.name.casefold() == str(block_name).casefold()
                and block.source_file.name.casefold() == str(source_file).casefold()
            ),
            None,
        )
        if target_index is None:
            self.log("WARNING", f"交叉引用目标块未找到：{block_name}")
            return
        self.block_table.selectRow(target_index)
        self.show_block(target_index)
        self.jump_to_source_line(int(line_number))
        if self._current_xref_variable:
            self._populate_xref(self._current_xref_variable)
        self.log("INFO", f"交叉引用跳转：{block_name}:L{line_number}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
