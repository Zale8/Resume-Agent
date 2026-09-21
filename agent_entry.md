# Resume-Agent 执行手册（agent\_entry.md）

> 本文件是新 Agent 会话的**自包含入口**：读完它 + AGENT.md 即可开始工作，不依赖对话历史。
> 与具体任务冲突时，以 [AGENT.md](AGENT.md) 为最高优先级。

## 0. 30 秒上手

1. **体检**（零依赖）：
   ```bash
   python gen.py doctor
   ```
   通过 = Python 版本、仓库结构、简历库发现、python-docx 生成依赖全部就绪。
   （本机若 `python` 不可用，使用已安装 python-docx 的解释器全路径调用。）
2. **看简历库**：`../简历库/`（仓库外，个人数据，禁止入 Git）。
3. **生成简历的方式（v0.7 起）**：产品**没有模板库**，但有**范式 Preset + DesignSpec
   装配层 + 三种骨架**。Agent 先确定本份 **Design Decision**（设计决策），经
   `assemble_job_spec` 装配成 DesignSpec 并校验后渲染（**推荐路径**，见第 5 节）；
   旧「直接选骨架 + 色板」路径保留兼容。仅当范式未覆盖全新版式时才写一次性脚本，
   用户定稿确认后自动删除（AGENT.md §十三）。
4. **任何时候不确定边界**：查 [AGENT.md](AGENT.md)（红线/目录/流程/自检）。

***

## 1. 核心工作原则

### 1.1 红线与目录

详见 [AGENT.md §一\~§三](AGENT.md)。核心要点：

- **事实优先、可根据JD内容合理优化**：基于简历库真实资产进行调整优化，缺失信息标「待补充」
- **数据隔离**：个人数据只在仓库外 `简历库/`，仓库内零真实信息
- **动态排版**：不使用固定模板，按岗位 + 设计偏好生成 DOCX
- **三类经历分开**：`02_实习经历` / `03_项目经历` / `04_校园经历` 不混放
- **目录完整规范**：`00_个人信息` \~ `14_JD结构化分析` + `99_配置`，详见 AGENT.md §三

### 1.2 匹配分析口径

必须输出 **Strong / Partial / Gap / Transferable** 四类 + **突出 / 弱化 / 删除 / 补充 / 待询问**策略，
不得以单一百分比替代。

### 1.3 时间口径（事实层约定）

- 教育、实习、项目：统一用**月份**（如 `2022.09-2026.06`），不写具体日期。
- 校园经历：用户真实担任过的职务/活动可按该职务常规职责专业化写满，
  时间统一模糊为「在校期间 / 任职期间」；仍禁止编造名次、数据、奖项、未发生的事件。
- 证书：不写取得时间。

### 1.4 简历板块规则

- **核心四板块优先顺序**：个人信息 → 教育经历 → 实习经历 → 项目经历。
- 专业技能、证书奖项为次要板块：可按 JD 调整位置/篇幅/合并（可并入技能板块）。
- 板块内部可按 JD 重排（最相关经历放最前）。
- 空间不足可删除与JD匹配度较低的信息，调整文字大小等方式（删除前需要询问是否删除或给出其他意见）
- 不设独立「自我评价」板块；优势特质精炼融入开头个人优势简介。

***

## 2. 简历内容层（resume.md）

每份简历先产出**内容层** `resume.md`（Agent 与用户确认内容用，也是动态生成脚本的数据输入），
再进入 DOCX 生成。resume.md 用通用章节 + 表格即可，**不再使用模板字段代码（NAME/W1C 等）**。

