# Changelog

本项目的所有重要变更将记录在此文件中。

## v0.4 (2026-09-13) — 沉淀通用排版积木与三种骨架

> 起因：v0.3 删除模板库后，每份简历由 Agent 编写一次性脚本动态生成。
> 实践发现：脚本里重复了大量页面/字体/色板/照片/间距的样板代码，
> 且容易「复制上一份公司脚本只改 RGB」。本版本把**通用、与公司无关**
> 的排版原语与已验证的三种骨架沉淀为产品代码。

### Added

- **`src/resume_generator/layout_kit.py`** — 通用排版积木：
  - `ResumeBlocks` / `BulletBlock` 内容数据结构（由调用方从简历库填入，本模块不读个人文件）
  - 页面/字体/间距原语：`setup_a4` / `set_run_font` / `set_paragraph_spacing` /
    `add_text` / `add_hairline` / `shade_cell` / `set_cell_margins` / `clear_table_borders` /
    `insert_photo`
  - 六套行业色板 `PALETTES`（tech_navy / pharma_teal / finance_gold /
    education_warm / manufacturing_steel / minimal_ink）
  - `count_pages_com()`（Word COM 实测页数）、`describe_kit()`（列出可选骨架与色板）
  - `MIN_BODY_PT = 9` 正文下限；未安装 python-docx 时仍可 import（色板/元数据可用）
- **`src/resume_generator/skeletons.py`** — 三种已验证骨架：
  `build_document(blocks, skeleton_id, palette_id)`，分别实现
  双栏侧边栏式 / 横幅工牌卡式 / 单栏极简编辑风
- **`tests/smoke_layout_kit.py`** — 用虚构人物（张三）验证三种骨架可产出 DOCX（需 python-docx）

### Changed

- **`agent_entry.md §5` 重写**：明确「先选骨架、再选色板」，
  给出 `build_document(...)` 调用示例、骨架/色板 ID 清单，
  以及「什么时候才允许编写一次性脚本」（仅骨架未覆盖的全新版式）；
  一次性脚本仍须尽量复用 layout_kit 原语，用后即删
- **`gen.py doctor`**：检测 `layout_kit.py` / `skeletons.py` 是否就位；
  docstring 与结论文案改为「选定骨架 + layout_kit 动态构建」
- **版本统一为 v0.4**：README / PRD / src/README / architecture 等由「v0.3 当前版本」
  更新为「v0.4 当前版本」，v0.4 由「未来规划」改为「已实现」
- `prompts/resume_writer.md` 的「与 DOCX 动态生成的衔接」改为复用积木 + 骨架

### 说明（骨架 ≠ 模板）

骨架只提供**布局思路与通用组件**，配色/字体/组件必须按本次岗位重新组合。
「旧骨架换色冒充新设计」被明确禁止（见 layout_kit 顶部与 agent_entry §5.2）。
产品仓库仍**不含任何成品版式或公司特定脚本**。

## v0.3 (2026-09-13) — 删除模板库，简历由 Agent 动态生成

> 起因（用户明确决策）：「把 templates 删掉，以后不要从里面挑选模板生成了，自行生成。」
> 体检产品时发现：5 份成品简历只有 1 份走 `gen.py render`，最满意的单栏极简 /
> 横幅工牌卡版式均为 Agent 临时脚本动态排版产出；固定模板真实渲染还会丢弃技能字段、
> 留空字段、估算超页。模板路线与实际生产脱节且无法复现满意版式。

### Removed（破坏性变更）

- **删除整个 `templates/` 模板库**（5 套模板；Git 历史可恢复）
- 删除模板渲染流水线：`src/resume_generator/docx_engine.py`、`resume_map.py`、`template_kit.py`
- 删除 3 个配套测试：`smoke_docx_engine.py`、`smoke_resume_map.py`、`smoke_other_user.py`
- `gen.py` 移除 `render` / `standardize` / `list-templates` 三个子命令
- `.gitignore` 移除 templates 下 docx/png 的入库例外（产品内不再有任何 docx）

### Changed

- **生成方式改为动态排版**：每份简历由 Agent 编写一次性 python-docx 脚本直接构建
  （布局/配色/字体/照片全部代码生成），数据运行时从简历库读取、不硬编码，
  Word COM 实测 1 页，确认后删除临时脚本（AGENT.md §十三/§十四 重写）
- `gen.py doctor` 新增 python-docx / pywin32 可用性检测；CLI 本身仍零依赖
- `paths.py` 产品根判定不再依赖 templates/ 目录
- 自检清单从 11 项扩为 **12 项**（新增「单页与照片」，临时脚本条目更新）
- 全面重写文档：AGENT.md / agent_entry.md / README.md / PRD.md /
  architecture.md / resume_writer.md / src/README.md / scripts/README.md
- resume.md 内容层不再使用模板字段代码（NAME/W1C 等），改为通用章节结构

## v0.2.7 (2026-09-13) — JD 产物分目录

> 起因：用户发现 `13_JD分析/` 下同时出现两个名字只差后缀的文件，
> 误以为重复生成。实为两个阶段的产物，但**命名相近 + 目录混放**导致难以分辨。

### Changed

- **拆分目录，职责分离**（用户建议）：
  | 目录 | 内容 |
  |---|---|
  | `14_JD结构化分析/` | ① JD 要什么（与候选人无关，**可复用于同岗位多次投递**） |
  | `13_JD分析/` | ② 这个人与岗位的关系（匹配分析） |
  | `11_岗位JD/` | JD 原文 |
  | `09_岗位定制简历/` | 成品 DOCX |
