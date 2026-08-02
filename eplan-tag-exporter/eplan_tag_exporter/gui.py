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
        self.title("EPLAN PDF Tag Exporter V1.0")
        self.geometry("760x420")
        self.minsize(680, 380)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.vendor_var = tk.StringVar(value="自动识别")
        self.status_var = tk.StringVar(value="请选择 EPLAN PDF 图纸。")
        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="EPLAN PDF Tag Exporter", font=("Microsoft YaHei UI", 20, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        ttk.Label(root, text="直接读取 EPLAN PDF 图纸，识别 PLC 地址并生成 IO 表格。").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 24)
        )

        ttk.Label(root, text="PDF图纸").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Entry(root, textvariable=self.input_var).grid(row=2, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="浏览…", command=self._choose_input).grid(row=2, column=2, padx=(12, 0), pady=8)

        ttk.Label(root, text="PLC 品牌").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Combobox(
            root, textvariable=self.vendor_var, values=list(VENDOR_OPTIONS.keys()), state="readonly"
        ).grid(row=3, column=1, sticky="ew", pady=8)

        ttk.Label(root, text="输出表格").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Entry(root, textvariable=self.output_var).grid(row=4, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="保存到…", command=self._choose_output).grid(row=4, column=2, padx=(12, 0), pady=8)

        ttk.Separator(root).grid(row=5, column=0, columnspan=3, sticky="ew", pady=20)
        action_frame = ttk.Frame(root)
        action_frame.grid(row=6, column=0, columnspan=3, sticky="ew")
        action_frame.columnconfigure(0, weight=1)
        ttk.Label(action_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(action_frame, text="识别并生成表格", command=self._run_export).grid(row=0, column=1, padx=(12, 0))
        ttk.Button(action_frame, text="打开输出目录", command=self._open_output_folder).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(
            root,
            text="当前先支持可搜索文字型 PDF；扫描图片型 PDF 后续加入 OCR/图纸视觉识别。",
            foreground="#666666",
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(24, 0))

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择 EPLAN PDF 图纸",
            filetypes=[("PDF 图纸", "*.pdf"), ("兼容标签表", "*.xlsx *.xls *.csv"), ("所有文件", "*.*")],
        )
        if not filename:
            return
        self.input_var.set(filename)
        input_path = Path(filename)
        self.output_var.set(str(input_path.with_name(f"{input_path.stem}_IO点表.xlsx")))
        self.status_var.set("图纸已选择，可以开始识别。")

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="选择表格保存位置", defaultextension=".xlsx", filetypes=[("Excel 表格", "*.xlsx")]
        )
        if filename:
            self.output_var.set(filename)

    def _run_export(self) -> None:
        input_text = self.input_var.get().strip()
        output_text = self.output_var.get().strip()
        if not input_text or not output_text:
            messagebox.showwarning("缺少文件", "请选择 PDF 图纸和输出表格位置。")
            return
        input_path = Path(input_text)
        output_path = Path(output_text)
        if not input_path.exists():
            messagebox.showerror("文件不存在", f"找不到输入文件：\n{input_path}")
            return
        try:
            self.status_var.set("正在读取 PDF、识别地址并生成表格…")
            self.update_idletasks()
            export_tags(input_path, output_path, plc_vendor=VENDOR_OPTIONS[self.vendor_var.get()])
        except Exception as exc:
            self.status_var.set("识别失败。")
            messagebox.showerror("识别失败", str(exc))
            return
        self.status_var.set(f"生成完成：{output_path.name}")
        messagebox.showinfo("完成", f"IO 表格已生成：\n{output_path}")

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
    EplanTagExporterApp().mainloop()


if __name__ == "__main__":
    main()