```markdown
# 简历内容：姓名 → 公司 - 岗位
> 生成日期：YYYY-MM-DD
> 数据来源：简历库（事实可追溯）

## 个人信息
| 项 | 值 | 来源 |
|---|---|---|
| 姓名 / 意向 / 电话 / 邮箱 / 城市 | … | 00、06 |

## 个人优势（开头简介，2-4 句）
…（来源 07 + 真实特质，不堆头衔）

## 教育经历
学校 / 学历 / 专业 / 时间 / 相关课程（来源 01）

## 实习经历（按 JD 相关性排序，每条：时间｜公司｜岗位 + STAR 要点）
…（来源 02）

## 项目经历（同上）
…（来源 03；课设按项目事实写，来源 04）

## 校园经历（岗位需要时才放）
…（来源 04）

## 专业技能 / 证书奖项（可合并；证书不写时间）
…（来源 05、08）

## 待补充（缺失但 JD 关注的信息，不写入成品）
- …
```

每条优化内容可在 generation\_notes.md 标注 Level 2/3 与依据。

***

## 3. 版式设计路由（选骨架，不是选模板）

根据岗位与用户偏好，先在对话层面确定**本份 Design Decision**（范式骨架、配色方向、
照片决策等，见第 5 节），再经 DesignSpec 装配后由生成脚本实现。
以下是已验证的三类范式（思路参考，每次重新设计，禁止换色冒充新版式）：

| 范式骨架    | 形态                                    | 适用                   |
| ------- | ------------------------------------- | -------------------- |
| 双栏侧边栏式  | 左窄栏（信息+照片+技能）/ 右宽栏经历，浅色块底             | 信息密度高、技能多的通用/技术岗     |
| 横幅工牌卡式  | 顶部深色 Header 横幅（姓名+信息+照片）+ 白卡板块 + 成果色条 | 单岗位精准投递、品牌感行业（医药/消费） |
| 单栏极简编辑风 | 纯白、1 字体族、黑+1 强调色、编号标题、量化数字前置          | 外企/大厂/ATS 严格场景       |

变体维度：布局、行业配色（科技深蓝/医药青绿/金融金棕/教育暖橙/制造钢灰）、
字体策略、照片形态、标题样式、成果展示、技能呈现。
最终以 `99_配置/style_preferences.md` 与用户当次要求为准。

***

## 4. 照片

- 照片只从 `简历库/00_个人信息/photos/` 读取，禁止用其他来源图片。
- 每份简历必须含照片，尺寸按版式裁剪合适（侧边栏近方形 / Header 竖版 / 小圆形均可）。
- ⚠️ **P3（单栏极简）范式例外需显式开启**：`build_p3_spec()` /
  `build_p3_compact_spec()` 的 `photo.enabled` 预设为 `False`（`photo_zone="none"`，
  Header 单列），因此 P3 简历要带照片必须在 Design Decision 里写
  `enabled=True`（浮动坐标另配）。**不要只挂 `floating`** —— Validator 会以
  「停用照片时不得单独启用浮动」判 ERROR 并拒绝渲染（详见 §5.1 第 5 步）。
- 无照片：提醒用户补充，不擅自用占位图。

***

## 5. DOCX 动态生成规范（v0.4 核心流程）

> 详细红线见 AGENT.md §十四。这里是执行步骤。
> v0.4 已沉淀**通用排版积木**（`layout_kit.py`）与**三种骨架**（`skeletons.py`）：
> 生成时必须复用它们，**禁止复制上一份公司的生成脚本只改颜色**。

### 5.1 执行步骤

> **Design Decision ≠ DesignSpec**（本节关键概念，2026-09-19 起；2026-09-21 修订）：
> - **Design Decision（本份设计决策）**：Agent 在生成前对「这一份简历怎么设计」做出的
>   判断，是**生成过程中的中间决策**。**必须每份落盘为 `design.json`**
>   （位于该份成品的 `09_岗位定制简历/公司/岗位/日期/` 目录内），
>   由 `gen.py build` 读取——**禁止套用上一份的 design.json**，禁止复用历史决策文件；
> - **DesignSpec**：Design Decision + 范式 Preset 经 `assemble_job_spec()` 正式装配、
>   经 `validate_spec()` 校验后的**结构化视觉事实源**，renderer 唯一认的设计输入；
> - User Facts / Resume Content / JD 分析 / style\_preferences / generation\_notes
>   **都不等于** DesignSpec。
>
> ⚠️ **为什么必须落盘**：旧规则（「对话内明确即可，不新建任何决策文件」）使设计决策
> 随会话结束即丢失，流程上唯一留存、且携带完整设计参数的实物只剩**上一份的临时脚本**
> ——这正是「总套用上一份」的制度性来源（见 `docs/architecture/audit_2026-09-21_root_cause.md` §R3）。
> 把决策落盘为机器可读的 `design.json`，既保留了「每份重新设计」，
> 又让「重新设计」有了可校验、可复现的载体。


