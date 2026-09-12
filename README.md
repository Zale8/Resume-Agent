# Resume-Agent

AI 个性化简历助手。

## 当前版本

MVP v0.2

## Resume-Agent 是什么

围绕「个人职业资产库」的 AI 简历管理与生成系统：

- 录入并长期保存真实经历，分层管理（事实层 / 表达层 / 岗位定制层）
- 输入招聘 JD，自动分析岗位要求
- 将 JD 与个人资产匹配，找出优势、差距与可迁移能力
- 根据岗位定向筛选、优化简历内容
- 按用户指定的模板与设计风格生成针对性简历
- **一条命令把内容渲染成 DOCX 成品**（v0.2 新增）

**核心原则：不能每次收到 JD 就凭空生成简历，一切生成必须基于真实资产。**

## 快速开始（三条命令）

```bash
python gen.py doctor            # 体检：环境 / 路径 / 模板 / 简历库
python gen.py list-templates    # 看有哪些模板、字段各是什么
python gen.py render --template template_02 --company 某科技公司 --role 产品经理 \
    --resume ../简历库/09_岗位定制简历/某科技公司/产品经理/2026-01-01/resume.md \
    --supplement
```

**零依赖**：只用 Python 3.8+ 标准库。不需要 `pip install`、不需要 Word/WPS/LibreOffice、
不需要 `pywin32` / `python-docx`。Windows / macOS / Linux 行为一致。

**零配置**：简历库路径自动发现，无任何写死的绝对路径。
换电脑、换用户名、换盘符、换人（换成别人的简历库）都能直接跑。
找不到时用 `--lib` 或环境变量 `RESUME_LIB` 指定。

> 给 AI 用：把 [agent_entry.md](agent_entry.md) 交给它即可，那是自包含的主提示词。

## 验证与守卫

```bash
python tests/check_privacy.py        # 数据隔离审计（工作区 + 全部提交历史 + 提交信息）
python tests/smoke_other_user.py     # 跨用户通用性（换人 / 换位置 / 不改代码）
python tests/smoke_docx_engine.py    # 模板填充正确性
python tests/smoke_resume_map.py     # 解析与映射正确性
python commit.py -m "feat: xxx"      # 带守卫的提交（先审计后提交）
```

| 保证 | 验证方式 |
|---|---|
| 零第三方依赖 | `python gen.py doctor` |
| 零绝对路径 | 核心代码扫描无命中 |
| 换人 / 换位置可用 | `python tests/smoke_other_user.py` |
| 个人数据不入库 | `python tests/check_privacy.py` |

## 架构：产品仓库 与 个人简历库分离

> 详见 [docs/architecture.md](docs/architecture.md)

```text
工作区/
├── Resume-Agent/        ← 产品仓库（本目录，Git 追踪，可公开/推送远程）
│   ├── gen.py           ← 统一 CLI 入口
│   ├── src/ prompts/ skills/ workflows/ templates/ docs/ tests/
│   └── README/PRD/AGENT/CHANGELOG/agent_entry
│
└── 简历库/              ← 个人简历数据库（本地，禁止进入 Git）
    ├── 00_个人信息/ 01_教育经历/ 02_实习经历/ 03_项目经历/
    ├── 04_校园经历/ 05_专业技能/ 06_求职意向/ 07_个人优势/
    ├── 08_证书奖项/ 09_简历母版/ 09_岗位定制简历/
    ├── 11_岗位JD/ 12_投递记录/ 13_JD分析/
    └── 99_配置/（用户偏好 + 设计风格）
```

- **Git 只存产品**：代码、Prompt、Skills、模板、工作流、文档。
- **个人数据只存本地**：信息、经历、照片、JD、分析、生成简历、偏好，绝不提交、不上传、不硬编码进产品。

## 核心流程

```
个人经历 → 简历库（事实层/表达层/定制层）
              ↓
招聘 JD → JD 分析 → 岗位能力模型
              ↓
        经历匹配（Strong/Partial/Gap/Transferable）
              ↓
        内容筛选与相关性排序 → resume.md
              ↓
模板（templates/，入Git）+ 设计风格（简历库/99_配置）
              ↓
   python gen.py render  →  定向简历 DOCX 成品
              ↓
        存入 简历库/09_岗位定制简历/{公司}/{岗位}/{日期}/
              ↓
        产品侧变更 Git 提交（简历产物不入 Git）
```

## 产品仓库目录结构

```
Resume-Agent/
├── README.md / PRD.md / AGENT.md / CHANGELOG.md / agent_entry.md / .gitignore
├── gen.py                    # 统一 CLI：doctor / list-templates / standardize / render
├── src/resume_generator/     # 产品代码
│   ├── paths.py              # 跨平台路径自动发现
│   ├── data_loader.py        # 简历库只读解析
│   ├── docx_engine.py        # 零依赖 DOCX 填充引擎（槽位对齐 / 照片 / 单页估算）
│   ├── resume_map.py         # resume.md → 模板字段映射（三级降级）
│   └── template_kit.py       # 任意 docx 标准化为可用模板
├── prompts/                  # Agent 提示词（方法论，不含个人数据）
├── skills/                   # 技能模块（产品能力封装）
├── workflows/                # 工作流规范索引
├── templates/                # 简历模板系统（版式/字体/配色）
├── tests/                    # 回归测试
└── docs/                     # 产品文档（含 architecture.md）
```

