# skills/ — 技能模块

> 本目录是 Resume Agent 的技能资产区，**可以进入 Git**。

## 用途

存放可复用的 Skill（封装好的多步工作流能力），例如：

| Skill | 说明 |
|---|---|
| `intake-experience` | 录入经历：对话采集 → 事实/表达分层 → 分类入库 |
| `analyze-jd` | JD 处理：保存原文 → 结构化分析 → 岗位能力模型 |
| `match-jd` | 匹配分析：检索资产库 → Strong/Partial/Gap/Transferable |
| `generate-resume` | 定向生成：匹配筛选 → 表达优化 → 选骨架 + 色板动态排版 → 出稿 + notes |
| `style-tune` | 设计风格：自然语言偏好 → 结构化设计参数（骨架/色板选用） |

## MVP v0.1 状态

技能逻辑以工作流规范形式维护在 [workflows/](../workflows/README.md) 与 [AGENT.md](../AGENT.md)，本目录暂为空，待流程稳定后封装。

## 红线

- Skill 是**产品能力**，不包含任何用户个人数据
- Skill 通过参数接收「简历库路径」，运行时只读调用
