# EPLAN Tag Exporter

面向电气自动化工程师的 EPLAN / IO 标签整理工具。

## V1.0 功能

- 读取 CSV、XLSX、XLS 格式的标签表
- 支持 PLC 品牌自动识别或手动选择
- 支持 Siemens、Mitsubishi、Beckhoff、CODESYS 常见地址
- 自动分类 DI、DO、AI、AO、Memory、DB、Unknown
- 输出标准化 Excel 工作簿
- 生成 IO 明细和统计表

## 安装

```bash
cd eplan-tag-exporter
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

## 使用

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
- TIA Portal、TwinCAT、GX Works3、CODESYS 变量表导出
- Windows 图形界面与品牌下拉框
- AI 辅助生成中文说明

## 许可证

MIT