- 迁移 `14_JD结构化分析/` 下已存在的结构化分析文件（从 `13_JD分析/` 移出）
- 同步更新 13 个文件中的路径引用（AGENT.md / agent_entry.md / PRD.md /
  README.md / architecture.md / 4 个 prompts / gen.py / 简历库 README）

### Fixed

- **`AGENT.md §七` 未定义 JD 分析产物的文件名**：只写了「结果存至
  13_JD分析/」，是本次困惑的根因。现补全两阶段命名表与「为什么不能合并」
  的理由（合并会导致「岗位事实」与「个人判断」混写，且 ① 无法复用）
- **`AGENT.md §三` 表格里的编号错误**：`09_简历母版` 与实际目录 `10_简历母版`
  不符（历史上曾与 `09_岗位定制简历` 撞号），已修正并加注
- **`gen.py` 的 `check-library` 有拼接错误**：注释与 `has_docx = False`
  被合并到同一行，导致该分支逻辑失效。整段重写为数据驱动的阶段表
- **`doctor` 未识别 `10_简历母版` / `12_投递记录` / `14_JD结构化分析`**：
  期望目录清单已补全为 16 项

### Added

- `check-library` 升级为**四阶段校验**（JD原文 / 结构化分析 / 匹配分析 / 成品 DOCX），
  输出一览表 + 缺失项 + 修复建议
- 成品检测放宽匹配：JD 文件名里的岗位名常与实际投递岗位不同
  （JD 叫「招聘简章」，实际投「库管员」），改为按公司目录查找

### 待办

- 3 个历史岗位缺 `14_JD结构化分析/` 下的独立结构化分析。它们的匹配分析里
  已含岗位结构化内容，但结构与规范不统一，且缺独立的「岗位能力模型」7 维表。
  是否补齐待用户决定（具体岗位见 `python gen.py check-library`）。

## v0.2.6 (2026-09-13) — 真实用例暴露的渲染缺陷

> 触发：用一份此前从未渲染过的真实简历（内联字段表格式）做端到端测试，
> 结果只映射到 15/32 字段，且文件名叫成了文档标题。**渲染层此前从未在这种
> 格式上验证过** —— 之前只测了「散文式章节」那一种写法。

### Fixed

- **内联字段表跨章节提取失败（严重）**：`extract_inline_fields()` 只在
  `## 模板字段` / `## 字段映射` 标题下扫描表格。但真实 resume.md 常把字段表
  分散写在 `## 个人信息` / `## 教育经历` / `## 技能` 各章节里
  （可读性更好），导致**提取到 0 项**，渲染器退回章节解析后 32 个字段
  只填上 15 个。
  现改为：**只要表格首列是大写字段名**就提取，与所在章节无关。
  该用例字段数从 0 → 33 项，最终映射 15/32 → 30/32
- **H1 姓名解析被文档标题污染**：H1 为
  `# 简历内容：<姓名> → <公司> - <岗位>`（而非 `<姓名> - <岗位>`）时，
  旧实现把整串当姓名，产出文件名为
  `简历内容：<姓名> → <公司> - <岗位>_<公司>_<岗位>.docx`。
  新增 `_split_title()` / `_looks_like_name()`：识别文档标题前缀、
  按箭号切分、校验姓名形态；拆不出时返回 None 而不是硬塞整串。
  同时 `gen.py` 增加「姓名从简历库 00_个人信息 兜底」与明确提示
- **L2 与 L3 被写成二选一**：原逻辑 `if not values:` 表示「有内联字段表就
  不解析章节」。但内联表常只写部分字段（个人信息 + 教育），其余 17 个字段
  白白空着。现改为**始终执行两者并互补**（L1 > L2 > L3，后者只补缺）

### Added

- **静默丢弃检测**：内容层写了字段、但当前模板没有对应位置时，此前会
  **静默丢弃**。真实案例：resume.md 声明 `SK1/SK2/SK3`，而 `template_02`
  根本没有技能字段，三个技能无声消失。现在会列出被丢弃的键**及其原值**，
  并给出「换模板」或「并入已有字段」的处理建议
- `MapReport.unknown_fields` / `unknown_values` 记录该情况，
  并写入 `*.fields.json` 供复查
- 回归测试新增 15 项断言（`### 3b 内联字段表跨章节提取`、
  `### 3c H1 姓名解析`），总数 75 → 90

### Fixed（数据隔离）

- **测试白名单里放入真实手机号**：`check_privacy.py` 的「通用测试号码」白名单
  曾被加入用户的真实手机号，还配了段辩解它「无害」的注释 —— 这等于让审计
  对自己的泄漏失明。已移除，并把红线写进代码注释
- **测试注释里写入真实姓名**：`smoke_resume_map.py` 的回归用例说明中直接写了
  真实姓名，被审计抓出。已改为泛指
- 上述泄漏曾进入 5 个提交的历史，已**重建历史清除**（仓库无远程，无外部影响）；
  `smoke_other_user.py` 的第 4 项检查也改为只校验**真实用户**敏感词，
  不再把虚构测试数据误判为泄漏

## v0.2.5 (2026-09-13) — 身份审计修正

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

## v0.2.4 (2026-09-13) — 仓库整理

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

## v0.2.3 (2026-09-13)

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