1. **内容确认**：resume.md 与用户确认。
2. **确定 Design Decision**（本份设计决策）：
   - **输入**：JD 分析 + resume.md 内容 + `99_配置/style\_preferences.md`
     （风格输入 / 参考）+ 用户当次视觉要求 + 可用照片信息（有无、原图比例）
     + 单页/内容预算；
   - **输出（落盘为 `design.json`）**：范式（P1/P2/P3）、palette、**photo decision**
     （photo.enabled / floating / position_h / position_v / offset_x_cm /
     offset_y_cm / border.color / border.width_pt 中**需要覆盖**的项）、
     其他本份布局决策（边距 / 间距 / 密度调整等）；
   - **未明确的字段保持 Preset 默认语义**，不得为「填满字段」编造数值；
   - 骨架/色板只是**范式级**选择，**不等于完整的本份设计**；本份照片坐标、
     尺寸等具体参数只进 `design.json`，**禁止写入 Preset / 产品代码 / 全局配置**；
   - `design.json` **每份新建**：`gen.py build` 缺该文件直接拒绝，
     且**不会套用上一份**；`paradigm` / `design_intent` 为必填，
     `design_intent` 含 `【...】` / `待填` / `TODO` 等占位符会被拒绝（防敷衍式填模板）。
     生成前可用 `python gen.py build --write-design-template` 取空白模板参考字段全集。
3. **选择/加载对应 Preset**：按范式取 `design/presets.py` 的 `build_p1/p2/p3_spec()`
   作为基线（P1 ↔ banner\_card、P2 ↔ two\_column\_sidebar、P3 ↔ single\_column\_minimal）。
4. **组装** **`ResumeBlocks`**（**不进仓库**的一次性脚本/临时代码）：
   - `sys.path.insert(0, "<产品仓库>/src")` 复用 `resume_generator`；
   - 用 `data_loader` 或直接读 resume.md，把内容填入 `layout_kit.ResumeBlocks`；
   - **所有事实数据运行时从简历库读取**，公司/岗位/日期走 argv 参数；
   - **不得出现硬编码姓名、电话、经历**。
