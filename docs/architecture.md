# 架构说明：代码目录与简历数据目录分离

> v0.1 起生效。核心原则：**Git 仓库只存产品，个人数据只存本地。**
> v0.2 曾追加固定模板渲染层；**v0.3 已移除模板库，改为 Agent 动态生成 DOCX**（见第五节）。

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
│   ├── gen.py                 ← 运维 CLI（doctor / check-library，零依赖）
│   ├── .gitignore
│   ├── src/                   ← 产品代码：paths 路径发现 + data_loader 只读解析
│   ├── prompts/               ← Agent 提示词（方法论，不含个人数据）
│   ├── scripts/               ← 通用工具（check_pages.py 页数估算）
│   ├── skills/                ← 技能模块（产品能力封装）
│   ├── workflows/             ← 工作流规范
│   ├── tests/                 ← 隐私审计
│   └── docs/                  ← 产品文档
│   （v0.3 起无 templates/ 目录：不保存任何固定简历模板）
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
    ├── 09_岗位定制简历/        ← 生成产物（generated）
    ├── 10_简历母版/           ← 3 份母版编排规则（A产品运营 / B AI应用 / C硬件制造）
    ├── 11_岗位JD/             ← JD 原文
    ├── 12_投递记录/
    ├── 13_JD分析/             ← 匹配分析（人岗关系）
    ├── 14_JD结构化分析/        ← JD 结构化分析（岗位要什么）
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
| 通用工具 | `Resume-Agent/scripts/` | ✅ |
| 工作流规范 | `Resume-Agent/workflows/` | ✅ |
| 固定简历模板 | —— | ❌ v0.3 起不保存模板；版式每次动态生成 |
| 配置（产品侧） | `.gitignore` 等 | ✅ |
| 文档 | `Resume-Agent/docs/`、`README/PRD/CHANGELOG` | ✅ |
| 个人信息/教育/实习/项目/技能 | `简历库/` | ❌ |
| 联系方式/照片 | `简历库/00_个人信息/` | ❌ |
| JD 原文 / 结构化分析 / 匹配分析 | `简历库/11、14、13` | ❌ |
| 投递记录 / 生成简历 / 简历母版 | `简历库/12、09、10` | ❌ |
| 用户偏好 | `简历库/99_配置/` | ❌ |

## 三、产品如何调用个人数据

- 产品代码 / Agent **只读引用**简历库路径，不在仓库内保存数据副本
- 简历库路径通过参数或会话上下文传入，不硬编码进可提交的文件
- 文档示例一律使用虚构人物（张三 / 某科技公司）

## 四、双保险

1. **物理隔离**：简历库在 Git 仓库目录之外，`git add` 永远扫不到
2. **.gitignore 规则**：仓库内仍保留 `data/ jd/ analysis/ generated/ config/` 等路径的忽略规则，防止误建目录后误提交

## 五、DOCX 生成层架构（v0.3 重写）

### v0.2 固定模板路线为什么被废弃

v0.2 的链路是 `templates/*/template.docx（{{FIELD}} 占位符）+ resume.md → gen.py render`。
真实使用暴露三个结构性问题：

1. **槽位丢内容**：模板字段固定，真实简历出现「技能 3 项全被丢弃、字段留空、
   证书只进 3/4 项」等警告，岗位最关键的匹配内容反而进不了简历；
2. **版式不可演进**：用户最满意的成品（单栏极简、横幅工牌卡）都是 Agent 临时脚本
   动态排版做的，模板库复刻不出来；「换色式假模板」也被用户明确否决；
3. **产品链路与实际生产脱节**：5 份成品里只有 1 份走 render，其余全靠临时脚本。

2026-09-13 用户决策：删除模板库与渲染流水线（docx_engine / resume_map /
template_kit 及 3 个相关 smoke 测试一并移除，Git 历史可查），**每份简历由 Agent
自行生成**。

### v0.3 数据流

```
简历库/00~08（INPUT，只读）
        +
resume.md（AI 产出并经用户确认的内容层）
        +
99_配置/style_preferences.md（设计偏好）
        │
        ▼
Agent 编写「一次性 python-docx 脚本」（系统临时目录，不入库）
   ├── data_loader / paths   运行时读取事实与定位简历库
   ├── 版式代码               页面/字体/配色/分栏/表格/照片/色块，按本次设计构建
   └── argv 参数              公司/岗位/日期，不硬编码
        │
        ▼
简历库/09_岗位定制简历/{公司}/{岗位}/{日期}/姓名_公司_岗位.docx（OUTPUT）
        │
        ▼
Word COM ComputeStatistics(2) 实测页数 = 1 → 用户目视确认 → 删除临时脚本
```

