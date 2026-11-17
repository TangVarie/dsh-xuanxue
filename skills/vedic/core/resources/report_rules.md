# 报告打包规则

> 用途：当用户说"生成报告""打包""导出HTML"时执行

---

## 脚本位置

report_builder.py 在 core 模块的 `scripts/` 目录下（相对 vedic skill 根目录为 `core/scripts/report_builder.py`；下方命令里的 `scripts/` 以 `core/` 为根）。需要 `pip install markdown`。

找不到脚本时按以下顺序查找：
1. vedic skill 根目录下的 `core/scripts/report_builder.py`
2. 工作目录下的 `report_builder.py`（用户可能手动复制过）
3. 如果都找不到 → 告诉用户脚本路径，让用户确认位置

## 打包命令

```python
# 打包全部已有文件
python scripts/report_builder.py [工作目录] --lang cn

# 只打包core
python scripts/report_builder.py [工作目录] --include core --lang cn

# 只打包core + career
python scripts/report_builder.py [工作目录] --include core,career --lang cn
```

- report_builder 自动检测目录中存在哪些 MD 文件，只打包存在的；`--include` 可选择只打包特定部分（core,career,love,soul,timing,qa）。
- **分析模式**：默认读工作目录的 `analysis_record.json`（strict_blind / chart_derived / calibrated）；都没有时按 chart_derived，旧值 blind 视为 chart_derived。一般不传 `--mode`；只有 analysis_record 缺失且能说明实际模式时才传，不得为了好看传 `strict_blind`（条件见 `shared/permissions.md` §2）。
- **收录检查**：脚本打印每个模块"应收录 / 实际收录"。有缺章节时报告标「部分报告（缺：…）」，转述时照写，不称"完整报告"。

## ⚠️ 禁止行为

1. **禁止自动打开浏览器预览**：生成HTML后不要用 `open`/`start`/`xdg-open` 打开浏览器。只告诉用户文件路径，让用户自己决定是否打开。
2. **禁止在聊天框中输出HTML代码**：HTML文件由脚本生成，不要在对话中贴代码。
3. **生成完成后只报结果**：`"报告已生成：[完整文件路径]"`，附一行收录检查结果（完整 / 部分报告缺哪些）和分析模式，不做其他操作。
