# src/ — 产品代码

> 本目录是 Resume Agent 的产品代码区，**可以进入 Git**。

## 用途

存放 Resume Agent 的程序代码：简历库路径发现、只读解析、**DesignSpec 设计决策层**、
通用排版积木与三种骨架。
DOCX 成品由本目录渲染：Agent 确定本份 **Design Decision** →
`assemble_job_spec()` 装配为 **DesignSpec** → `validate_spec()` 校验 →
`build_document(design_spec=)` 渲染（见 [AGENT.md §十四](../AGENT.md)）；
仅当需要骨架未覆盖的全新版式时，才编写一次性 python-docx 脚本，脚本不在本目录，用户定稿确认后自动删除。

## 当前状态（v0.8.2）

`gen.py` 等 CLI 代码**零第三方依赖**（仅 Python 3.8+ 标准库）；
DOCX 生成环节使用 `python-docx`（`gen.py doctor` 会检测是否安装）。

```
src/
└── resume_generator/
    ├── paths.py          # 跨平台路径自动发现（消灭绝对路径）
    ├── data_loader.py    # 简历库只读解析（唯一个人信息来源）
    ├── layout_kit.py     # 通用排版积木：页面/字体/色板/照片/间距（无个人事实、无成品版式）
    ├── render_style.py   # DesignSpec → RenderStyle 解析（Renderer 唯一可读的排版参数包）
    ├── skeletons.py      # 三种可复用骨架：build_document(blocks, skeleton_id/palette_id, design_spec=)
    └── design/           # DesignSpec 设计决策层（v0.7/v0.8 主链路）
        ├── spec.py       # schema：Sourced / PageSpec / TypographySpec / ColorSpec …
        ├── presets.py    # 三范式 Preset：build_p1/p2/p3_spec + build_p3_compact_spec
        ├── assembly.py   # assemble_job_spec()：delta 装配（photo / typography / section / experience）
        ├── validator.py  # validate_spec()：ERROR 即拒绝渲染（不校验不渲染）
        └── consumption.py# 字段消费矩阵（⚠️ 改设计前必查：49.7% 字段无消费点）
```

### 各模块职责

| 模块 | 职责 | 关键设计 |
|---|---|---|
| `paths.py` | 定位简历库与产品仓库 | 命令行参数 > 环境变量 > 逐级向上查找；找不到时给出可操作的修复指引 |
| `data_loader.py` | 只读解析 `简历库/00~08` 的 md | 只读不改；解析失败返回 None/空列表，由调用方决定 |
| `layout_kit.py` | 提供页面/字体/色板/照片/间距等**排版原语**与 `ResumeBlocks` 数据结构 | 不含个人事实、不含完整版式；`ResumeBlocks` 由调用方从简历库填入 |
| `render_style.py` | 把 DesignSpec 解析成 `RenderStyle`（字号/行距/间距/组件/色板） | Renderer 唯一可读的排版参数包；Spec 缺字段时回退骨架 Profile 并登记 `spec_fallbacks` |
| `design/`（spec / presets / assembly / validator / consumption） | DesignSpec 设计决策层：schema、三范式 Preset、装配、校验、字段消费矩阵 | `assemble_job_spec()` 只有 4 个 delta（photo / typography / section / **无 page、无 color**）；**consumption.py 是"哪些字段真能改"的唯一权威** |
| `skeletons.py` | 三种骨架（双栏侧边栏 / 横幅工牌卡 / 单栏极简） | 先定骨架再定色板；核心板块顺序固定；禁止「旧骨架换色冒充新设计」；**列宽比例/边距/照片盒硬编码于 `_LAYOUT_CONFIG`** |

> **骨架 ≠ 模板**：骨架只提供布局思路与通用组件，配色/字体/组件必须按本次岗位重新组合。
> 换色不等于新设计（见 `layout_kit.py` 顶部说明）。

### 入口

统一运维 CLI 在仓库根目录：`gen.py`

```bash
python gen.py doctor           # 环境 / 路径 / 简历库 / python-docx 依赖
python gen.py check-library    # 四阶段产物一致性
```

## 架构红线

- **禁止**在代码中硬编码任何用户真实个人信息（姓名、电话、邮箱、经历等）
- 产品代码只通过**读取本地简历库路径**的方式调用个人数据
- **禁止绝对路径**（产品代码与文档中不得出现 `C:\Users\...`）
- 不在本目录放置任何**具体公司/岗位**的简历生成脚本或成品版式；
  通用排版积木与骨架（`layout_kit.py` / `skeletons.py`）是允许且鼓励的产品沉淀；
  一次性的、含本次公司/岗位信息的脚本仍须临时使用，用户定稿确认后自动删除

### 自测

```bash
python tests/smoke_layout_kit.py   # 用虚构人物验证三种骨架能产出 DOCX（需 python-docx）
```

详见 [AGENT.md §十三 / §十四](../AGENT.md)。

## 后续规划

| 版本 | 内容 |
|---|---|
| v0.4 | ✅ 已沉淀动态排版的**通用**辅助函数与三种骨架（`layout_kit.py` / `skeletons.py`，不含任何版式成品） |
| v0.6 | ✅ `10_简历母版` 体系退役；视觉来源唯一化为 DesignSpec → Skeleton → Renderer |
| v0.7 | ✅ Golden Sample 回归基准 + 照片浮动能力（`photo.floating` / `photo.border`） |
| v0.8 | ✅ Design Decision 进入生产文档；P3 Compact 紧凑版式（**当前版本 v0.8.2**：页面底色接入 Renderer） |
| v1.0 | 更多 CLI 子命令（`intake` / `match`） |
| v2.0 | 网申表单理解与辅助填写（保留人工确认环节，不做自动投递） |
