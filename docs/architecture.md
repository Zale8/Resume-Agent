# 架构说明：代码目录与简历数据目录分离

> v0.1 起生效。核心原则：**Git 仓库只存产品，个人数据只存本地。**

## 一、目录拓扑

```text
创建自动投递简历智能体_DJgqY5KXSOKwX4WL9E5BNA/
│
├── Resume-Agent/              ← 产品仓库（Git 追踪，可公开/可推送远程）
│   ├── README.md
│   ├── PRD.md
│   ├── AGENT.md               ← Agent 核心行为规范
│   ├── CHANGELOG.md
│   ├── .gitignore
│   ├── src/                   ← 产品代码（MVP 为空）
│   ├── prompts/               ← Agent 提示词（方法论，不含个人数据）
│   ├── skills/                ← 技能模块（产品能力封装）
│   ├── workflows/             ← 工作流规范
│   ├── templates/             ← 简历模板系统（版式/字体/配色规则）
│   └── docs/                  ← 产品文档
│
└── 简历库/                    ← 个人简历数据库（本地，禁止进入 Git）
    ├── 00_个人信息/            ← 联系方式 + photos/ 证件照
    ├── 01_教育经历/
    ├── 02_实习经历/            ← 含校园经历
    ├── 03_项目经历/
    ├── 04_专业技能/
    ├── 05_求职意向/
    ├── 06_个人优势/            ← 自我评价
    ├── 07_证书奖项/
    ├── 08_简历母版/            ← 原始简历全文存档
    ├── 09_岗位定制简历/        ← 生成产物（generated）
    ├── 10_岗位JD/             ← JD 原文
    ├── 11_投递记录/
    ├── 12_JD分析/             ← 结构化分析 + 匹配分析
    └── 99_配置/               ← user_preferences / style_preferences
```

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

## 五、历史教训

v0.1 初版曾把个人简历数据放在 `Resume-Agent/data/` 并提交进入 Git 历史。
发现后处理：个人数据迁出仓库 + **重建 Git 历史**（本地仓库、无远程、无协作），
确保个人数据从未存在于任何 Git 提交中。
