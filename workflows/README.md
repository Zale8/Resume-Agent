# workflows/ — 工作流规范

> 本目录是 Resume Agent 的工作流方法论区，**可以进入 Git**。
> 内容是「流程与规则」，不含任何用户个人数据。
> **当前状态**：工作流逻辑集中在 AGENT.md 和 prompts/ 中，本目录暂为索引页。

## 核心工作流

| 工作流 | 规范位置 |
|---|---|
| 信息录入与分类 | [AGENT.md §三](../AGENT.md) 信息分类规则 |
| 简历内容三层体系（事实/表达/定制） | [AGENT.md §一](../AGENT.md) 第八条 / [AGENT.md §四](../AGENT.md) 第 18 条 |
| 数据与 Git 管理规则 | [AGENT.md §二](../AGENT.md) |
| JD 处理流程（保存→分析→能力模型） | [AGENT.md §七](../AGENT.md) |
| JD 匹配分析（Strong/Partial/Gap/Transferable） | [AGENT.md §七](../AGENT.md) |
| 定向简历生成（严格按序流程） | [AGENT.md §六](../AGENT.md) |
| 经历相关性分级（Highly Relevant → Irrelevant） | [AGENT.md §三](../AGENT.md) 第 13 条 |
| 设计风格系统（自然语言 → 结构化参数） | [AGENT.md §十一](../AGENT.md) |
| **DOCX 动态生成规范（内容 → DOCX）** | [AGENT.md §十四](../AGENT.md) + [agent_entry.md §5](../agent_entry.md) |
| 临时脚本管理（定稿确认后自动删除） | [AGENT.md §十三](../AGENT.md) |
| 完成后自检（12 项清单） | [AGENT.md §九](../AGENT.md) |

> 面向 AI 的可执行入口是 [agent_entry.md](../agent_entry.md)（自包含，无需读其他文件即可开工）。

## 后续规划

当工作流复杂到单文件难以维护时，按文件拆分到本目录：

```
workflows/
├── intake_workflow.md
├── jd_analysis_workflow.md
├── matching_workflow.md
├── resume_generation_workflow.md
└── style_workflow.md
```

拆分后 AGENT.md 只保留原则与索引，避免双源冲突。
