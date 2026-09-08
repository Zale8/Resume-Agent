# prompts/ — Agent 提示词

> 本目录是 Resume Agent 的提示词资产区，**可以进入 Git**。

## 用途

存放可复用的 Agent 系统提示词、角色提示词、任务提示词模板。

## 内容规划

| 文件 | 说明 |
|---|---|
| `system_prompt.md` | 简历助手主系统提示词（后续从 AGENT.md 沉淀） |
| `jd_analyst.md` | JD 结构化分析专家提示词 |
| `matcher.md` | 岗位匹配分析专家提示词 |
| `resume_writer.md` | 定向简历撰写专家提示词 |
| `expression_optimizer.md` | 经历表达优化专家提示词 |

## MVP v0.1 状态

核心行为规范统一维护在根目录 [AGENT.md](../AGENT.md)，本目录暂不拆分，避免双源维护。
当某段提示词稳定复用时，再沉淀到本目录。

## 红线

- 提示词中**禁止**写入用户真实个人信息
- 提示词只能包含方法论、输出格式、规则约束
