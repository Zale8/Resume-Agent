# Resume-Agent

AI 个性化简历助手。

## 当前版本

**v0.8.2**（2026-09-21）— 动态排版生成；DesignSpec 设计决策层 + 三种范式 Preset + 三种骨架；固定模板库与母版体系均已移除

## Resume-Agent 是什么

围绕「个人职业资产库」的 AI 简历管理与生成系统：

- 录入并长期保存真实经历，分层管理（事实层 / 表达层 / 岗位定制层）
- 输入招聘 JD，自动分析岗位要求
- 将 JD 与个人资产匹配，找出优势、差距与可迁移能力
- 根据岗位定向筛选、优化简历内容
- **Agent 按 JD 与设计偏好动态排版，直接生成 DOCX 成品**（v0.3 起不再使用固定模板；v0.4 起沉淀通用积木 `layout_kit` 与三种骨架 `skeletons`）

**核心原则：不能每次收到 JD 就凭空生成简历，一切生成必须基于真实资产。**

> 为什么没有模板库？v0.2 的「固定模板 + 占位符填充」在真实使用中会丢内容
> （技能被槽位丢弃、字段留空、超页），而最满意的几份成品恰恰是 Agent 按岗位
> 动态排版生成的。v0.3 删除模板库，每份简历由 Agent 自行设计版式。
> 详见 [AGENT.md §十四](AGENT.md)。

## 快速开始

```bash
python gen.py doctor            # 体检：环境 / 路径 / 简历库 / python-docx 依赖
python gen.py check-library     # 校验 JD原文/JD结构化/匹配分析/成品 四阶段一致性
```

**CLI 零依赖**：`gen.py` 只用 Python 3.8+ 标准库，不需要 `pip install` 即可体检。

**生成 DOCX 需要 python-docx**：Agent 动态生成简历时使用（`pip install -r requirements.txt`，
doctor 会检测，并会提示 `layout_kit.py` / `skeletons.py` 是否就位）；
实测真实页数可选装 Word/WPS + pywin32（仅 Windows）。

**零配置**：简历库路径自动发现，核心代码无任何写死的绝对路径。
换电脑、换用户名、换盘符、换人（换成别人的简历库）都能直接跑。
找不到时用 `--lib` 或环境变量 `RESUME_LIB` 指定。

> 给 AI 用：把 [agent_entry.md](agent_entry.md) 交给它即可，那是自包含的执行手册。

## 简历怎么生成（v0.4 流程）

```
resume.md 内容层（与用户确认真实内容）
      ↓
Agent 确定版式：骨架（双栏 / 横幅卡 / 单栏极简）+ 行业配色 + 字体 + 照片形态
      ↓
复用 src/resume_generator 的通用积木：layout_kit（页面/字体/色板/照片/间距）
+ skeletons（三种骨架 build_document）
      ↓
由数据填充 ResumeBlocks（数据全部运行时从简历库读取，不硬编码）
      ↓
生成 DOCX → Word COM 实测页数 = 1 → 用户目视确认
      ↓
存入 简历库/09_岗位定制简历/{公司}/{岗位}/{日期}/ → 用户定稿确认后自动删除临时脚本
```

版式随岗位变化、内容随 JD 重组，但**事实数据全程不变、不虚构**。

## 验证与守卫

```bash
python gen.py doctor               # 环境/路径/依赖体检（含 layout_kit/skeletons 就位检查）
python gen.py check-library        # 简历库四阶段产物一致性
python tests/smoke_layout_kit.py   # 用虚构人物验证三种骨架能产出 DOCX（需 python-docx）
python tests/check_privacy.py      # 数据隔离审计（工作区 + 全部提交历史 + 提交信息）
python commit.py -m "feat: xxx"    # 带守卫的提交（先审计后提交）
```

| 保证 | 验证方式 |
|---|---|
| CLI 零第三方依赖 | `python gen.py doctor` |
| 核心代码零绝对路径 | 仓库扫描无命中 |
| 换人 / 换位置可用 | 简历库路径自动发现 + 数据全部运行时读取，脚本不含个人数据 |
| 个人数据不入库 | `python tests/check_privacy.py` |

## 架构：产品仓库 与 个人简历库分离

> 详见 [docs/architecture.md](docs/architecture.md)

