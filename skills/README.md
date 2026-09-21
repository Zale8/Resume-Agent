# skills/ — 技能模块

> 本目录是 Resume Agent 的技能资产区，**可以进入 Git**。

## 计划中的技能（尚未实现）

以下技能在设计中，逻辑目前以 Prompt + AGENT.md 工作流规范形式维护：

| 计划 Skill | 对应 Prompt / 规范 | 状态 |
|---|---|---|
| `intake-experience` | `prompts/expression_optimizer.md` + AGENT.md §四 | 以 Prompt 形式运行 |
| `analyze-jd` | `prompts/jd_analyst.md` + AGENT.md §七 | 以 Prompt 形式运行 |
| `match-jd` | `prompts/matcher.md` + AGENT.md §七 | 以 Prompt 形式运行 |
| `generate-resume` | `prompts/resume_writer.md` + AGENT.md §六/§十四 | 以 Prompt 形式运行 |
| `style-tune` | AGENT.md §十一 + `简历库/99_配置/` | 以对话形式运行 |

## 当前版本（v0.8.2）状态

技能逻辑以 Prompt + 工作流规范形式维护在 [prompts/](../prompts/)、[workflows/](../workflows/README.md) 与 [AGENT.md](../AGENT.md)，本目录暂无实现文件。待流程稳定后封装为独立 Skill 文件。

## 红线

- Skill 是**产品能力**，不包含任何用户个人数据
- Skill 通过参数接收「简历库路径」，运行时只读调用
