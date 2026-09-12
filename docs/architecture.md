# 架构说明：代码目录与简历数据目录分离

> v0.1 起生效。核心原则：**Git 仓库只存产品，个人数据只存本地。**
> v0.2 追加：**渲染层零依赖、零绝对路径、跨平台**（见第五节）。

## 一、目录拓扑

```text
<任意工作区目录>/
│
├── Resume-Agent/              ← 产品仓库（Git 追踪，可公开/可推送远程）
│   ├── README.md
│   ├── PRD.md
│   ├── AGENT.md               ← Agent 核心行为规范（治理规则）
│   ├── agent_entry.md         ← 通用主提示词（任意 AI 加载即用的入口）
│   ├── CHANGELOG.md
│   ├── gen.py                 ← 统一 CLI 入口
│   ├── .gitignore
│   ├── src/                   ← 产品代码（零第三方依赖）
│   ├── prompts/               ← Agent 提示词（方法论，不含个人数据）
│   ├── skills/                ← 技能模块（产品能力封装）
│   ├── workflows/             ← 工作流规范
│   ├── templates/             ← 简历模板系统（版式/字体/配色规则）
│   ├── tests/                 ← 回归测试
│   └── docs/                  ← 产品文档
│
└── 简历库/                    ← 个人简历数据库（本地，禁止进入 Git）
    ├── 00_个人信息/            ← 联系方式 + photos/ 证件照
    ├── 01_教育经历/
    ├── 02_实习经历/            ← 实习/工作经历
    ├── 03_项目经历/
    ├── 04_校园经历/            ← 校园组织/班级/社会实践/自学/课设
    ├── 05_专业技能/
    ├── 06_求职意向/
    ├── 07_个人优势/            ← 自我评价
    ├── 08_证书奖项/
    ├── 09_简历母版/            ← 原始简历全文存档
    ├── 09_岗位定制简历/        ← 生成产物（generated）
    ├── 11_岗位JD/             ← JD 原文
    ├── 12_投递记录/
    ├── 13_JD分析/             ← 结构化分析 + 匹配分析
    └── 99_配置/               ← user_preferences / style_preferences
```

> 顶层工作区目录名不做任何假设。`src/resume_generator/paths.py` 会从当前目录
> 逐级向上查找名为「简历库」（或 `resume_lib`）的目录；也可用 `--lib` / `RESUME_LIB` 指定。
> 这保证工程复制到任意电脑、任意用户名、任意盘符下都能直接运行。

## 二、什么能进 Git

| 类别 | 位置 | 进 Git |
|---|---|---|
| 产品代码 | `Resume-Agent/src/` | ✅ |
| Agent / Prompt | `Resume-Agent/prompts/`、`AGENT.md` | ✅ |
| Skills | `Resume-Agent/skills/` | ✅ |
| 模板系统 | `Resume-Agent/templates/` | ✅ |
| 工作流规范 | `Resume-Agent/workflows/` | ✅ |
| 配置（产品侧） | `.gitignore` 等 | ✅ |
| 文档 | `Resume-Agent/docs/`、`README/PRD/CHANGELOG` | ✅ |
| 个人信息/教育/实习/项目/技能 | `简历库/` | ❌ |
| 联系方式/照片 | `简历库/00_个人信息/` | ❌ |
| JD / 分析 / 生成简历 | `简历库/10、12、09` | ❌ |
| 用户偏好 | `简历库/99_配置/` | ❌ |

## 三、产品如何调用个人数据

- 产品代码 / Agent **只读引用**简历库路径，不在仓库内保存数据副本
- 简历库路径通过参数或会话上下文传入，不硬编码进可提交的文件
- 文档示例一律使用虚构人物（张三 / 某科技公司）

## 四、双保险

1. **物理隔离**：简历库在 Git 仓库目录之外，`git add` 永远扫不到
2. **.gitignore 规则**：仓库内仍保留 `data/ jd/ analysis/ generated/ config/` 等路径的忽略规则，防止误建目录后误提交

## 五、渲染层架构（v0.2 新增）

### 数据流

