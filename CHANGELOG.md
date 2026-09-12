# Changelog

本项目的所有重要变更将记录在此文件中。

## v0.2.5 (2026-09-12) — 身份审计修正

### Fixed

- **审计漏报历史中的个人邮箱**：`--show-identity` 原先只读 `git config user.email`
  （当前配置），而**不是历史中实际使用过的身份**，因此漏报了历史里真实存在的
  个人邮箱。配置读取与历史读取是两件事，必须分开检查。
  现改为扫描 `git log --format=%an/%ae/%cn/%ce` 汇总全部历史身份，
  再与当前配置分别报告

### Added

- `tests/check_privacy.py --show-identity`：查看历史身份 + 当前配置 + 远程状态，
  并给出「只改后续提交」与「连历史一起清除」两种处理方式

### 说明（本仓库当前的身份状况）

| 范围 | 身份 |
|---|---|
| 历史中 12 个提交（用户原有） | 个人邮箱（具体值见 `python tests/check_privacy.py --show-identity`） |
| 本次改造新增的提交 | `Resume-Agent <resume-agent@localhost>` |
| 本地配置（后续新提交将继承） | `Resume-Agent <resume-agent@localhost>` |

> 本文档刻意**不写出**该个人邮箱的具体值 —— 把真实邮箱写进产品仓库，
> 本身就是一次泄漏（本条目第一版就犯了这个错，被审计抓出后修正）。

**决定：保留历史身份不变。** 理由：
1. 本仓库**从未配置远程**，仅本地使用，无公开暴露风险；
2. 保留原始作者身份是对用户署名的尊重，且这些提交本就是用户本人所做；
3. 清除历史需再次重写全部哈希，收益（本地仓库里的邮箱）小于代价；
4. 本地配置已改为非个人邮箱，**后续新提交不会带上它**；
5. 若将来要推送公开远程，届时报 `git config user.email "你的用户名@users.noreply.github.com"` 即可。

## v0.2.4 (2026-09-12) — 仓库整理

### Added

- `.gitattributes`：仓库内统一存 LF、检出转 CRLF，二进制文件（docx/png/jpg/pdf）
  禁止换行转换。消除 Windows 上反复出现的 `LF will be replaced by CRLF` 警告
  与虚假 diff

### Changed

- 产品仓库整理完毕：**工作区干净，16 个提交，5.91 MB**
- 确认零依赖可用后清理了冗余的手工依赖包（`pypdf` + `pymupdf`，57 MB）——
  核心代码完全不 import 它们，全局环境也已具备，删掉不影响任何功能
- 清理旧 Git 历史备份（含个人信息的 15 MB `.git` 快照）

### Fixed

- `check_privacy.py --install-hook` 的提示补充了受限环境说明：
  Git 钩子需 `sh`，无法创建命名管道时会直接失败导致无法提交，
  此时应改用 `python commit.py`

## v0.2.3 (2026-09-12)

### Fixed

- **照片未被写入产物（严重，静默失败）**：`replace_photo()` 会把图片部件改名为
  证件照的真实格式（如占位图 `image1.png` → 证件照 `image1.jpeg`），但
  `write_zip()` 是按 `order` 列表遍历写出的，改名后**新名字不在 order 中**，
  于是照片部件根本没被写进 zip —— 而关系文件 `document.xml.rels` 仍指向它。
  后果：产物**照片直接消失**，严重时 Word 报文件损坏。
  - 修复：改名时同步更新 `order`（原地替换那个位置）
  - 双保险：`write_zip()` 现在会发现「entries 里有、order 里没有」的部件并
    **追加写出**，而不是静默丢弃
- **照片替换报告名与实际产物不一致**：`replace_photo()` 返回的是改名前的旧部件名，
  调用方拿报告去读产物会 `KeyError`（把「替换成功」误报成失败）。现返回产物中
  真实存在的名字

### Added

- **`tests/smoke_docx_engine.py` 新增包完整性校验** `_check_package_integrity()`：
  逐个解析所有 `.rels`，验证每个关系目标（含 `../` 相对路径规范化后）
  都真实存在于 zip 中。这是「产物能否被 Word/WPS 正常打开」的核心判据
- **照片替换改为走完整 render 链路验证**（此前只单测 `replace_photo()`，
  因此漏掉了上述两个缺陷）；并断言写入的字节与输入证件照完全一致

