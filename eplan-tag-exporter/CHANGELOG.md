# 版本记录 / Changelog

本文件记录 EPLAN Tag Exporter 的正式版本变化。

版本规则采用语义化版本：`主版本.次版本.修订版本`。

- 主版本：重大架构或兼容性变化
- 次版本：新增功能，保持兼容
- 修订版本：问题修复、小优化

## V1.1.2 - 2026-08-14

将 Windows 软件图标更换为上海羲林自动化的官方品牌图形。

### 变更
- 从公司提供的 `上海羲林自动化 团队成员介绍.pdf` 内嵌 Logo 提取绿色/橙色图形主体
- 新增 16、24、32、48、64、128、256 像素多尺寸 Windows ICO
- EXE 文件图标、Windows 窗口图标和任务栏图标统一使用羲林图形
- PyInstaller 构建同时嵌入 ICO，并打包运行时所需的 ICO/PNG 资源
- 版本号更新为 V1.1.2，EXE 文件名更新为 `EPLAN-Tag-Exporter-v1.1.2.exe`

### 来源与限制
- 公司资料标注官网为 `www.sh_xilin.com`，但该域名在 2026-08-14 无法解析，不能可靠下载当前 favicon
- 使用的是同一份公司原始资料中的官方 Logo；原图只有 80 x 76 像素，因此放大查看会有轻微模糊

## V1.1.1 — 2026-08-14

修复实际导出内容杂乱和容易打开错误文件的问题。

### 修复
- 图形界面默认只生成 `TIA 格式 Excel`，普通识别明细不再默认输出
- 默认文件名改为 `<输入文件>_PLC变量表_TIA可导入.xlsx`，完成提示明确推荐打开带 `TIA` 的工作簿
- TIA 主表按输入区、输出区、存储区、DB 区和数字地址自然排序
- 同一逻辑地址只保留一条，优先采用高置信度且带中文说明的记录
- 空地址、Unknown 地址和不能确定数据类型的记录不再混入 TIA 主表
- 相邻接线行产生的说明噪声被清理；原始记录保留在 `原始提取_含重复` 供复核
- TIA 主表和原始复核表冻结标题行，并扩大说明、源文件和注释列
- 同时选择普通 Excel 与 TIA Excel 时使用不同文件名，避免互相覆盖

### 验证
- 使用乱序、重复地址、无效地址、邻行噪声的测试数据验证清洗结果
- 25 项自动化测试通过
- Windows EXE：`EPLAN-Tag-Exporter-v1.1.1.exe`
- GitHub：PR #3 已 squash 合并到 `main`（提交 `99aa163`）；Windows 构建 run #6 成功
- Google Drive：EXE 文件 ID `1uKwmc6yE4NVevM1cuCKtcRX6O2YZIcKF`；整理示例 ID `1pTfGe7mjiq-7PNLhUd-MQqRCNr6nTZvE`

## V1.1.0 — 2026-08-14

新增参考 `PLC变量表_TIA可导入.xlsx` 的 TIA Excel 工作簿导出。

### 新增
- 新增 `TIA 格式 Excel` 图形界面选项，并默认启用
- 输出 `说明_汇总`、`TIA_All_总表`、`TIA_<项目>`、`原始提取_含重复`、`TIA导入步骤` 工作表
- TIA 主表采用参考文件的 12 列结构、列宽、颜色和 `TableStyleMedium2` 条纹表格样式
- 变量名按 `<项目>_<地址>` 生成，并对重复地址自动追加序号
- Siemens I/Q/M 逻辑地址自动补 `%`，DI/DO/AI/AO/Memory/DB 映射为常见 TIA 数据类型
- TIA CSV 扩展为 8 列，并增加三项 HMI 权限字段
- 增加 TIA Excel/CSV 的结构、命名、地址、样式和汇总自动化测试

### 兼容性说明
- 参考文件使用列名 `Hmi Writable`；当前 Siemens V21 文档写作 `Hmi Writeable`，本版本优先保持参考文件格式
- TIA Portal 不同版本导出的内部 ID、`TagTableProperties` 和语言列可能不同，程序不伪造这些版本相关字段
- 导入生产 PLC 前必须在对应 TIA 版本中复核名称、地址、数据类型、冲突和安全点位

### 发布文件
- Windows EXE：`EPLAN-Tag-Exporter-v1.1.0.exe`
- 样例：`PK06_TIA导出样例_v1.1.0.xlsx`
- GitHub：PR #2 已 squash 合并到 `main`（提交 `b15615a`）；Windows 构建 run #5 成功
- Google Drive：EXE 文件 ID `1RUffsg84nbBeZ6u4DqDx4hmWwbAOdIK1`；样例文件 ID `1WeIBy5L_Tt4aDHoaEavY03EVVMxrVm9h`

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