5. **装配 DesignSpec 并构建 DOCX**：

   **推荐路径（v0.9 起）——`gen.py build` 一键达标**：

   ```bash
   # 1) 先落盘本份 design.json（在成品目录，每份新建）
   python gen.py build --write-design-template        # 取空白模板参考
   # 2) 写好 design.json（含 paradigm / design_intent / palette / photo / 边距等）
   # 3) 一条命令：解析 resume.md → 校验 → auto-fit 收敛 → 八维 QA → 出 DOCX
   python gen.py build <成品目录>/resume.md --design <成品目录>/design.json \
          --out <成品目录>/姓名_公司_岗位.docx
   ```

   - `build` 内部走完整链路：`parse_resume_md` → `load_job_spec` → `fit()`。
     诊断有致命项 → 退出码 2；auto-fit 后仍不达标 → 退出码 1（除非 `--allow-overflow`）；
     达标 → 退出码 0。退出码可直接进脚本/CI 门禁。
   - **auto-fit 收敛梯**：间距 → 行距 → 边距 →（可选）字号，逐档递进有上限；
     字号档**默认关闭**（规范「绝不靠缩字号硬塞」），需显式 `--allow-font-reduction`。
     用尽仍不达标会**停下并给出归因**（提示删内容），绝不静默压字号。
   - **八维 QA 报告**（页数 / 溢出 / 末行位置 / 寡行 / 内容密度 / 边距安全区 /
     字号下限 / 照片变形）随命令输出——验收不再靠人肉翻页。
   - **兼容旧路径**（保留可用）：`build_document(blocks, skeleton_id, palette_id)`
     —— 先定骨架，再定色板；适合无本份级定制的快速生成。骨架 ID：
     `two_column_sidebar` / `banner_card` / `single_column_minimal`；色板 ID：
     `tech_navy` / `pharma_teal` / `finance_gold` / `education_warm` /
     `manufacturing_steel` / `minimal_ink`（不传则用骨架默认色板）；
     可用 `layout_kit.describe_kit()` 打印全部可选骨架与色板。

   **手工装配路径（当 `build` 不能表达本份某个视觉决策时使用）**：

   ```python
   from dataclasses import replace
   from resume_generator.design import (
       build_p3_spec, assemble_job_spec, validate_spec,
       PhotoFloating, PhotoBorder, Sourced)
   from resume_generator.skeletons import build_document

   base = build_p3_spec()                    # 1) 范式 Preset 基线（按范式选 p1/p2/p3）
   photo = replace(                          # 2) 本份 photo delta：只写 Decision
       base.photo,                           #    中明确覆盖的字段；未写的保持
       enabled=True,                         #    ⚠️ P3 Preset 默认关照片，必须显式开启
       floating=PhotoFloating(enabled=True), #    Preset 语义（不挂=内联旧行为；
       border=PhotoBorder(Sourced.kv1("<色值>"),   #  schema 默认补齐其余）
                          Sourced.kv1("<宽度>", "pt")))
   spec = assemble_job_spec(base, photo_delta=photo)   # 3) 装配（不可变）
   validate_spec(spec)                       # 4) 校验边界：不校验不渲染
   doc = build_document(blocks, design_spec=spec)      # 5) 渲染
   doc.save(out_path)                        # 6) 输出到 09 目录
   ```
   - 示例中 `<色值>` / `<宽度>` 为占位，**数值以当次 Design Decision 为准**，
     禁止把某一份的坐标/尺寸写进代码或文档示例；
   - `photo_delta` 用 `dataclasses.replace(base.photo, ...)` 构造；`floating` /
     `border` 不挂 = 保持旧行为（内联、无边框）；
   - ⚠️ **`photo_delta` 替换的是整份 `PhotoSpec`，不是「只补差量」**：
     `build_p3_spec()` / `build_p3_compact_spec()` 的预设是
     `photo.enabled=False`（`header.photo_zone="none"`，Header 走单列），
     所以**给 P3 加照片必须同时写 `enabled=True`**；只挂
     `floating=PhotoFloating(enabled=True)` 会被 Validator 判
     ERROR（`invalid_photo_floating`：「停用照片时不得单独启用浮动」）
     并由 `build_document()` 抛出 `ValueError` 拒绝渲染。
     P1 / P2 Preset 预设 `enabled=True`，只挂 `floating` 即可。
   - **不允许绕过 `validate_spec`**；`build_document(design_spec=...)` 内部会再次
     校验，ERROR 直接拒绝渲染；
   - 走手工装配路径时，页数收敛请改用 `resume_generator.fitting.fit()`
     （与 `gen.py build` 同一引擎），**不要再手写后处理收紧间距**。
6. **输出**：`简历库/09_岗位定制简历/公司/岗位/日期/姓名_公司_岗位.docx`。
7. **单页与八维 QA**（v0.9 起由 `gen.py build` 的 auto-fit **自动完成**）：
   - 走 `build` 路径时：收敛过程与八维 QA 报告随命令输出；退出码 0 即达标，
     退出码 1 表示用尽收敛梯仍不达标（报告会归因，通常指向「需删内容」）。
   - 走手工路径时：Word/WPS COM `doc.ComputeStatistics(2)` 读真实页数
     （或用 `resume_generator.fitting.measure_pages()`，同一口径）：
     - \= 1 → 通过；
     - \> 1 → 用 `resume_generator.fitting.fit()` 收敛，**不要再手写后处理收紧间距**；
     - 无 Word 时用 `python scripts/check_pages.py 成品.docx` 估算，再请用户目视确认。
   - **禁止**为凑页数缩字号到 9pt 以下或虚报数据。
