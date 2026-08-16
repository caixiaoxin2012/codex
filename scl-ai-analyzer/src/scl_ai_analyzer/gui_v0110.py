from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .ai_review import (
    AIReviewUnavailable,
    OpenAIChineseReviewGenerator,
    render_rule_based_chinese_summary,
)
from .gui_v0105 import MainWindow as BaseMainWindow
from .tag_checker import TagCheckReport, TagChecker, render_tag_check_markdown


class AIReviewWorker(QObject):
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(self, report: TagCheckReport) -> None:
        super().__init__()
        self.report = report

    def run(self) -> None:
        try:
            result = OpenAIChineseReviewGenerator().generate(self.report)
            self.finished.emit(result.text, result.provider, result.model)
        except AIReviewUnavailable as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"AI Code Review 失败：{exc}")


class MainWindow(BaseMainWindow):
    def __init__(self) -> None:
        self._tag_checker = TagChecker()
        self._tag_report: TagCheckReport | None = None
        self._base_report_text = ""
        self._ai_thread: QThread | None = None
        self._ai_worker: AIReviewWorker | None = None
        super().__init__()
        self.setWindowTitle("SCL AI Analyzer V0.11.0 — PLC Code Review")

    def _build_detail_panel(self):
        panel = super()._build_detail_panel()

        review_panel = QWidget()
        layout = QVBoxLayout(review_panel)

        header = QHBoxLayout()
        self.review_summary_label = QLabel("PLC Code Review：等待项目分析")
        self.review_summary_label.setWordWrap(True)
        header.addWidget(self.review_summary_label, 1)
        self.ai_review_button = QPushButton("生成 AI 中文说明")
        self.ai_review_button.clicked.connect(self.generate_ai_review)
        self.ai_review_button.setEnabled(False)
        header.addWidget(self.ai_review_button)
        layout.addLayout(header)

        table = QTableWidget(0, 9)
        table.setHorizontalHeaderLabels(
            ["严重度", "规则", "程序块", "变量", "区域", "类型", "行号", "问题", "整改建议"]
        )
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.cellDoubleClicked.connect(self._jump_from_code_review)
        layout.addWidget(table, 2)

        layout.addWidget(QLabel("中文审查说明"))
        explanation = QPlainTextEdit()
        explanation.setReadOnly(True)
        explanation.setPlaceholderText(
            "规则检查始终离线可用。点击“生成 AI 中文说明”后，只把结构化检查结果交给 AI，不发送完整 PLC 源码。"
        )
        layout.addWidget(explanation, 1)

        self.detail_tabs.addTab(review_panel, "PLC Code Review")
        self.detail_tables["PLC Code Review"] = table
        self.detail_views["PLC Code Review AI"] = explanation
        return panel

    def on_analysis_finished(self, project: object, report: str) -> None:
        super().on_analysis_finished(project, report)
        if not self.project:
            return

        self._tag_report = self._tag_checker.check_project(self.project)
        tag_markdown = render_tag_check_markdown(self._tag_report)
        self._base_report_text = self.report_text.rstrip() + "\n\n" + tag_markdown + "\n"
        self.report_text = self._base_report_text
        self._populate_code_review()
        self.ai_review_button.setEnabled(True)
        self.log(
            "INFO",
            f"PLC Code Review 完成：检查 {self._tag_report.checked_variables} 个变量，发现 {len(self._tag_report.issues)} 个问题",
        )

    def _populate_code_review(self) -> None:
        table = self.detail_tables.get("PLC Code Review")
        if table is None or self._tag_report is None:
            return

        report = self._tag_report
        table.clearContents()
        table.setRowCount(len(report.issues))
        for row, issue in enumerate(report.issues):
            values = (
                issue.severity,
                issue.rule_id,
                issue.block_name,
                issue.variable,
                issue.section,
                issue.data_type,
                str(issue.line_number),
                issue.message,
                issue.suggestion,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        (issue.block_name, issue.line_number),
                    )
                table.setItem(row, col, item)

        table.resizeColumnsToContents()
        errors = sum(1 for item in report.issues if item.severity == "error")
        warnings = sum(1 for item in report.issues if item.severity == "warning")
        self.review_summary_label.setText(
            f"检查 {report.checked_blocks} 个程序块 / {report.checked_variables} 个变量；"
            f"发现 {len(report.issues)} 个问题（error {errors} / warning {warnings}）。"
        )
        self.detail_views["PLC Code Review AI"].setPlainText(
            "【离线规则摘要】\n" + render_rule_based_chinese_summary(report)
        )

        tab_index = self.detail_tabs.indexOf(table.parentWidget())
        if tab_index >= 0:
            self.detail_tabs.setTabText(tab_index, f"PLC Code Review ({len(report.issues)})")

    def generate_ai_review(self) -> None:
        if self._tag_report is None:
            return
        if self._ai_thread and self._ai_thread.isRunning():
            return
        if not self._tag_report.issues:
            self.detail_views["PLC Code Review AI"].setPlainText(
                "【离线规则摘要】\n" + render_rule_based_chinese_summary(self._tag_report)
            )
            return

        self.ai_review_button.setEnabled(False)
        self.detail_views["PLC Code Review AI"].setPlainText(
            "正在生成 AI 中文说明……\n\n仅发送结构化检查结果，不发送完整 PLC 源码。"
        )
        self.log("INFO", "开始生成 AI Code Review 中文说明")

        self._ai_thread = QThread(self)
        self._ai_worker = AIReviewWorker(self._tag_report)
        self._ai_worker.moveToThread(self._ai_thread)
        self._ai_thread.started.connect(self._ai_worker.run)
        self._ai_worker.finished.connect(self._on_ai_review_finished)
        self._ai_worker.failed.connect(self._on_ai_review_failed)
        self._ai_worker.finished.connect(self._ai_thread.quit)
        self._ai_worker.failed.connect(self._ai_thread.quit)
        self._ai_thread.finished.connect(self._ai_worker.deleteLater)
        self._ai_thread.finished.connect(self._ai_thread.deleteLater)
        self._ai_thread.start()

    def _on_ai_review_finished(self, text: str, provider: str, model: str) -> None:
        self.ai_review_button.setEnabled(True)
        rendered = f"【AI 中文说明 · {provider} / {model}】\n\n{text}"
        self.detail_views["PLC Code Review AI"].setPlainText(rendered)
        self.report_text = (
            self._base_report_text.rstrip()
            + "\n\n## AI PLC Code Review 中文说明\n\n"
            + text.strip()
            + "\n"
        )
        self.log("INFO", f"AI Code Review 中文说明生成完成：{provider}/{model}")

    def _on_ai_review_failed(self, message: str) -> None:
        self.ai_review_button.setEnabled(True)
        offline = render_rule_based_chinese_summary(self._tag_report) if self._tag_report else ""
        self.detail_views["PLC Code Review AI"].setPlainText(
            f"【AI 中文说明暂不可用】\n{message}\n\n【离线规则摘要】\n{offline}"
        )
        self.log("WARNING", message)

    def _jump_from_code_review(self, row: int, _column: int) -> None:
        table = self.detail_tables.get("PLC Code Review")
        if table is None or not self.project or row < 0:
            return
        first = table.item(row, 0)
        if first is None:
            return
        target = first.data(Qt.ItemDataRole.UserRole)
        if not isinstance(target, tuple) or len(target) != 2:
            return
        block_name, line_number = target
        target_index = next(
            (
                index
                for index, block in enumerate(self.project.blocks)
                if block.name.casefold() == str(block_name).casefold()
            ),
            None,
        )
        if target_index is None:
            self.log("WARNING", f"Code Review 目标块未找到：{block_name}")
            return
        self.block_table.selectRow(target_index)
        self.show_block(target_index)
        self.jump_to_source_line(int(line_number))
        self.log("INFO", f"Code Review 跳转：{block_name}:L{line_number}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SCL AI Analyzer")
    app.setApplicationDisplayName("SCL AI Analyzer")
    app.setApplicationVersion("0.11.0")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