**OUTPUT 永不回流为 INPUT**（见 [AGENT.md §十二](../AGENT.md)）。

### 依赖策略（分层）

| 层 | 依赖 | 说明 |
|---|---|---|
| 运维 CLI（gen.py / check_privacy） | 仅 Python 3.8+ 标准库 | 零依赖，任意机器可体检 |
| DOCX 构建（一次性脚本） | `python-docx` | 生成必需；doctor 检测并提示安装 |
| 页数实测（一次性脚本） | Word/WPS + `pywin32` | 可选，Windows 本机最可靠 |
| 无 Word 时估算 | `scripts/check_pages.py` | 通用近似估算 |

### 为什么动态生成不违背「可复现 / 可换人」

- **可换人**：脚本不含任何个人事实，数据全部运行时从简历库读取；换简历库即换人，不改产品。
- **可追溯**：每次生成的 resume.md + generation_notes.md（含版式设计、取舍、实测页数）
  存在岗位目录；产品侧规范（AGENT §十四 / agent_entry §5）保证每次生成行为一致。
- **不污染仓库**：一次性脚本放临时目录、用后即删，公司/岗位特定信息永远不进 Git。
- 版式是**个人产物**（随岗位变化），产品沉淀的是设计范式（双栏/横幅卡/单栏极简）
  与通用规范，而不是 docx 文件。

### 单页校验

- 以 Word COM `ComputeStatistics(2)` **实测 = 1 页**为交付门槛；
- 无 Word 时用 `scripts/check_pages.py` 估算 + 必须用户目视确认；
- 超页动作是删减内容（先砍 Weakly Relevant）与收紧间距，正文不低于 9pt。

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

## 七、跨用户通用性（v0.3 口径）

v0.2 曾用 `tests/smoke_other_user.py` 端到端验证「换人 / 换位置 / 不改代码」；
v0.3 渲染流水线移除后该测试同步删除。通用性改由以下机制保证（可随时人工复核）：

1. `paths.py` 自动发现简历库（支持 `--lib` / `RESUME_LIB`、任意目录名）——`gen.py doctor` 验证；
2. `data_loader.py` 只读解析简历库，产品代码内零个人数据——`tests/check_privacy.py` 审计；
3. **一次性生成脚本禁止硬编码任何个人事实**，数据运行时读取、公司/岗位走参数
   （AGENT.md §十三/§十四）；换人 = 换简历库，产品代码与规范零改动。

## 八、历史教训（依赖与可移植性）

> 数据隔离相关的历次事故见上文「六、历史教训（务必阅读）」，此处不重复。

**v0.1 的渲染链路依赖 `C:\Users\13032\Desktop` + 扫描桌面目录名 + Word COM。**
后果：换电脑/换用户名即失效；macOS/Linux 完全无法运行；Word 无响应时脚本挂起（实测）。

v0.2 处理：删除 `render_templates.py` / `gen_template_configs.py` / `reprocess_templates.py`，
重写为零依赖、零绝对路径的 `gen.py` + `src/resume_generator/`。

v0.3 再处理：实践证明固定模板槽位会丢内容、满意版式均来自动态生成，
故删除 `templates/` 与 `docx_engine.py` / `resume_map.py` / `template_kit.py`，
改为 Agent 一次性 python-docx 脚本动态生成（用后即删），规范固化于
[AGENT.md §十四](../AGENT.md)。`gen.py` 本身仍保持零依赖。

### 当前可移植性保证

| 保证 | 验证方式 |
|---|---|
| 运维 CLI 零第三方依赖（仅标准库） | `python gen.py doctor` |
| 零绝对路径 | 核心代码扫描 `C:\Users` 无命中 |
| 跨用户 / 跨位置 | 路径自动发现 + 生成脚本不硬编码个人数据（§七） |
| 数据隔离 | `python tests/check_privacy.py` |
| 生成依赖可见性 | `gen.py doctor` 检测 python-docx / pywin32 是否可用 |