```
简历库/00~08（INPUT，只读）
        +
模板 templates/*/template.docx（产品资产）
        +
resume.md / resume.fields.json（AI 产出的内容层）
        │
        ▼
   gen.py render
        │
        ├── paths.py        定位简历库（无绝对路径）
        ├── resume_map.py   内容 → 模板字段（三级降级）
        ├── docx_engine.py  字段 → DOCX（只改 <w:t> 文本）
        └── data_loader.py  仅 --supplement 时读取客观字段
        │
        ▼
简历库/09_岗位定制简历/{公司}/{岗位}/{日期}/*.docx（OUTPUT）
```

**OUTPUT 永不回流为 INPUT**（见 [AGENT.md §十二](../AGENT.md)）。

### 为什么自己实现 DOCX 填充而不用 python-docx

| 原因 | 说明 |
|---|---|
| 零依赖 | `python-docx` 需要 `pip install`；离线/内网/新电脑上会卡住 |
| 保真 | `python-docx` 会丢弃非标准命名空间（`v:` / `o:` / `w10:` / `mc:`），破坏模板版式 |
| 问题本质 | 模板里的 `{{FIELD}}` 全部位于单个 `<w:t>` run 内，是纯文本替换问题 |
| 确定性 | 只改文本、其余 zip 条目字节复制，结果可复现、可审计 |

### 三个必须处理的版式陷阱

1. **空格对齐槽位**：模板用字面空格而非制表位对齐，例如
   `<w:t>{{W1C}}　　　　          {{W1P}}</w:t>`。
   替换值短于槽位必须补空格，否则「职位」左移、整行错位。
   → 实现为 `docx_engine.Slot`（容量 = 标记宽度 + 其后空格宽度）。
2. **`mc:Choice` / `mc:Fallback` 双写**：文本框在 OOXML 中写入两份内容，
   只替换一份会导致 Word 与其他阅读器显示不一致。
   → 填充时两个分支都会被替换；统计文字量时剔除 `mc:Fallback` 以免虚高。
3. **t01 品红补高 run**：`<w:rPr>` 颜色为 `FF00FF`、只含 `<w:br/>` 的 run 用于撑起左栏高度，
   使右栏浮动文本框不错位。必须在填充前删除，否则会多出空白行。
   → `docx_engine.strip_marker_runs`。

### 单页校验的诚实边界

`docx_engine.estimate_overflow` 统计文字量估算行数，**不启动 Word、不做真实排版**，
因此只能给出 `ok` / `likely_overflow` 两档提示，不是精确页数。

- 零依赖、跨平台、随时可用 → 采用它作为默认提示；
- 需要更精确时，装 `python-docx` 后用 `scripts/check_pages.py` 做二次确认；
- 最终仍须打开文档**目视确认**。

## 六、数据隔离的可执行验证（v0.2.2 新增）

> 光靠「人肉检查 git status」不够 —— 本仓库曾经就漏过：个人数据被删除后
> **仍留在提交历史里**，而且文档示例里混入了真实姓名/公司/学校名。

### 三层防护

| 层级 | 手段 | 覆盖范围 |
|---|---|---|
| 1. 物理隔离 | 简历库在 Git 工作树之外 | `git add` 永远扫不到 |
| 2. `.gitignore` 兜底 | 忽略 `data/ jd/ analysis/ generated/ config/` 等误建目录 | 误建目录不会入库 |
| 3. **可执行审计** | `python tests/check_privacy.py` | 工作区 + **全部提交历史** + 提交信息 + 被忽略文件 + 作者身份 |

第 3 层是关键补充：前两层只能防「现在」，防不了「过去」和「文档示例」。

### 审计内容

```bash
python tests/check_privacy.py              # 审计
python tests/check_privacy.py --install-hook  # 安装 pre-commit 守卫
```

| 检查项 | 说明 |
|---|---|
| A. 工作区全部文件 | 含未跟踪文件；排除二进制与 `.git` |
| B. 全部提交历史 | 遍历每个 revision 的每个文件版本 |
| C. 提交信息正文 | commit message 里也可能写出真实姓名 |
| D. 被忽略但存在的文件 | `git status --ignored` 里的实际文件 |
| E. 提交作者身份 | 仅提示（那是用户 git 身份，不属简历数据泄漏） |

