# Changelog

本项目的所有重要变更将记录在此文件中。

## v0.1.1 (2026-09-08)

### Changed

- **架构重构：产品仓库与个人简历库物理分离**
  - 个人简历数据（个人信息、教育、实习、项目、技能、证书、自我评价、照片、用户偏好）全部迁移至仓库外 `../简历库/`
  - 产品仓库新增 `src/ prompts/ skills/ workflows/ docs/` 目录结构
  - 新增 [docs/architecture.md](docs/architecture.md) 说明分离架构
  - 重写 .gitignore：忽略数据目录与个人照片，模板/文档设计资源可入库
  - AGENT.md 新增「数据与 Git 管理规则」章节，自检清单新增「数据隔离」项
  - Git 提交类型移除 resume/jd（个人数据不入 Git），保留 feat/update/fix/style/docs
- **重建 Git 历史**：初版曾误将个人数据提交入库，本次重建仓库确保个人数据从未进入任何提交

## v0.1.0 (2026-09-08)

### Added

- Resume Agent 项目初始化
- 简历资产库分类规范（个人信息/教育/经历/项目/技能/证书/自我评价）
- JD 管理与文件规范（YYYY-MM-DD_公司_岗位.md）
- JD 结构化分析规范（工作职责/任职要求/关键词/岗位能力模型）
- 匹配分析规范（Strong/Partial/Gap/Transferable + 突出/弱化/删除/补充）
- 模板系统（template_01 稳重正式 / template_02 极简科技 占位配置）
- 定向简历生成规范（resume.md + generation_notes.md）
- 用户偏好与设计风格配置规范
- 三层内容体系（事实层 / 专业表达层 / 岗位定制层）
- 完成后自检清单
- 核心文档：README.md / PRD.md / AGENT.md

### Not Included

- 自动网申
- 自动投递
- 招聘网站自动化
