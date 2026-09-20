# scripts/ — 工具脚本

> 本目录是 Resume Agent 的通用工具区，**可以进入 Git**。
> 红线：只允许保留**通用、与具体公司/岗位无关**的工具脚本（见 [AGENT.md §十三](../AGENT.md)）。

## 当前脚本

| 脚本 | 用途 | 依赖 |
|---|---|---|
| `check_pages.py` | 估算 docx 内容总高度，判断是否单页 A4 | `python-docx`（`pip install python-docx`） |

```bash
python scripts/check_pages.py ../简历库/09_岗位定制简历/公司/岗位/日期/姓名_公司_岗位.docx
```

### 与 Word COM 实测的关系（v0.3）

DOCX 由 Agent 动态生成后，**页数以 Word/WPS COM `ComputeStatistics(2)` 实测为准**
（在一次性生成/验证脚本中调用，本机已装 pywin32）。

`check_pages.py` 用于**没有 Word / 不适合启动 COM 时的快速估算**
（按段落字号、行距、段间距逐段累加）：

- 估算提示「预计单页内 / 预计溢出」；
- 它不启动 Word，结果是近似值，**不能替代 COM 实测，也不能替代打开文档目视确认**；
- 估算溢出时的正确动作是删减内容（先砍 Weakly Relevant），不是缩字号硬塞。

## 禁止事项

- ❌ 不得放入公司/岗位特定的简历生成脚本——这类脚本属临时工具，用户定稿确认后自动删除（AGENT.md §十三）
- ❌ 不得硬编码绝对路径
- ❌ 不得硬编码任何用户个人信息

## 已删除的历史脚本

| 脚本 | 删除原因 |
|---|---|
| `render_templates.py` | 硬编码桌面路径 + 扫描目录；依赖 Word COM 与 pymupdf，跨平台失败 |
| `gen_template_configs.py` / `reprocess_templates.py` | 一次性模板处理脚本；固定模板库已于 v0.3 整体移除 |
