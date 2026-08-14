# EPLAN Tag Exporter

面向电气自动化工程师的 EPLAN / IO 标签整理工具。

## V1.1 功能

- 读取 CSV、XLSX、XLS 格式的标签表
- 支持 PLC 品牌自动识别或手动选择
- 支持 Siemens、Mitsubishi、Beckhoff、CODESYS 常见地址
- 自动分类 DI、DO、AI、AO、Memory、DB、Unknown
- 提供 Windows 图形界面
- 输出标准化 Excel 工作簿
- 生成 IO 明细和统计表
- 按参考工程格式生成 TIA Excel 工作簿：汇总、总表、项目表、原始提取、导入步骤
- TIA 变量名按“项目_逻辑地址”生成，地址自动补 `%`，并生成 TIA CSV

## 安装

```bash
cd eplan-tag-exporter
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

## Windows 图形界面

安装依赖后，双击：

```text
run_gui.pyw
```

或者在命令行运行：

```bash
python -m eplan_tag_exporter.gui
```

图形界面包含：

- 输入文件选择
- PLC 品牌下拉选择
- 输出文件位置选择
- 一键生成普通 Excel、TIA 格式 Excel、CSV 或 TIA CSV
- 打开输出目录

### 打包为独立 EXE

在 Windows 中双击：

```text
build_windows.bat
```

脚本会自动安装 PyInstaller，并生成：

```text
dist\EPLAN-Tag-Exporter-v1.1.0.exe
```

生成的 EXE 可以直接运行，无需用户另外安装 Python。

### TIA Excel 工作簿

勾选“**TIA 格式 Excel**”后会生成 `<基础文件名>_TIA.xlsx`，包含：

- `说明_汇总`：项目 DI/DO 数量、总数和导入提示
- `TIA_All_总表`：所有变量和溯源列
- `TIA_<项目>`：按输入文件名识别的项目变量表
- `原始提取_含重复`：地址、说明、页码、源文件等复核信息
- `TIA导入步骤`：导入前后的安全检查说明

主表前 8 列为 `Name`、`Path`、`Data Type`、`Logical Address`、`Comment`、`Hmi Visible`、`Hmi Accessible`、`Hmi Writable`，后 4 列为项目溯源信息。不同 TIA Portal 版本的 XLSX 内部字段可能不同；若目标版本拒绝直接导入，请先从该版本导出空白变量表，再复制前 8 列。

## 命令行使用

自动识别品牌：

```bash
python -m eplan_tag_exporter input.xlsx -o output.xlsx
```

手动选择 PLC 品牌：

```bash
python -m eplan_tag_exporter input.xlsx -o output.xlsx --plc-vendor siemens
python -m eplan_tag_exporter input.xlsx -o output.xlsx --plc-vendor mitsubishi
python -m eplan_tag_exporter input.xlsx -o output.xlsx --plc-vendor beckhoff
python -m eplan_tag_exporter input.xlsx -o output.xlsx --plc-vendor codesys
```

可选值：`auto`、`siemens`、`mitsubishi`、`beckhoff`、`codesys`。

手动模式适合处理地址重叠。例如 `M100`：

- `--plc-vendor siemens`：识别为 Siemens Memory
- `--plc-vendor mitsubishi`：识别为 Mitsubishi Memory

输入表至少需要一个地址列。程序会自动寻找以下列名：

- 地址：地址、Address、PLC地址、变量地址
- 名称：名称、Name、Tag、变量名
- 说明：说明、Description、Comment、注释

也可以手动指定列：

```bash
python -m eplan_tag_exporter input.xlsx -o output.xlsx \
  --plc-vendor siemens \
  --address-column PLC地址 \
  --name-column 变量名 \
  --description-column 注释
```

## 地址识别示例

| 地址 | 品牌 | 类型 |
|---|---|---|
| I0.0 | Siemens | DI |
| Q0.0 | Siemens | DO |
| IW64 / PIW256 / AIW64 | Siemens | AI |
| QW80 / PQW512 / AQW80 | Siemens | AO |
| DB100.DBX0.0 | Siemens | DB |
| X0 / X10 | Mitsubishi | DI |
| Y0 / Y20 | Mitsubishi | DO |
| M100 | Siemens 或 Mitsubishi | Memory |
| D200 | Mitsubishi | Data Register |
| %IX0.0 | Beckhoff/CODESYS | DI |
| %QX0.0 | Beckhoff/CODESYS | DO |
| %IW0 | Beckhoff/CODESYS | AI |
| %QW0 | Beckhoff/CODESYS | AO |

## 开发计划

- EPLAN XML / EDZ / 报表适配
- 安全 IO 分类
- 元件代号识别，如 QF、KM、SB、SQ、YV、M
- TwinCAT、GX Works3、CODESYS 专用变量表导出
- 图形界面数据预览和列映射
- AI 辅助生成中文说明

## 许可证

MIT