```text
工作区/
├── Resume-Agent/        ← 产品仓库（本目录，Git 追踪，可公开/推送远程）
│   ├── gen.py           ← 运维 CLI（doctor / check-library）
│   ├── src/ prompts/ skills/ workflows/ docs/ tests/ scripts/
│   └── README/PRD/AGENT/CHANGELOG/agent_entry
│   （注意：不包含 templates/ —— 不保存任何固定简历模板）
│
└── 简历库/              ← 个人简历数据库（本地，禁止进入 Git）
    ├── 00_个人信息/ 01_教育经历/ 02_实习经历/ 03_项目经历/
    ├── 04_校园经历/ 05_专业技能/ 06_求职意向/ 07_个人优势/
    ├── 08_证书奖项/ 09_岗位定制简历/
    ├── 11_岗位JD/ 12_投递记录/
    ├── 13_JD分析/（匹配分析） 14_JD结构化分析/（岗位要什么）
    └── 99_配置/（用户偏好 + 设计风格）
```

- **Git 只存产品**：代码、Prompt、Skills、工作流、文档、通用工具。
- **个人数据只存本地**：信息、经历、照片、JD、分析、生成简历、偏好，绝不提交、不上传、不硬编码进产品。

## 核心流程

```
个人经历 → 简历库（事实层/表达层/定制层）
              ↓
招聘 JD → ① JD 结构化 → 岗位能力模型 → ② 人岗匹配（Strong/Partial/Gap/Transferable）
              ↓
        内容筛选与相关性排序 → resume.md 内容层
              ↓
   Agent 读取设计偏好（简历库/99_配置）→ 动态排版生成 DOCX → 实测单页
              ↓
        存入 简历库/09_岗位定制简历/{公司}/{岗位}/{日期}/
              ↓
        产品侧变更 Git 提交（简历产物与临时脚本不入 Git）
```

## 产品仓库目录结构

```
Resume-Agent/
├── README.md / PRD.md / AGENT.md / CHANGELOG.md / agent_entry.md / .gitignore
├── gen.py                    # 运维 CLI：doctor / check-library
├── requirements.txt          # python-docx 依赖声明
├── src/resume_generator/     # 产品代码
│   ├── paths.py              # 跨平台路径自动发现
│   ├── data_loader.py        # 简历库只读解析（唯一个人信息读取入口）
│   ├── layout_kit.py         # 通用排版积木（页面/字体/色板/照片/间距，无个人数据）
│   └── skeletons.py          # 三种可复用骨架（build_document）
├── prompts/                  # Agent 提示词（方法论，不含个人数据）
├── scripts/check_pages.py    # 通用页数估算工具（可选 python-docx）
├── skills/ workflows/ docs/ tests/
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
| `python gen.py doctor` | 环境与路径体检（含 python-docx 检测），排查「跑不起来」 |
| `python gen.py check-library` | 校验 11/14/13/09 四处产物是否齐全、命名是否规范 |
| `python scripts/check_pages.py <docx>` | 无 Word 时估算 DOCX 内容高度是否单页 |
| `python tests/smoke_layout_kit.py` | 验证三种骨架可用（虚构数据，需 python-docx） |
| `python gen.py --help` | 查看全部参数 |

DOCX 成品不是通过命令渲染的，而是 Agent 在对话中按
[agent_entry.md 第 5 节](agent_entry.md) 复用 `layout_kit` + `skeletons` 动态生成，
并用 Word COM 实测页数。

## 如何使用（对话示例）

- 「记录一下我的这个项目」→ 自动分类保存为项目经历（存入简历库）
- 「这是一个 JD」→ 保存原文并自动分析（14 结构化 + 13 匹配分析）
- 「这个岗位我匹配吗？」→ 输出 Strong/Partial/Gap/Transferable 匹配分析
- 「根据这个 JD 给我生成一份简历」→ 内容确认 → Agent 动态排版生成单页 DOCX
- 「我要简洁科技感一点 / 换个配色」→ 调整设计重新生成（不改经历事实）

详细规范见 [agent_entry.md](agent_entry.md)（执行手册）与 [AGENT.md](AGENT.md)（治理规则）。

## 当前不支持（V2 及以上）

自动搜索岗位、自动登录招聘网站、自动填写网申、**自动投递简历**、验证码处理、自动发送邮件、
招聘网站爬虫、招聘账号管理、自动岗位推荐。

> **MVP 范围明确**：第一版只做「自动生成简历」这一条链路，并把它做扎实。
> 自动投递不属于 MVP。主流招聘平台用户协议普遍禁止自动化投递，且会被风控识别
> 并可能导致封号，投递环节必须保留人工确认。

## Git 提交规范

仅用于产品侧变更：

| 类型 | 用途 |
|---|---|
| feat | 新增产品功能/目录/能力 |
| update | 更新产品内容 |
| fix | 修复问题 |
| style | 版式设计规范 / 风格配置机制调整 |
| docs | PRD、README、AGENT、说明文档修改 |

> 个人简历资产修改不产生 Git 提交（数据在仓库外）。提交前必须确认暂存区无个人真实信息。