强标识模式：手机号、邮箱、身份证、银行卡，**外加用户自定义敏感词清单**
（真实姓名/学校/公司名），清单放在仓库外的
`简历库/99_配置/privacy_terms.txt`。

> 为什么清单必须在仓库外：把真实姓名写进产品仓库，本身就是一次泄漏。

### 提交入口

Git 的 `pre-commit` 钩子在 Windows 上要通过 `sh` 执行，受限环境里会因
`couldn't create signal pipe, Win32 error 5` 直接失败，导致**连正常提交都做不了**。
因此推荐使用**零依赖的 Python 提交入口**：

```bash
python commit.py -m "feat: 新增 xxx"           # 只提交已暂存内容
python commit.py -m "docs: 更新说明" --all     # 先 add -A 再提交
```

它会先跑审计，通过才提交；失败则拒绝并打印处理方式。
`--force` 可跳过（仅在人工确认无个人数据时使用）。

> `--install-hook` 仍可用（适合正常桌面环境），但若遇到上述 `sh` 报错，
> 请把 `.git/hooks/pre-commit` 改名停用，改用 `commit.py`。

### 历史教训（务必阅读）

本仓库的 Git 历史**曾被重写两次**：

1. **v0.1 初版**：个人简历数据放在 `Resume-Agent/data/` 并提交入库。
   → 迁出个人数据 + 重建历史。
2. **v0.2.1 复查发现**：即使数据已删除，**历史里仍然存在**：
   - `scripts/reprocess_templates.py`（11 个提交）含测试手机号与邮箱
   - `templates/template_05/template_config.md`（8 个提交）含真实姓名
   - `scripts/gen_xiaomi_resume_docx.py` 等含真实公司名
   - 提交信息正文含真实姓名
   → 再次重建历史：保留全部 12 个提交与产品文件，仅丢弃含个人数据的
     4 个文件路径，并对提交正文脱敏。

**结论：删除文件不等于删除历史。** 任何涉及个人数据的提交都必须假设
「它会永久留在历史里」，因此必须在提交前阻断，而不是事后清理。

## 七、跨用户通用性验证

`tests/smoke_other_user.py` 在系统临时目录下另建一套**完全虚构**的简历库
（目录名故意不叫「简历库」，路径层级与产品仓库无关），然后验证：

1. 从该目录运行 `gen.py doctor` 能自动定位到这个陌生位置的简历库
2. 不传 `--lib` / `--out` 也能渲染成功（靠自动发现 + 自动归档）
3. 产物落在该简历库的岗位定制简历目录下
4. 产物内容是正确的虚构用户数据
5. 产物**完全不含**真实用户信息（按仓库外词表逐项比对）
6. 产品仓库内没有被写入任何用户数据

这直接验证了「换人 / 换位置 / 不改代码」这一核心要求。

## 八、历史教训（依赖与可移植性）

> 数据隔离相关的历次事故见上文「六、历史教训（务必阅读）」，此处不重复。

**v0.1 的渲染链路依赖 `C:\Users\13032\Desktop` + 扫描桌面目录名 + Word COM。**
后果：换电脑/换用户名即失效；macOS/Linux 完全无法运行；Word 无响应时脚本挂起（实测）。

v0.2 处理：删除 `render_templates.py` / `gen_template_configs.py` / `reprocess_templates.py`，
重写为零依赖、零绝对路径的 `gen.py` + `src/resume_generator/`，
并在 [AGENT.md §十四](../AGENT.md) 将其固化为不可违反的规范。

### 当前可移植性保证

| 保证 | 验证方式 |
|---|---|
| 零第三方依赖（仅 Python 3.8+ 标准库） | `python gen.py doctor` |
| 零绝对路径 | 核心代码扫描 `C:\Users` 无命中 |
| 跨用户 / 跨位置 | `python tests/smoke_other_user.py` |
| 数据隔离 | `python tests/check_privacy.py` |
| 模板填充正确性 | `python tests/smoke_docx_engine.py` |
| 解析与映射正确性 | `python tests/smoke_resume_map.py` |