### 说明

本次缺陷由**可选工具** `scripts/check_pages.py`（依赖 python-docx）暴露：
它打开产物时报 `KeyError: word/media/image1.jpeg`。这印证了保留该可选工具的价值
——零依赖的主链路给结论，可选工具做交叉验证。

## v0.2.2 (2026-09-12)

> 主题：**数据隔离的可靠化 + 跨用户通用性的可验证化**。
> 起因：复查发现「个人数据已删除」并不等于「历史里没有」——历史与文档示例中
> 仍留有真实姓名、公司名、学校名。

### Fixed（安全）

- **Git 历史中的个人数据（严重）**：即便工作区已清理，以下内容仍留在历史中：
  - `scripts/reprocess_templates.py`（11 个提交）含测试手机号与邮箱
  - `templates/template_05/template_config.md`（8 个提交）含**真实姓名**
  - `scripts/gen_xiaomi_resume_docx.py` / `gen_gree_resume_docx.py` 含真实公司名
  - **提交信息正文**含真实姓名
  - → **重建 Git 历史**：保留全部 12 个提交、提交时间、提交信息与全部产品文件，
    仅丢弃上述 4 个含个人数据的文件路径，并对提交正文脱敏
- **文档与代码中的真实实体名**：`agent_entry.md` / `gen.py` / `README.md` /
  `resume_map.py` 的示例里混入了真实公司名与学校名（违反 `docs/architecture.md`
  「文档示例一律使用虚构人物」的既有规范）。全部改为虚构值（某科技公司 / 某虚构大学）
- **测试文件硬编码真实信息**：`smoke_other_user.py` 曾把真实姓名/学校/公司名
  写成「禁用词」——这本身就是泄漏。改为从仓库外的
  `简历库/99_配置/privacy_terms.txt` 读取

### Added

- **`tests/check_privacy.py` — 数据隔离审计**（AGENT.md §九 第 6 项的可执行版本）
  - 覆盖：工作区（含未跟踪）、**全部提交历史**、提交信息正文、
    被忽略但存在的文件、提交作者身份
  - 强标识：手机号 / 邮箱 / 身份证 / 银行卡 + 仓库外自定义敏感词清单
  - 词表解析带防护：剥离 markdown 标记、丢弃过长或含标点的说明行（避免误报淹没真问题）
  - `--install-hook` 可安装 pre-commit 守卫
- **`commit.py` — 零依赖提交入口**：先审计后提交，通过才落盘。
  不依赖 `sh`，规避了 Windows 上 Git 钩子因 `couldn't create signal pipe` 失败的问题
- **`tests/smoke_other_user.py` — 跨用户通用性验证**：在临时目录另建一套完全虚构的
  简历库（目录名故意不叫「简历库」，路径与产品仓库无关），验证
  「换人 / 换位置 / 不改代码」能否跑通，并逐项比对产物不含真实用户信息
- **`简历库/99_配置/privacy_terms.txt`**（仓库外）：真实姓名/学校/公司名清单，
  供审计精确匹配。放在仓库外是刻意的——写进仓库本身就是泄漏

### Changed

- `docs/architecture.md` 新增「六、数据隔离的可执行验证」与「七、跨用户通用性验证」，
  并把「历史教训」拆分为「数据隔离」与「依赖可移植性」两组；
  原「确保个人数据从未存在于任何 Git 提交中」的不实陈述已更正为真实经过
- `docs/architecture.md` 新增「当前可移植性保证」表，列出每项保证对应的验证命令
- `AGENT.md` §九 第 6 项自检明确指向可执行审计命令，而非仅靠人工看 `git status`

### Removed

- 从未被跟踪的临时探针与调试脚本

## v0.2.1 (2026-09-12)

> 主题：**把「自动生成简历」这一条链路做扎实**。MVP 明确不包含自动投递。

### Added

- **`generation_notes.md` 自动生成**：`gen.py render` 现在自动产出生成说明（此前靠 AI 手写、经常漏，
  而 AGENT.md 要求产物目录必须有）。记录内容全部是**机器可验证的事实**：
  - 模板槽位用量（`模板 2 个槽位 / resume.md 提供 4 条`）
  - **未进入模板的内容**（槽位不足被丢弃的条目，逐条列出并带公司/岗位/时间）
  - 留空的模板字段、简历库补齐明细
  - 版式检查：补高标记清理、照片替换、窄槽位超出、缩字号、溢出估算
  - `resume.md` 的 sha256 内容指纹
  - 「六、AI 优化说明」「七、真实性自检」两节留白，明确标注需 AI 填写
  - 已有人工/AI 写过这两节时不覆盖，改写为 `generation_notes.auto.md`
