from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .__main__ import export_tags


VENDOR_OPTIONS = {
    "自动识别": "auto",
    "西门子 Siemens": "siemens",
    "三菱 Mitsubishi": "mitsubishi",
    "倍福 Beckhoff": "beckhoff",
    "CODESYS": "codesys",
}


class EplanTagExporterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EPLAN Tag Exporter V1.0")
        self.geometry("760x420")
        self.minsize(680, 380)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.vendor_var = tk.StringVar(value="自动识别")
        self.status_var = tk.StringVar(value="请选择 EPLAN 导出的 CSV、XLSX 或 XLS 文件。")

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        title = ttk.Label(root, text="EPLAN Tag Exporter", font=("Microsoft YaHei UI", 20, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        subtitle = ttk.Label(
            root,
            text="导入 EPLAN 标签表，选择 PLC 品牌，一键生成 IO 明细与统计 Excel。",
        )
        subtitle.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 24))

        ttk.Label(root, text="输入文件").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Entry(root, textvariable=self.input_var).grid(row=2, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="浏览…", command=self._choose_input).grid(row=2, column=2, padx=(12, 0), pady=8)

        ttk.Label(root, text="PLC 品牌").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=8)
        vendor_box = ttk.Combobox(
            root,
            textvariable=self.vendor_var,
            values=list(VENDOR_OPTIONS.keys()),
            state="readonly",
        )
        vendor_box.grid(row=3, column=1, sticky="ew", pady=8)

        ttk.Label(root, text="输出文件").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Entry(root, textvariable=self.output_var).grid(row=4, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="保存到…", command=self._choose_output).grid(row=4, column=2, padx=(12, 0), pady=8)

        separator = ttk.Separator(root)
        separator.grid(row=5, column=0, columnspan=3, sticky="ew", pady=20)

        action_frame = ttk.Frame(root)
        action_frame.grid(row=6, column=0, columnspan=3, sticky="ew")
        action_frame.columnconfigure(0, weight=1)

        ttk.Label(action_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(action_frame, text="生成 Excel", command=self._run_export).grid(row=0, column=1, padx=(12, 0))
        ttk.Button(action_frame, text="打开输出目录", command=self._open_output_folder).grid(row=0, column=2, padx=(8, 0))

        tips = ttk.Label(
            root,
            text="提示：手动选择品牌可正确处理 M100 等跨品牌重叠地址。",
            foreground="#666666",
        )
        tips.grid(row=7, column=0, columnspan=3, sticky="w", pady=(24, 0))

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择 EPLAN 标签文件",
            filetypes=[
                ("标签表", "*.xlsx *.xls *.csv"),
                ("Excel 文件", "*.xlsx *.xls"),
                ("CSV 文件", "*.csv"),
                ("所有文件", "*.*"),
            ],
        )
        if not filename:
            return
        self.input_var.set(filename)
        input_path = Path(filename)
        self.output_var.set(str(input_path.with_name(f"{input_path.stem}_IO统计.xlsx")))
        self.status_var.set("文件已选择，可以开始生成。")

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="选择输出位置",
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx")],
        )
        if filename:
            self.output_var.set(filename)

    def _run_export(self) -> None:
        input_text = self.input_var.get().strip()
        output_text = self.output_var.get().strip()
        if not input_text:
            messagebox.showwarning("缺少输入文件", "请先选择输入文件。")
            return
        if not output_text:
            messagebox.showwarning("缺少输出文件", "请选择输出文件位置。")
            return

        input_path = Path(input_text)
        output_path = Path(output_text)
        vendor = VENDOR_OPTIONS[self.vendor_var.get()]

        if not input_path.exists():
            messagebox.showerror("文件不存在", f"找不到输入文件：\n{input_path}")
            return

        try:
            self.status_var.set("正在分析并生成 Excel…")
            self.update_idletasks()
            export_tags(input_path, output_path, plc_vendor=vendor)
        except Exception as exc:  # GUI boundary: present a clear message to the user.
            self.status_var.set("生成失败。")
            messagebox.showerror("生成失败", str(exc))
            return

        self.status_var.set(f"生成完成：{output_path.name}")
        messagebox.showinfo("完成", f"Excel 已生成：\n{output_path}")

    def _open_output_folder(self) -> None:
        output_text = self.output_var.get().strip()
        folder = Path(output_text).parent if output_text else Path.cwd()
        folder.mkdir(parents=True, exist_ok=True)

        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)


def main() -> None:
    app = EplanTagExporterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
