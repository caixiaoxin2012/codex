from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .call_xref import BlockCallCrossReferenceAnalyzer
from .gui_v0103 import MainWindow as BaseMainWindow


class MainWindow(BaseMainWindow):
    def __init__(self) -> None:
        self._call_xref_analyzer = BlockCallCrossReferenceAnalyzer()
        self._call_xref_cache = {}
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.10.4")

    def _build_detail_panel(self):
        panel = super()._build_detail_panel()

        call_panel = QWidget()
        layout = QVBoxLayout(call_panel)
        self.call_path_label = QLabel("从 OB 到当前块的调用路径：尚未分析")
        self.call_path_label.setWordWrap(True)
        layout.addWidget(self.call_path_label)

        table = QTableWidget(0, 9)
        table.setHorizontalHeaderLabels(
            [
                "方向", "调用者/目标", "实例", "调用类型", "状态",
                "文件", "行号", "关联工程对象", "源码",
            ]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.cellDoubleClicked.connect(self._jump_from_call_xref)
        layout.addWidget(table)

        self.detail_tabs.addTab(call_panel, "调用块交叉引用")
        self.detail_tables["调用块交叉引用"] = table
        return panel

    def on_analysis_finished(self, project: object, report: str) -> None:
        super().on_analysis_finished(project, report)
        if self.project:
            self._call_xref_cache = self._call_xref_analyzer.build(self.project)
            self.log("INFO", f"调用块交叉引用索引完成：{len(self._call_xref_cache)} 个程序块")
            if self.current_block_index is not None:
                self._populate_call_xref(self.current_block_index)

    def show_block(self, index: int) -> None:
        super().show_block(index)
        if self.project:
            if not self._call_xref_cache:
                self._call_xref_cache = self._call_xref_analyzer.build(self.project)
            self._populate_call_xref(index)

    def _populate_call_xref(self, index: int) -> None:
        if not self.project or index < 0 or index >= len(self.project.blocks):
            return
        block = self.project.blocks[index]
        xref = self._call_xref_analyzer.lookup(
            self.project,
            block.name,
            cache=self._call_xref_cache,
        )
        table = self.detail_tables["调用块交叉引用"]
        table.clearContents()
        if xref is None:
            table.setRowCount(0)
            self.call_path_label.setText("从 OB 到当前块的调用路径：未找到")
            return

        if xref.root_paths:
            paths = [" → ".join(path) for path in xref.root_paths]
            self.call_path_label.setText(
                "从 OB 到当前块的调用路径：\n" + "\n".join(f"• {path}" for path in paths[:20])
                + (f"\n• … 另有 {len(paths) - 20} 条路径" if len(paths) > 20 else "")
            )
        elif block.block_type == "ORGANIZATION_BLOCK":
            self.call_path_label.setText(f"从 OB 到当前块的调用路径：{block.name}（根块）")
        else:
            self.call_path_label.setText("从 OB 到当前块的调用路径：未发现可解析路径")

        rows: list[tuple[str, object]] = []
        for ref in xref.incoming:
            rows.append(("IN", ref))
        for ref in xref.outgoing:
            rows.append(("OUT", ref))

        table.setRowCount(len(rows))
        for row, (direction, ref) in enumerate(rows):
            if direction == "IN":
                peer = ref.caller_block
                jump_block = ref.caller_block
                instance = ref.instance_name or "-"
            else:
                peer = ref.resolved_block or ref.target_name
                jump_block = ref.caller_block
                instance = ref.instance_name or "-"

            values = (
                direction,
                peer,
                instance,
                ref.call_kind + (" / resolved" if ref.resolved_block else " / unresolved"),
                ref.state or "-",
                ref.source_file,
                str(ref.line_number),
                "; ".join(ref.related_objects) or "-",
                ref.source_line,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        (jump_block, ref.source_file, ref.line_number),
                    )
                table.setItem(row, col, item)

        table.resizeColumnsToContents()
        tab_index = self.detail_tabs.indexOf(table.parentWidget())
        if tab_index >= 0:
            self.detail_tabs.setTabText(
                tab_index,
                f"调用块交叉引用 · {block.name} (IN {len(xref.incoming)} / OUT {len(xref.outgoing)})",
            )

    def _jump_from_call_xref(self, row: int, _column: int) -> None:
        table = self.detail_tables.get("调用块交叉引用")
        if table is None or row < 0 or not self.project:
            return
        item = table.item(row, 0)
        if item is None:
            return
        target = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(target, tuple) or len(target) != 3:
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
            self.log("WARNING", f"调用交叉引用目标块未找到：{block_name}")
            return
        self.block_table.selectRow(target_index)
        self.show_block(target_index)
        self.jump_to_source_line(int(line_number))
        self.log("INFO", f"调用交叉引用跳转：{block_name}:L{line_number}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
