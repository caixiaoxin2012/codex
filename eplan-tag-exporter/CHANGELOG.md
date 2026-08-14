# 版本记录 / Changelog

本文件记录 EPLAN Tag Exporter 的正式版本变化。

版本规则采用语义化版本：`主版本.次版本.修订版本`。

- 主版本：重大架构或兼容性变化
- 次版本：新增功能，保持兼容
- 修订版本：问题修复、小优化

## V1.0.0 — 2026-08-14

首个正式 Windows 发布版本。

### 已完成
- 支持直接读取可搜索文字型 EPLAN PDF 图纸
- 兼容 CSV / XLSX / XLS 标签表输入
- PLC 品牌自动识别或手动选择
- 支持 Siemens、Mitsubishi、Beckhoff、CODESYS 常见地址规则
- PLC 地址分类：DI、DO、AI、AO、Memory、DB 等
- PDF 地址与邻近元件代号、中文说明关联
- 增加关联置信度：high / medium / low
- Excel 输出：IO明细、IO统计、元件统计、原始识别数据
- 普通 CSV 输出
- Siemens TIA Portal CSV 导出模板
- Windows Tkinter 图形界面
- PyInstaller 单文件 EXE 打包
- GitHub Actions 自动生成 Windows EXE
- 正式 EXE：`EPLAN-Tag-Exporter-v1.0.0.exe`

### 当前限制
- 扫描图片型 PDF 暂未加入 OCR
- EPLAN 跨页连接和交叉引用仍需继续增强
- 不同公司/项目的图纸模板需要继续使用真实样本校准

## 后续版本记录要求

以后每次正式更新至少记录：

1. 版本号和发布日期
2. 新增功能
3. 修复问题
4. 兼容性变化
5. 已知限制
6. 对应 EXE 文件名
7. GitHub 发布/合并状态
8. Google Drive 发布状态