8. **视觉确认**：无头浏览器截 HTML 预览，或请用户打开 docx 确认配色/照片/分页。
9. **写 generation\_notes.md**（生成后 **Record**）：公司/岗位、JD、实际采用的设计与
   参数（骨架/配色/字体/照片处理）、选取与删除的内容、优化逻辑、实测页数、
   待补充项、人工调整及原因。generation\_notes 是**结果记录，不是决策输入**——
   下一次生成的设计输入是**当次新建的 `design.json`**（不机器读取上一份 notes、
   也不复用上一份 `design.json`）。
10. **临时脚本处置**：用户定稿确认该版简历后，自动删除临时脚本（不询问、不要求用户清理）；
   用户要求继续调整时保留脚本迭代；确认仓库内无残留。
   （走 `gen.py build` 路径时通常无需临时脚本，即无此步。）

### 5.1.1 什么时候可以不只用骨架

三种骨架是**已验证的起点**，不是必须照搬的模板。以下情况才编写一次性 python-docx 脚本：

- 需要骨架未覆盖的**全新版式**（如时间轴、双栏非对称、卡片矩阵）；
- 用户明确指定了与三种骨架都不同的结构。

即使如此，仍应尽量复用 `layout_kit` 的原语（`setup_a4` / `set_run_font` /
`insert_photo` / 色板等），**禁止自建一套与积木并行的样式系统**。
该脚本在用户定稿确认后自动删除（§5.1 第 10 步 / AGENT.md §十三）；
未定稿期间保留用于排版迭代。

**临时脚本边界（适用于所有一次性脚本）——临时脚本是执行器，不是设计系统**：

- ✅ 可以：读取本份输入、组装 `ResumeBlocks`、调用 `assemble_job_spec()` 等正式装配
  接口、调用 `build_document()`、做 COM 页数 QA；
- ❌ 不可以：自行重新实现照片浮动等 DesignSpec 已具备的能力、绕过 Validator 直接
  操作底层 DOCX XML、把本份照片坐标 / offset / 尺寸写入 Preset 或产品代码、
  创建第二套设计配置系统。

### 5.1.2 Golden Sample（视觉回归基准，2026-09-19 登记）

`简历库/09_岗位定制简历/` 下封存有一份 **Golden Sample**
（同目录含只读封存 DOCX、视觉规范、人工修改 Change Log 与 8 条验收规则）。

定位与边界：

- ✅ **只读视觉回归基准**：生成完成、准备交付**之前**用它校验视觉结果
  （页数、末行阈值、分割线、照片处理等验收规则见其 §三）。
- ✅ **产品级规则的存档处**：其「产品化分级」记录了已确认的实现规则
  （如分割线用 pBdr 段落底边框实现、照片段禁止 exact 行距）。
  **只查「规则」，不取「参数」**——它的配色值 / 照片尺寸 / 页边距 / 浮动坐标
  是**那一份的 Design Decision**，对其它任何一份都不是规范。
- ⛔ **禁止在生成之前打开它**，不得把它的视觉参数作为本份设计的起点
  （与 AGENT.md §六 第 7 条「不读取上一份 notes」同一原则）。
- ❌ **不属于** Resume Content，**不属于** User Facts，**不是模板**，**不是母版**，
  **不作为个人事实数据源**——内容一律仍从简历库事实层读取。
- 禁止照抄 Golden Sample 复刻成新模板/母版（母版体系已于 v0.6 退役，见 AGENT.md §三）。

数据流位置：Golden Sample 只在 **QA/验收侧** 作为对照基准，
不进入 `User Facts → Resume Content → DesignSpec → Skeleton → Layout Engine → DOCX` 生成链路。

### 5.2 版式硬约束（生成时逐条满足）