- **`MapReport` 映射诊断**：`resume_map.py` 显式追踪「模板槽位 vs 实际内容量」，
  暴露此前被**静默丢弃**的内容（如 template_02 只有 2 段实习槽位，而简历库有 4 段实习）
- **姓名自动识别**：从 `resume.md` 的 H1 解析姓名，文件名自动为 `{姓名}_{公司}_{岗位}.docx`，
  无需每次手动传 `--name`
- **`--jd` 校验**：检查 JD 文件存在性与内容长度（过短时提醒），并记入生成说明。
  JD 不参与字段填充，但它是整条链路的输入起点，缺失应被显式发现
- **归档目录复用**：产物优先落在 **`resume.md` 所在目录**（`base_dir`），
  与内容层放在一起形成「改字段 → 重渲 → 对比」闭环；仅在没有 `--resume` 时才
  用 `09_岗位定制简历/{公司}/{岗位}/{日期}/`。修复了此前会另建日期目录、
  导致同一岗位产物散落的问题（`find_resume_base()` 保留作无 resume.md 时的兜底）
- **覆盖提示**：输出文件已存在时提醒将覆盖上一版；`--force` 可消除提示
- 新增参数 `--no-notes`、`--force`

### Fixed

- **校园经历角色解析错误**：`_split_role_from_org` 在分隔符两侧**都含职务词**时
  （如「校园学生会部长 / 自律会主席」）会把两段都判为角色，导致组织位返空、
  角色位保留整串（宽度 27，塞进窄槽位会挤成两行）。
  现正确拆为组织「校园学生会」+ 角色「部长」
- **行内角色串过长**：新增 `_condense_role()`，超长并列职务只保留首个职务；
  修复后 `C1P` 超出倍数从 3.38× 降到不再超出
- **技能项未去空白**：分类行 `**AI与大模型**：ChatGPT / Claude` 切分后残留
  全角空格（`'ChatGPT '`），现统一 strip
- **证书槽位统计自相矛盾**：`--supplement` 补齐证书发生在槽位统计之后，
  导致报告显示「证书提供 0 项」而实际已填入 3 项。现按补齐后的最终值刷新统计
- **溢出判断大量误报**：此前用「占位符标记 + 其后空格」估算槽位容量，
  再套一个写死的「单页 50 行 / 每行 46 字符」。对 `{{MAJ}}` 这类只留几个字符的
  标记完全不可靠，导致把正常的整行字段误判为超宽。现改为：
  - 从 `w:sectPr` 读取**真实页面尺寸与页边距**（`PageGeometry`），
    不再写死 A4 与 50 行
  - 用**该行自己的字号**（`w:sz`）判断行宽是否溢出，而不是全文中位数字号
  - 区分「流式文本换行（设计如此）」与「行内槽位换行（破坏版式）」
  - 新增 `MIN_OVERFLOW_WIDTH` 过滤只右移几像素的轻微超出
- **整行溢出的字段归属错误**：曾在填充后二次扫描并靠文本匹配猜字段，
  导致一行列出所有同长度值的字段。现改为在填充阶段精确记录每个文本节点
  实际替换了哪些字段
- 「下一步」提示编号在条件分支下跳号（1、2、4）

### Changed

- `agent_entry.md` §3 工作流标注「⑦⑧ 是循环而非终点」：看到内容被丢弃警告应回到 ⑥ 重排后重渲
- `agent_entry.md` §5 新增两条解析约束：**顺序即优先级**、**长角色名会被压缩**
- `agent_entry.md` §6 补充工具自动完成事项与四类警告的处理方式
- `README.md` 补充渲染时自动完成的事、会主动警告的四类问题
- 明确 MVP 范围为「只做自动生成简历」，自动投递移出 MVP
- 新增回归测试 `tests/smoke_resume_map.py`（75 项断言），
  覆盖组织/角色拆分、角色压缩、占位文本过滤、章节解析、槽位丢弃报告、
  三级降级策略、生成说明产出——这些启发式规则此前无任何测试保护

