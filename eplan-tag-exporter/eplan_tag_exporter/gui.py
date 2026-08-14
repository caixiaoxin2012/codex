from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .io_service import export_outputs


VENDOR_OPTIONS = {
    "自动识别": "auto",
    "西门子 Siemens": "siemens",
    "三菱 Mitsubishi": "mitsubishi",
    "倍福 Beckhoff": "beckhoff",
    "CODESYS": "codesys",
}


APP_VERSION = "1.1.2"


def resource_path(*parts: str) -> Path:
    """Resolve bundled assets in source and PyInstaller one-file builds."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    base_path = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[1]
    return base_path.joinpath(*parts)


class EplanTagExporterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"EPLAN PDF Tag Exporter V{APP_VERSION}")
        self.geometry("820x520")
        self.minsize(720, 480)
        self._set_app_icon()

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.vendor_var = tk.StringVar(value="自动识别")
        self.xlsx_var = tk.BooleanVar(value=False)
        self.csv_var = tk.BooleanVar(value=False)
        self.tia_xlsx_var = tk.BooleanVar(value=True)
        self.tia_csv_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="请选择 EPLAN PDF 图纸或兼容标签表。")
        self._build_ui()

    def _set_app_icon(self) -> None:
        ico_path = resource_path("assets", "xilin-app-icon.ico")
        png_path = resource_path("assets", "xilin-app-icon.png")
        if sys.platform == "win32" and ico_path.exists():
            try:
                self.iconbitmap(default=str(ico_path))
                return
            except tk.TclError:
                pass
        if png_path.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, self._icon_image)
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="EPLAN PDF Tag Exporter", font=("Microsoft YaHei UI", 20, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        ttk.Label(root, text="统一输入/输出接口：读取 EPLAN PDF 或标签表，识别 PLC 地址并生成工程数据文件。").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 24)
        )

        ttk.Label(root, text="输入文件").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Entry(root, textvariable=self.input_var).grid(row=2, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="浏览…", command=self._choose_input).grid(row=2, column=2, padx=(12, 0), pady=8)

        ttk.Label(root, text="PLC 品牌").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Combobox(
            root, textvariable=self.vendor_var, values=list(VENDOR_OPTIONS.keys()), state="readonly"
        ).grid(row=3, column=1, sticky="ew", pady=8)

        ttk.Label(root, text="输出位置/文件名").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=8)
        ttk.Entry(root, textvariable=self.output_var).grid(row=4, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="保存到…", command=self._choose_output).grid(row=4, column=2, padx=(12, 0), pady=8)

        ttk.Label(root, text="输出格式").grid(row=5, column=0, sticky="nw", padx=(0, 12), pady=10)
        format_frame = ttk.Frame(root)
        format_frame.grid(row=5, column=1, columnspan=2, sticky="w", pady=8)
        ttk.Checkbutton(format_frame, text="Excel 明细 (.xlsx)", variable=self.xlsx_var).grid(row=0, column=0, padx=(0, 18))
        ttk.Checkbutton(format_frame, text="TIA 格式 Excel", variable=self.tia_xlsx_var).grid(row=0, column=1, padx=(0, 18))
        ttk.Checkbutton(format_frame, text="CSV (.csv)", variable=self.csv_var).grid(row=0, column=2, padx=(0, 18))
        ttk.Checkbutton(format_frame, text="TIA Portal CSV", variable=self.tia_csv_var).grid(row=0, column=3)

        ttk.Separator(root).grid(row=6, column=0, columnspan=3, sticky="ew", pady=20)
        action_frame = ttk.Frame(root)
        action_frame.grid(row=7, column=0, columnspan=3, sticky="ew")
        action_frame.columnconfigure(0, weight=1)
        ttk.Label(action_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(action_frame, text="识别并导出", command=self._run_export).grid(row=0, column=1, padx=(12, 0))
        ttk.Button(action_frame, text="打开输出目录", command=self._open_output_folder).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(
            root,
            text="输入支持：PDF / XLSX / XLS / CSV。当前 PDF 先支持可搜索文字型图纸；扫描版后续接 OCR/视觉识别。",
            foreground="#666666",
            wraplength=740,
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(24, 0))

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择 EPLAN 图纸或标签文件",
            filetypes=[
                ("支持的输入文件", "*.pdf *.xlsx *.xls *.csv"),
                ("PDF 图纸", "*.pdf"),
                ("Excel / CSV", "*.xlsx *.xls *.csv"),
                ("所有文件", "*.*"),
            ],
        )
        if not filename:
            return
        self.input_var.set(filename)
        input_path = Path(filename)
        self.output_var.set(str(input_path.with_name(f"{input_path.stem}_PLC变量表_TIA可导入.xlsx")))
        self.status_var.set("输入文件已选择，可以开始识别。")

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="选择输出位置和基础文件名",
            defaultextension=".xlsx",
            filetypes=[("Excel 表格", "*.xlsx"), ("所有文件", "*.*")],
        )
        if filename:
            self.output_var.set(filename)

    def _selected_formats(self) -> list[str]:
        formats: list[str] = []
        if self.xlsx_var.get():
            formats.append("xlsx")
        if self.csv_var.get():
            formats.append("csv")
        if self.tia_xlsx_var.get():
            formats.append("tia_xlsx")
        if self.tia_csv_var.get():
            formats.append("tia_csv")
        return formats

    def _run_export(self) -> None:
        input_text = self.input_var.get().strip()
        output_text = self.output_var.get().strip()
        formats = self._selected_formats()
        if not input_text or not output_text:
            messagebox.showwarning("缺少文件", "请选择输入文件和输出位置。")
            return
        if not formats:
            messagebox.showwarning("缺少输出格式", "请至少选择一种输出格式。")
            return

        input_path = Path(input_text)
        output_base = Path(output_text)
        if not input_path.exists():
            messagebox.showerror("文件不存在", f"找不到输入文件：\n{input_path}")
            return

        try:
            self.status_var.set("正在读取、识别并导出…")
            self.update_idletasks()
            result = export_outputs(
                input_path,
                output_base,
                plc_vendor=VENDOR_OPTIONS[self.vendor_var.get()],
                formats=formats,
            )
        except Exception as exc:
            self.status_var.set("导出失败。")
            messagebox.showerror("导出失败", str(exc))
            return

        names = "\n".join(path.name for path in result.files)
        self.status_var.set(f"完成：识别 {result.row_count} 条记录，生成 {len(result.files)} 个文件。")
        messagebox.showinfo("完成", f"已生成：\n{names}\n\n请优先打开文件名中带“TIA”的工作簿。")

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