- A4 严格 1 页；基本信息在首行/顶部；照片尺寸合适；合适的背景/强调色。
- 中文字体使用用户机器已装字体；字号层级清晰（正文通常 9.5–12pt）。
- 不缩字号硬塞内容；不靠虚报数据撑篇幅。
- **先定骨架再定色板，版式组件按岗位重新组合**；换色不算新设计。

### 5.3 自测（写积木相关代码后）

```bash
python tests/smoke_layout_kit.py   # 用虚构人物验证三种骨架能产出 DOCX（需 python-docx）
```

### 5.4 诚实说明能力边界

- v0.9 起「一键达标」有机制保障：`gen.py build` 内部完成解析、校验、auto-fit 收敛
  与八维 QA，**多数情况下首轮即达标、无需手工后处理**（已有一份复合定制版实测首轮达标）。
- 但机制不保证「内容永远装得下」：auto-fit 用尽收敛梯仍不达标时会**停下并归因**，
  通常意味着**内容确实过多**（需删减），而非排版参数没调好。此时应反馈用户做内容取舍。
- 页数以 Word COM 实测为准；无 Word 时用估算器并说明口径；最终以用户目视确认为准。
- 历史 DOCX / 历史 `design.json` **都不是模板、不是数据源**；
  需要同类版式时**新建本份 `design.json`** 走 `gen.py build`，不复制上一份。

***

## 6. 典型路由

| 用户说         | Agent 做                                                |
| ----------- | ------------------------------------------------------ |
| 「记录一个项目/实习」 | 存入 `03_项目经历/` 或 `02_实习经历/`，事实层口径                       |
| 「这是 JD」     | 存 `11_岗位JD/` → ① 结构化（14）→ ② 匹配分析（13）                   |
| 「我匹配吗」      | 读 JD + 全库资产 → Strong/Partial/Gap/Transferable 报告       |
| 「生成简历」      | resume.md 内容层 → 确认 → 新建 `design.json` → `gen.py build` 一键达标 → 交付（无临时脚本） |
| 「换个风格/太丑」   | 更新本份 `design.json` 重新 `build`；事实层不动                        |
| 「改个电话/学校」   | 重要事实：先确认 → 订正事实层 → 重新 `build`                              |
| 「检查产品」      | `python gen.py doctor` / `python gen.py check-library` |

***

## 7. 运维命令

```bash
python gen.py doctor            # 环境 / 路径 / 简历库 / python-docx 依赖体检（含积木就位检查）
python gen.py check-library     # 11/14/13/09 四阶段产物一致性校验
python scripts/check_pages.py <docx路径>   # 无 Word 时的页数估算（需 python-docx）
python tests/smoke_layout_kit.py           # 验证三种骨架可产出 DOCX（虚构数据，需 python-docx）
python tests/check_privacy.py   # 提交前隐私审计（工作区+全部历史）
```

***

## 8. 产物与文件纪律

- 每次输出目录：`简历库/09_岗位定制简历/公司/岗位/日期/`，含
  `resume.md`、`generation_notes.md`、`姓名_公司_岗位.docx`。
- 最终版确认前，不在输出目录生成 preview/ 预览 PDF/PNG（用户偏好）。
- DOCX/PDF 是**最终输出**，不反向解析、不作为下次输入。
- 仓库内禁止保留公司特定脚本；产品代码只有通用模块与工具。

### 产品仓库结构

```
Resume-Agent/
├── gen.py                 # 运维 CLI（doctor / check-library）
├── AGENT.md               # 最高规范
├── agent_entry.md         # 本文件
├── PRD.md  README.md  CHANGELOG.md
├── src/resume_generator/  # paths 路径发现 + data_loader 只读解析
│                         # + layout_kit 排版积木 + skeletons 三种骨架
├── prompts/               # jd_analyst / matcher / expression_optimizer / resume_writer
├── scripts/check_pages.py # 通用页数估算
├── skills/ workflows/ docs/ tests/   # tests 含 smoke_layout_kit.py
```

***

## 9. 完成后自检

详见 [AGENT.md §九](AGENT.md)（唯一权威版本，12 项清单）。汇报时注明「自检：N/12 通过」。