## 三层内容体系

| 层级 | 内容 | 规则 |
|---|---|---|
| Level 1 事实层 | 用户真实提供的信息 | 不得被 AI 擅自修改 |
| Level 2 专业表达层 | 基于事实优化语言表达 | 只优化表达，不改变事实 |
| Level 3 岗位定制层 | 按具体 JD 调整表达重点 | 必须来源于真实经历 |

## 命令行速查

| 命令 | 用途 |
|---|---|
| `python gen.py doctor` | 环境与路径体检，排查「跑不起来」 |
| `python gen.py list-templates` | 列出模板及其字段清单 |
| `python gen.py standardize 模板.docx --name template_07` | 把下载/收到的 docx 标准化为可用模板 |
| `python gen.py render --template X --company Y --role Z --resume resume.md` | 渲染 DOCX 成品 |
| `python gen.py --help` / `python gen.py render --help` | 查看全部参数 |

`render` 常用附加参数：

| 参数 | 作用 |
|---|---|
| `--jd` | JD 原文路径（校验并记入生成说明，不参与字段填充） |
| `--supplement` | 用简历库事实层补齐 resume.md 漏写的客观字段（联系方式、证书等） |
| `--fields resume.fields.json` | 直接给字段字典（优先级最高，最可控） |
| `--photo` / `--no-photo` | 指定或禁用证件照 |
| `--no-notes` / `--no-emit-fields` | 不生成生成说明 / 字段快照 |
| `--out` / `--filename` / `--date` | 覆盖输出路径与归档日期 |

### 渲染时自动完成的事

- **姓名自动识别**：从 `resume.md` 的 H1 解析，文件名自动为 `{姓名}_{公司}_{岗位}.docx`
- **自动归档**：产物落在 `resume.md` 所在目录（与内容层放在一起，便于迭代对比）
- **自动生成 `generation_notes.md`**：记录模板槽位用量、**被丢弃的内容**、留空字段、版式检查、内容指纹
- **自动输出 `*.fields.json`**：可复查、可回灌（改字段后 `--fields` 重跑，无需重写内容）

### 会主动警告的四类问题

| 警告 | 含义 | 处理 |
|---|---|---|
| 内容因槽位不足未进入简历 | 模板槽位固定（如只有 2 段实习），多余的被丢弃 | 重排 `resume.md` 把最相关放最前，或换槽位更多的模板 |
| 模板字段留空 | resume.md 与简历库都没有对应内容 | 让 AI 补章节，或加 `--supplement` |
| 窄槽位超出预留宽度 | 值比模板预留空间长，同行后续字段会被挤右 | 精简该字段值 |
| 内容可能超过一页 | 文字量估算超单页容量 | 删减 Weakly Relevant 内容（**不要缩字号**） |

## 如何使用（对话示例）

- 「记录一下我的这个项目」→ 自动分类保存为项目经历（存入简历库）
- 「这是一个 JD」→ 保存原文并自动分析
- 「这个岗位我匹配吗？」→ 输出 Strong/Partial/Gap/Transferable 匹配分析
- 「根据这个 JD 给我生成一份简历」→ 执行完整定向生成流程，并渲染出 DOCX
- 「用我自己的模板」→ `gen.py standardize` 后即可渲染
- 「我要简洁科技感一点」→ 更新设计偏好（不改经历事实）

详细规范见 [agent_entry.md](agent_entry.md)（可执行版）与 [AGENT.md](AGENT.md)（治理规则）。

## 当前不支持（V2 及以上）

自动搜索岗位、自动登录招聘网站、自动填写网申、**自动投递简历**、验证码处理、自动发送邮件、
招聘网站爬虫、招聘账号管理、自动岗位推荐。

> **MVP 范围明确**：第一版只做「自动生成简历」这一条链路，并把它做扎实。
> 自动投递不属于 MVP。主流招聘平台用户协议普遍禁止自动化投递，且会被风控识别
> 并可能导致封号，投递环节必须保留人工确认。详见 [agent_entry.md §10](agent_entry.md)。

## Git 提交规范

仅用于产品侧变更：

| 类型 | 用途 |
|---|---|
| feat | 新增产品功能/目录/能力 |
| update | 更新产品内容 |
| fix | 修复问题 |
| style | 模板或设计调整 |
| docs | PRD、README、AGENT、说明文档修改 |

> 个人简历资产修改不产生 Git 提交（数据在仓库外）。提交前必须确认暂存区无个人真实信息。
