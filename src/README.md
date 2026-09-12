# src/ — 产品代码

> 本目录是 Resume Agent 的产品代码区，**可以进入 Git**。

## 用途

存放 Resume Agent 的程序代码、自动化逻辑。

## 当前状态（MVP v0.2）

**已实现。** 采用**零第三方依赖**设计：只用 Python 3.8+ 标准库，
克隆下来即可运行，不需要 `pip install`，不依赖 Word / WPS / LibreOffice。

```
src/
└── resume_generator/
    ├── paths.py          # 跨平台路径自动发现（消灭绝对路径）
    ├── data_loader.py    # 简历库只读解析（唯一个人信息来源）
    ├── docx_engine.py    # 零依赖 DOCX 填充引擎
    ├── resume_map.py     # resume.md → 模板字段映射
    └── template_kit.py   # 任意 docx 标准化为可用模板
```

### 各模块职责

| 模块 | 职责 | 关键设计 |
|---|---|---|
| `paths.py` | 定位简历库与产品仓库 | 命令行参数 > 环境变量 > 逐级向上查找；找不到时给出可操作的修复指引 |
| `data_loader.py` | 只读解析 `简历库/00~08` 的 md | 只读不改；解析失败返回 None/空列表，由调用方决定 |
| `docx_engine.py` | 把字段值填进 `template.docx` | 只改 `<w:t>` 文本；保持空格对齐槽位；支持照片替换；单页溢出估算 |
| `resume_map.py` | 把 `resume.md` 翻译成模板字段 | 三级降级：字段 JSON > 内嵌字段表 > 章节结构解析 |
| `template_kit.py` | 标准化用户上传的 docx | 探测/改写占位符语法；识别照片占位；生成配置与映射文档 |

### 入口

统一 CLI 在仓库根目录：`gen.py`

```bash
python gen.py doctor
python gen.py list-templates
python gen.py standardize 模板.docx --name template_07
python gen.py render --template template_02 --company X --role Y --resume resume.md
```

## 架构红线

- **禁止**在代码中硬编码任何用户真实个人信息（姓名、电话、邮箱、经历等）
- 产品代码只通过**读取本地简历库路径**的方式调用个人数据
- **禁止绝对路径**（不得出现 `C:\Users\...`）
- **禁止 Windows 专有依赖**（`pywin32` / Word COM / WPS COM）
- **禁止**引入第三方包作为必需依赖（可选增强功能须能优雅降级）

详见 [AGENT.md §十四](../AGENT.md) 渲染层实现规范。

## 后续规划

| 版本 | 内容 |
|---|---|
| v0.3 | 模板版式可视化预览（不依赖 Word 的渲染方案） |
| v1.0 | 更多 CLI 子命令（`intake` / `match`）；模板设计器 |
| v2.0 | 网申表单理解与辅助填写（保留人工确认环节，不做自动投递） |
