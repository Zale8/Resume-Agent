# scripts/ — 工具脚本

> 本目录是 Resume Agent 的通用工具区，**可以进入 Git**。
> 红线：只允许保留**通用、与具体公司/岗位无关**的工具脚本（见 [AGENT.md §十三](../AGENT.md)）。

## 当前脚本

| 脚本 | 用途 | 依赖 |
|---|---|---|
| `check_pages.py` | 估算 docx 内容总高度，判断是否单页 A4 | **可选**：`python-docx`（`pip install python-docx`） |

```bash
python scripts/check_pages.py ../简历库/09_岗位定制简历/公司/岗位/日期/姓名_公司_岗位.docx
```

### 与内置溢出估算的关系

渲染时 `gen.py render` 已内置**零依赖**的文字量估算（`docx_engine.estimate_overflow`），
无需安装任何东西即可得到「是否可能超一页」的提示。

`check_pages.py` 是**更精确的可选增强**（按段落字号、行距、段间距逐段累加）：
- 有 `python-docx` 时用它做二次确认；
- 没有也不影响主流程 —— 这符合「零依赖必须能跑通」的架构约束。

> 两者都是**估算**，都不启动 Word，因此都不能替代「打开文档目视确认页码」。

## 禁止事项

- ❌ 不得放入公司特定脚本（如 `gen_某公司_resume_docx.py`）—— 这类脚本属临时工具，生成后即删
- ❌ 不得硬编码绝对路径
- ❌ 不得硬编码任何用户个人信息

## 已删除的历史脚本（v0.2）

| 脚本 | 删除原因 |
|---|---|
| `render_templates.py` | 硬编码 `C:\Users\...\Desktop` + 扫描桌面找文件夹；依赖 Word COM（`win32com`）与 `pymupdf`，在 macOS/Linux 上必然失败 |
| `gen_template_configs.py` | 硬编码绝对路径与工作区名，仅用于一次性生成 v3 模板配置；功能已由 `gen.py standardize` 取代 |
| `reprocess_templates.py` | 硬编码绝对路径 + 依赖 `lxml` / `PIL`；功能已由 `gen.py standardize` 取代 |

> `reprocess_templates.py` 文件头记录的两个关键机制已被继承进 `docx_engine.py`：
> ① 空格对齐槽位必须保持宽度；② t01 的品红（FF00FF）`<w:br/>` 补高 run 必须在填充前删除。
> 二者现在都有明确实现与回归测试，不再依赖一次性脚本。