## v0.2.0 (2026-09-12)

### Added

- **统一 CLI 入口 `gen.py`**：`doctor` / `list-templates` / `standardize` / `render` 四个子命令
- **渲染层实现（v0.1 缺失的关键环节）**：`resume.md` → DOCX 成品的完整链路
  - `src/resume_generator/paths.py` — 跨平台路径自动发现（命令行参数 > 环境变量 > 逐级向上查找）
  - `src/resume_generator/docx_engine.py` — 零依赖 DOCX 填充引擎
    - 空格对齐槽位保持（`Slot`）：防止「公司名变长导致职位左移」的版式错位
    - `mc:Choice` / `mc:Fallback` 双分支同步替换
    - t01 品红（FF00FF）`<w:br/>` 补高 run 自动清理
    - 照片替换（自动识别占位图，默认只替换最小位图以防误伤图标）
    - 单页溢出估算（剔除 Fallback 重复内容后统计文字量）
    - 窄槽位 vs 流式文本区分：仅窄槽位允许有限度缩字号（下限 8pt）
  - `src/resume_generator/resume_map.py` — `resume.md` → 模板字段映射（三级降级：字段 JSON > 内嵌字段表 > 章节结构解析）
  - `src/resume_generator/template_kit.py` — 把用户上传的任意 docx 标准化为可用模板
- **`agent_entry.md`**：自包含通用主提示词，任意 AI 加载即用（含模板/风格路由表、resume.md 格式规范、11 项自检清单、环境约束）
- **模板路由表**：按 JD 公司风格动态选型（§4）
- **`--supplement`**：用简历库事实层补齐 resume.md 漏写的客观字段（联系方式/证书），不覆盖已有值、不补经历描述、补齐明细逐条打印
- **回归测试 `tests/smoke_docx_engine.py`**：对全部模板验证字段发现/填充/双分支一致性/照片替换/溢出估算
- **`templates/template_06/` 补全元数据**：此前只有 `template.docx`，缺 `template.json` / `field_mapping.md` /
  `template_config.md`（`list-templates` 显示为「未命名」）。现由 `gen.py standardize` 生成完整配置
- `scripts/README.md`、`src/README.md` 说明文档

### Changed

- **零依赖化**：渲染链路只用 Python 3.8+ 标准库，不再需要 `pip install`、Word/WPS/LibreOffice、`pywin32`、`python-docx`
- **零绝对路径化**：`docs/architecture.md` 目录拓扑改用占位符；简历库路径全部自动发现
- `AGENT.md` 新增**§十四 渲染层实现规范**（禁止 AI 直接改 DOCX 二进制、禁止 Windows 专有依赖、必须保持空格对齐槽位、不得为塞内容缩字号）
- `AGENT.md §九` 自检清单统一为 **11 项**（修正 §十二「第 10 项」、§十三「第 11 项」、`workflows/README` 「8 项清单」的编号冲突）
- `README.md` 更新为 v0.2 快速开始与命令行速查
- `workflows/README.md` 修正各工作流指向的 AGENT.md 章节号（原指向 §二~§八，与实际 §一~§十四 不符）
- `.gitignore` 补充 `_output/`、`*.fields.json` 等产物规则

### Removed

- `scripts/render_templates.py`（硬编码 `C:\Users\...\Desktop` + 扫描桌面目录名 + 依赖 Word COM / pymupdf）
- `scripts/gen_template_configs.py`（硬编码绝对路径，功能由 `gen.py standardize` 取代）
- `scripts/reprocess_templates.py`（硬编码绝对路径，依赖 lxml / PIL，功能由 `gen.py standardize` 取代）
- 空目录 `templates/template_05/`（内容此前已移除，仅剩空壳）

> 上述脚本记录的两个关键机制已继承进 `docx_engine.py` 并有回归测试覆盖：
> ① 空格对齐槽位必须保持宽度；② t01 品红补高 run 必须在填充前删除。

### Fixed

- 渲染链路此前**完全断裂**：`AGENT.md` 与 `generation_notes.md` 引用的
  `gen_xiaomi_resume_docx.py` 已在 `cccbe20` 被 revert，仓库内没有任何脚本能把
  `resume.md` 填进 `template.docx`。本版本补齐该环节。
- `data_loader.py` 的 `load_personal_data` 此前无任何调用方（死代码），现由 `--supplement` 使用

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
