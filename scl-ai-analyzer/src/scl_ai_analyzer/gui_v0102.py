from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit, QTableWidget

from .gui import MainWindow as BaseMainWindow
from .source_reverse import ReverseSourceIndex


class MainWindow(BaseMainWindow):
    def __init__(self) -> None:
        self._reverse_index: dict[int, tuple] = {}
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.10.2")
        self.detail_views["源码"].cursorPositionChanged.connect(self._on_source_cursor_changed)

    def _build_detail_panel(self):
        panel = super()._build_detail_panel()
        reverse_view = QPlainTextEdit()
        reverse_view.setReadOnly(True)
        reverse_view.setPlaceholderText("点击源码中的任意一行，这里会显示变量、调用、报警、设备、状态机和因果链关联。")
        self.detail_tabs.addTab(reverse_view, "反向关联")
        self.detail_views["反向关联"] = reverse_view
        return panel

    def show_block(self, index: int) -> None:
        super().show_block(index)
        if not self.project:
            return
        block = self.project.blocks[index]
        self._reverse_index = ReverseSourceIndex().build(block)
        self._update_reverse_links(1)

    def _on_source_cursor_changed(self) -> None:
        if self.current_block_index is None or not self.project:
            return
        cursor = self.detail_views["源码"].textCursor()
        line_number = cursor.blockNumber() + 1
        self._update_reverse_links(line_number)

    def _update_reverse_links(self, line_number: int) -> None:
        view = self.detail_views.get("反向关联")
        if view is None or not self.project or self.current_block_index is None:
            return

        block = self.project.blocks[self.current_block_index]
        lines = block.text.splitlines()
        source_line = lines[line_number - 1].strip() if 1 <= line_number <= len(lines) else ""
        links = self._reverse_index.get(line_number, ())

        output = [
            f"当前块：{block.name}",
            f"源码位置：{block.source_file.name}:L{line_number}",
            f"源码：{source_line or '-'}",
            "",
            "关联工程对象：",
        ]
        if not links:
            output.append("- 当前行未找到可追踪工程对象")
        else:
            for link in links:
                output.append(f"- [{link.kind}] {link.name} — {link.detail}")

        view.setPlainText("\n".join(output))
        self._select_rows_for_line(line_number, links)
        self.statusBar().showMessage(f"源码 L{line_number}：反查到 {len(links)} 个关联对象")

    def _select_rows_for_line(self, line_number: int, links: tuple) -> None:
        kinds = {item.kind for item in links}
        table_kinds = {
            "调用关系": {"CALL"},
            "状态机": {"STATE", "STATE_MACHINE", "STATE_TRANSITION"},
            "设备": {"DEVICE"},
            "报警联锁": {"ALARM"},
            "标准块": {"STANDARD_BLOCK"},
            "因果链": {"CAUSAL_CHAIN", "CAUSAL_ACTION"},
        }
        for title, table in self.detail_tables.items():
            table.clearSelection()
            if not (kinds & table_kinds.get(title, set())):
                continue
            for row in range(table.rowCount()):
                first = table.item(row, 0)
                if first is None:
                    continue
                try:
                    row_line = int(first.text())
                except ValueError:
                    continue
                if row_line == line_number:
                    table.selectRow(row)

        # Automatically switch from source to the most relevant analysis tab only when
        # the reverse-association tab is already visible; otherwise keep the engineer's
        # source-reading context stable.
        if self.detail_tabs.currentWidget() is self.detail_views.get("反向关联"):
            priority = (
                ("报警联锁", "ALARM"),
                ("因果链", "CAUSAL_CHAIN"),
                ("状态机", "STATE_TRANSITION"),
                ("设备", "DEVICE"),
                ("标准块", "STANDARD_BLOCK"),
                ("调用关系", "CALL"),
            )
            for title, kind in priority:
                if kind in kinds:
                    table: QTableWidget = self.detail_tables[title]
                    self.detail_tabs.setCurrentWidget(table)
                    break


def main() -> int:
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
