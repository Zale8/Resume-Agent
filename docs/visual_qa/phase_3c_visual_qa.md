# Phase 3C Visual QA

## Baseline

| Test Suite    | Result   |
| ------------- | -------- |
| Component     | 22/22    |
| Typography    | 9/9      |
| Palette       | 8/8      |
| Spacing       | 10/10    |
| Stability     | 8/8      |
| DesignSpec    | 8/8      |
| DataLoader    | 32/32    |
| **Total**     | **97/97**|
| Smoke P1      | 37983    |
| Smoke P2      | 37933    |
| Smoke P3      | 37974    |
| Doctor        | PASS     |
| Privacy       | PASS     |

基线完整，未发生变化，可继续 Visual QA。

---

## QA 样本

5 份 DOCX 全部生成成功（虚构人物「林知远」，不入库，输出在 `temp/visual_qa/output/`）：

| Label              | 路径                      | Paradigm              | Bytes |
| ------------------ | ------------------------- | --------------------- | ----- |
| P1_legacy_banner   | banner_card + tech_navy   | (旧路径)              | 39695 |
| P2_legacy_sidebar  | two_column_sidebar + manufacturing_steel | (旧路径)  | 39691 |
| P3_legacy_minimal  | single_column_minimal + minimal_ink     | (旧路径)  | 39647 |
| P1_spec_banner     | build_p1_spec()           | p1_banner_single      | 39681 |
| P2_spec_sidebar    | build_p2_spec()           | p2_sidebar_two_column | 39687 |

由于 Visual QA 无法真正「看」DOCX 视觉，采用 **XML 结构检查**替代肉眼观察：
逐项核对段落顺序 / `w:jc`（对齐）/ `w:spacing`（段前段后行距）/ `w:color` /
`w:pBdr`（边框 sz+color）/ `w:tabs`（制表位）/ `w:drawing`（图片节点）/
`w:shd`（单元格底纹），覆盖用户文档第五~十二节的全部视觉维度。

---

# P1 Banner

## Issue 001

### Observation

P1_spec_banner 内容密度明显过松：bullet 段后 6pt（=120 twips，legacy 路径仅 1.5pt=30 twips），
正文行距 1.9 倍（=456 twips，legacy 路径约 1.08 倍=259 twips），section 标题段前 22pt
（=440 twips，legacy 路径 5pt=100 twips）。

### Classification

**B. DesignSpec / Preset 问题**

### Evidence

XML 对比（P1_spec_banner vs P1_legacy_banner，段落 [16] 第一条 bullet）：

- P1_spec：`sp={'before':'0','after':'120','line':'456','lineRule':'auto'}`
- P1_legacy：`sp={'before':'0','after':'30','line':'259','lineRule':'auto'}`

Spec 路径段 [6] section title：
- P1_spec：`sp={'before':'440','after':'20'}`
- P1_legacy：`sp={'before':'100','after':'20'}`

### Expected

Spec 路径应保持与 legacy 路径相近的内容密度，避免同等内容溢出多页。

### Current

Spec 路径内容密度过松，单页承载能力明显下降。**仅密度问题，非结构错误**。

### Action

**Defer**

### Reason

Renderer 正确执行了 `bullet_spacing_after=6pt` / `line_spacing=1.9` /
`section.spacing_before=22pt` 三个 Spec 参数，链路通畅，无 A 类 Bug。
问题在 Preset 取值偏大，未来阶段调 `build_p1_spec()` 即可。

---

## Issue 002

### Observation

P1_spec_banner 头部 header 深色块底色 `#252525`，与 legacy 路径 `tech_navy` 色板的
`#1B3A4B` 视觉差异较大；on_dark_secondary=`#BBBBBB`，contact 文字灰度偏高。

### Classification

**B. DesignSpec / Preset 问题**

### Evidence

XML 段 [0]（姓名）：
- P1_spec：`colors={'FFFFFF'} shade='#252525'`
- P1_legacy：`colors={'FFFFFF'} shade='#1B3A4B'`

Spec 的 `colors.dark_block.value='#252525'` vs legacy 走 `tech_navy` Palette 的 header `#1B3A4B`。

### Expected

深色 header 应保持足够对比度与行业气质（tech_navy 偏蓝），而非纯灰。

### Current

Spec 路径 header 偏中性灰，丢失行业色板特征。

### Action

**Defer**

### Reason

颜色角色映射正确（`dark_block` → header 底，`on_dark_primary` → 姓名），无角色错位。
仅 Spec 的颜色取值与行业色板不一致，属 Preset 问题。

---

# P2 Sidebar

## Issue 003

### Observation

P2_spec_sidebar 姓名 `#2C3E50` 字号 **26pt**（=52 half-pt），明显过大。
P2_legacy_sidebar 姓名 `#2C3E50` 仅 **14pt**（=28 half-pt），相差近一倍。

### Classification

**B. DesignSpec / Preset 问题**

### Evidence

XML 段 [1]（姓名）：
- P2_spec：`sp={'before':'160','after':'40'} colors={'2C3E50'} sizes={'52'}`
- P2_legacy：`sp={'before':'160','after':'40'} colors={'2C3E50'} sizes={'28'}`

### Expected

姓名字号应与侧栏宽度匹配，26pt 在窄侧栏内会与照片、联系方式挤压。

### Current

字号过大，但布局结构未溢出（侧栏宽度足够）。

### Action

**Defer**

### Reason

`TypographySpec.name_size=26pt` 由 Spec 显式提供，Renderer 正确消费。属 Preset 取值问题，
需在 `build_p2_spec()` 中调小 name_size。无 A 类 Bug。

---

## Issue 004

### Observation

P2_spec_sidebar 的 sidebar bullet 段后 8pt（=160 twips），legacy 路径仅 1pt（=20 twips）；
行距 1.4 倍（=336 twips）vs legacy 1.05 倍（=252 twips）。整体密度比 legacy 松约 4-8 倍。

### Classification

**B. DesignSpec / Preset 问题**

### Evidence

XML 段 [7]（sidebar 第一条技能 bullet）：
- P2_spec：`sp={'before':'0','after':'160','line':'336','lineRule':'auto'}`
- P2_legacy：`sp={'before':'0','after':'20','line':'252','lineRule':'auto'}`

### Expected

Spec 路径应与 legacy 保持相近密度，避免 sidebar 内容被挤压到主栏。

### Current

Sidebar 内容密度过松，但表格结构未破坏。

### Action

**Defer**

### Reason

`bullet_spacing_after=8pt` 与 `line_spacing=1.4` 均由 Spec 提供，Renderer 正确执行。属 Preset 问题。

---

## Issue 005

### Observation

P2 legacy 路径 sidebar bullets 字号 **17pt**，主栏 bullets 字号 **19pt**，
同语义 bullet 字号不对称。

### Classification

**D. Template Geometry**

### Evidence

XML 段 [7]（sidebar bullet）：`sizes={'17'}`
XML 段 [23]（main bullet）：`sizes={'19'}`

### Expected

同语义 bullet 应保持字号一致，或在 DesignSpec 中显式声明两栏不同字号。

### Current

字号不对称，但这是 `build_sidebar` 的设计选择（侧栏更窄→更小字号）。

### Action

**Defer**

### Reason

属 Skeleton Geometry 决策，非 Renderer Bug。若需统一，应改 Skeleton Profile 或在
DesignSpec 增加侧栏字号字段（当前 Schema 无此角色 = Schema Gap）。

---

## Issue 006

### Observation

P2_spec_sidebar 声明 `photo.display_shape="circle"`，但实际产出仍为矩形照片
（fallback 盒）。Renderer 未实现真正圆形裁切。

### Classification

**C. Capability Gap**

### Evidence

XML 段 [0] `[DRAWING]` 节点存在，但 `pic:blipFill` 内无 `a:srcRect` 圆形裁切标记。
Spec 的 `fallback.width=3.2cm / height=4.0cm` 盒尺寸正确生效。

### Expected

圆形裁切照片（视觉上裁为圆）。

### Current

矩形 fallback 盒，Spec 期望的 circle 形态未实现。

### Action

**Defer**

### Reason

3B-4 已登记为 Capability Gap #1：DOCX 圆形裁切需 `a:srcRect` + `a:fill` 椭圆遮罩，
当前 `layout_kit.insert_photo` 未实现。本阶段禁止为「视觉更好看」改 Renderer。

---

# P3 Minimal

## Issue 007

### Observation

P3_legacy_minimal 的 role_separator 为 **两个空格 `"  "`**，而 P1 Banner 用 `"｜"`、
P2 Sidebar 用 `"  ·  "`。三种骨架的角色分隔符不一致。

### Classification

**D. Template Geometry**

### Evidence

XML 段 [15]（实习条目）：
- P3_legacy：`text='某虚构科技公司  AI 产品实习生2025.07-2025.09'`（仅两空格分隔）

render_style.py 的 `SKELETON_DEFAULT_STYLE[SKELETON_MINIMAL].components.role_separator="  "`
为 Profile 显式登记值。

### Expected

Minimal 风格用纯空格分隔是设计意图（极简无符号），但应在 DesignSpec 中显式声明。

### Current

Separator 视觉为空格，与 P1/P2 不一致。属设计选择，非 Bug。

### Action

**Defer**

### Reason

Profile 已显式登记 `"  "`，Renderer 正确消费。属 Template Geometry 设计决策。

---

## Issue 008

### Observation

P3_legacy_minimal 编号 section title `01  个人优势` 中，编号 `01` 用 accent 色
`#C0392B`，文字 `个人优势` 用 ink `#111111`，两 run 同段不同色，层次清晰。

### Classification

**无问题**（仅记录确认）

### Evidence

XML 段 [6]：`colors={'C0392B','111111'} sizes={'24'} text='01  个人优势'`

### Expected

编号与文字色彩对比，符合 minimal 风格设计意图。

### Current

✅ 正确生效，无异常。

### Action

无

### Reason

确认 Typography 层级与 Component 编号模板正常工作。

---

# Capability Gaps

引用 Phase 3B-4 已登记的能力缺口，本次 QA 仅复核未新增：

1. **真圆形裁切照片**：P2 Spec 声明 `circle` 形态，实际仍走 rect fallback 盒
   （Issue 006）。需 `layout_kit.insert_photo` 增加 `a:srcRect` + 椭圆遮罩支持。

2. **Bullet marker 独立着色 / 悬挂缩进**：当前 bullet symbol 与正文同 run 同色，
   无法单独为 marker 着色或实现悬挂缩进。`RenderComponents.bullet_symbol` 只控制字符，
   未控制 marker run 拆分。

3. **Tag chip 边框 / 填充 / padding**：`RenderComponents` 无 tag 结构参数，
   Tag 当前仅作为 bullet 文本输出。

4. **ContactBlock 图标 / label-value 结构**：`RenderComponents` 无 contact icon 资源
   与 label/value 拆分参数，contact_lines 仍为单字符串拼接。

5. **AchievementBanner 零实现**：`RenderComponents` 无 banner 结构参数，
   Renderer 未实现该组件。Spec 中如出现 banner 字段会走 fallback。

6. **icon_hairline 图标集资源缺口 #3**：3B-4 已登记，本阶段未触发。

---

# Deferred

1. **P1_spec / P2_spec Preset 取值过松**（Issue 001/004）：
   `bullet_spacing_after` / `line_spacing` / `section.spacing_before` 在
   `build_p1_spec()` / `build_p2_spec()` 中偏大，需后续阶段统一调参。
   属 B 类，不在 Phase 3C 修复范围。

2. **P2_spec name_size=26pt 过大**（Issue 003）：
   需在 `build_p2_spec()` 中调小 name_size 至 14-18pt 范围。
   属 B 类。

3. **P1_spec header 颜色与行业色板不一致**（Issue 002）：
   `colors.dark_block='#252525'` 偏中性灰，丢失 tech_navy 行业特征。
   属 B 类，需调 `build_p1_spec()` 的 ColorSpec。

4. **P2 sidebar bullet 字号不对称**（Issue 005）：
   sidebar 17pt vs main 19pt，需在 DesignSpec 增加侧栏字号角色或统一字号。
   属 D 类 + Schema Gap。

5. **P3 minimal role_separator 空格**（Issue 007）：
   属 Template Geometry 设计选择，若需统一可在 DesignSpec 显式声明。
   属 D 类。

6. **所有 Capability Gap**（1-6 项）：
   禁止在 Phase 3C 修复，需在后续能力扩展阶段实现。

---

# Parameter Control Map

| Visual Element     | Parameter                | Owner File              | Owner Layer     |
| ------------------ | ------------------------ | ----------------------- | --------------- |
| 字体大小            | TypographySpec.body_size / name_size / etc | render_style.py | Typography |
| 字体粗细            | TypographySpec.*_weight  | render_style.py         | Typography      |
| 字体族              | font_family / _FONT_TOKEN_MAP | render_style.py   | Typography      |
| 行距                | TypographySpec.line_spacing | render_style.py     | Typography      |
| 颜色（ink/accent/muted/hairline/dark_block/on_dark_*/light_sidebar） | ColorSpec.* | render_style.py | Palette |
| Sidebar heading 色 | sidebar_heading（Schema Gap） | render_style.py    | Palette         |
| Section 标题段前    | SectionSpec.spacing_before | render_style.py       | Spacing         |
| Section → 首行间距  | SectionSpec.divider_to_first_line | render_style.py | Spacing         |
| Bullet 段后         | ExperienceSpec.bullet.spacing_after | render_style.py | Spacing       |
| 经历条目间距        | entry_before / entry_after | render_style.py       | Spacing         |
| Cell 内边距         | cell_left_cm / cell_right_cm | render_style.py     | Spacing         |
| Divider 厚度        | hairline_sz / bar_sz / side_label_sz | render_style.py | Spacing       |
| Section 标题符号    | section_title_symbol（▍） | render_style.py       | Components      |
| Section 编号模板    | title_numbering_template（%02d） | render_style.py | Components      |
| Role 分隔符         | role_separator（｜/·/空格） | render_style.py      | Components      |
| Bullet marker 字符  | bullet_symbol（·/•）     | render_style.py         | Components      |
| 日期定位模式        | date_mode（tab_stop/column） | render_style.py    | Components      |
| 日期 run 前缀       | date_prefix（\t）        | render_style.py         | Components      |
| 证书 label / 分隔   | cert_label / cert_separator | render_style.py     | Components      |
| 身份 / 联系 / 照片对齐 | identity_text_align / contact_align / photo_align | render_style.py | Components |
| 照片等比保护        | photo_preserve_aspect    | render_style.py         | Components      |
| 页面边距            | page.margins             | skeletons.py `_LAYOUT_CONFIG` + Spec override | Layout |
| 列宽比例            | col_ratios               | skeletons.py `_LAYOUT_CONFIG` | Layout          |
| 表格宽度            | usable_width             | skeletons.py `_resolve_layout`（单一来源） | Layout |
| 照片盒尺寸          | photo_box_cm             | skeletons.py `_LAYOUT_CONFIG` + Spec override | Layout |
| Sidebar heading 边框 | bottom border sz8        | skeletons.py `build_sidebar` | Component 实现  |
| Main section divider | bottom border sz6 / 空段落 | skeletons.py          | Component 实现  |
| Accent Bar（banner） | bar_sz / bar_before / bar_after | render_style.py + skeletons.py | Components + 实现 |
| 照片插入            | insert_photo()           | layout_kit.py           | DOCX 原语       |
| 照片裁切（circle）  | Capability Gap（未实现） | layout_kit.py（待扩展） | Capability      |
| 发丝线              | add_hairline()           | layout_kit.py           | DOCX 原语       |
| 右制表位            | add_right_tab_stop()     | layout_kit.py           | DOCX 原语       |
| 单元格底纹          | shade_cell()             | layout_kit.py           | DOCX 原语       |
| 单元格内边距        | set_cell_margins()       | layout_kit.py           | DOCX 原语       |
| 段落字体设置        | set_run_font()           | layout_kit.py           | DOCX 原语       |
| 页面 A4 设置        | setup_a4()               | layout_kit.py           | DOCX 原语       |

---

# 参数生效验证（第十三节）

按用户文档要求，分别改变 4 类参数验证链路通畅，**测完恢复默认**：

| 类别       | 改动                                  | 验证结果                                                   |
| ---------- | ------------------------------------- | ---------------------------------------------------------- |
| Typography | `body_size 9 → 14`                   | ✅ 字号集合从 `{16,18,19,21,23,39}` → `{16,18,19,21,23,28,39}` |
| Palette    | `accent → #00FF00`                    | ✅ 颜色集合新增 `00FF00`，移除 `E31937`                      |
| Spacing    | `section.spacing_before 22 → 40`     | ✅ section before twips `440 → 800`                          |
| Component  | `bullet.symbol · → ▶`                | ✅ 首条 bullet 文本前缀变化（· → ▶）                         |
| 恢复默认   | 重新 build_p1_spec()                  | ✅ 与 baseline 完全一致，无残留                              |

**结论**：DesignSpec → RenderStyle → Renderer → DOCX 链路完全通畅，4 类参数均能
在 DOCX XML 中观察到对应变化，且恢复后无残留。

---

# Final Result

**Visual QA: CONDITIONAL PASS**

理由：

1. **未发现 A 类 Renderer Bug**。所有 Spec 参数在 DOCX XML 中正确生效，
   日期右对齐、深色 header、照片插入、section title 符号、bullet marker、
   role 分隔符、编号模板、颜色角色映射全部正确。

2. **发现 5 个 B 类问题**（DesignSpec/Preset 取值偏松或偏大）：
   P1_spec / P2_spec 的 spacing / line_spacing / name_size / dark_block 颜色
   取值需要后续阶段在 `build_p1_spec()` / `build_p2_spec()` 中调整。
   **不在 Phase 3C 修复范围**。

3. **确认 2 个 D 类问题**（Template Geometry 设计选择）：
   P2 sidebar bullet 字号不对称、P3 minimal role_separator 用空格。
   属设计决策，非 Bug。

4. **6 项 Capability Gap 已登记**（3B-4 已记录，本次仅复核未新增）：
   圆形裁切 / bullet 独立着色 / Tag chip / ContactBlock 图标 /
   AchievementBanner / icon_hairline 资源。需后续能力扩展阶段实现。

5. **参数生效验证全通过**：4 类参数改变均能在 XML 中观察到对应变化，
   恢复默认后无残留。

6. **基线无回归**：97/97 测试通过，Smoke 三骨架字节完全一致（37983/37933/37974），
   Doctor / Privacy 通过。

**最终判断**：Phase 3C 建立了从视觉问题 → 参数 → 文件 → 模块 → 测试的可追踪链路，
未发现需要立即修复的 Renderer Bug。CONDITIONAL PASS —— 视觉问题已分类登记，
后续阶段按 Deferred 清单逐项处理。

---

# 最终验收问答

### Q1：P1 哪些问题属于 Renderer Bug？

**无**。P1 的两个问题（密度过松、header 颜色偏中性灰）均属 B 类 Spec/Preset 问题，
Renderer 正确执行了 Spec 提供的所有参数。

### Q2：P2 哪些问题只是 DesignSpec / Preset 问题？

- Issue 003：name_size=26pt 过大（Preset 取值）
- Issue 004：bullet after=8pt 偏大（Preset 取值）
- Issue 002（同 P1）：header 颜色偏中性灰（Preset 取值）

### Q3：P3 哪些问题属于 Component Capability Gap？

P3 本身无 Capability Gap 问题。但跨骨架通用的 Capability Gap（圆形裁切、bullet
独立着色等）在 P3 同样存在，已在 Capability Gaps 节统一登记。

### Q4：哪些问题现在不能修？

**全部 Deferred 项**：
- 6 项 Capability Gap（需能力扩展阶段）
- 5 项 B 类 Preset 问题（需调 `build_p1_spec()` / `build_p2_spec()`）
- 2 项 D 类 Template Geometry（需设计决策）

### Q5：如果我要调整某个视觉元素，我应该修改哪个文件？

参见 **Parameter Control Map** 节。简要导航：

| 我要改…            | 改哪里                                                       |
| ------------------- | ------------------------------------------------------------ |
| 字体大小/粗细/行距 | `render_style.py` Typography 段 + `TypographySpec` 字段      |
| 颜色                | `render_style.py` Palette 段 + `ColorSpec` 字段              |
| Section 间距        | `render_style.py` Spacing 段 + `SectionSpec.spacing_before`  |
| Bullet 段后         | `render_style.py` Spacing 段 + `ExperienceSpec.bullet`      |
| Bullet marker 字符  | `render_style.py` Components 段 + `BulletStyle.symbol`       |
| Role 分隔符         | `render_style.py` Components 段 + `RoleSpec.separator`      |
| 日期位置            | `render_style.py` Components 段（date_mode）+ `layout_kit.py`（add_right_tab_stop） |
| 照片盒尺寸          | `skeletons.py` `_LAYOUT_CONFIG` + `PhotoSpec.fallback`      |
| 照片裁切（circle）  | `layout_kit.py` `insert_photo`（**需扩展，当前 Capability Gap**） |
| 页面边距            | `skeletons.py` `_LAYOUT_CONFIG` + `PageSpec.margins`         |
| 列宽比例            | `skeletons.py` `_LAYOUT_CONFIG.col_ratios`                   |
| 模板结构            | `skeletons.py` `build_banner_card` / `build_minimal` / `build_sidebar` |
| 底层 DOCX 行为      | `layout_kit.py`（`insert_photo` / `add_hairline` / `setup_a4` 等） |

### Q6：修改后如何验证没有破坏旧模板？

按 Phase 3C 流程：

1. 跑 7 套件测试：`python -m unittest tests.test_renderer_component tests.test_renderer_typography tests.test_renderer_palette tests.test_renderer_spacing tests.test_renderer_stability tests.test_design_spec tests.test_data_loader`
2. 跑 Smoke：`python tests/smoke_layout_kit.py`
3. 跑 Doctor：`python gen.py doctor`
4. 跑 Privacy：`python tests/check_privacy.py`
5. 对比 Smoke 三骨架字节必须 **byte-perfect**：
   - P1 = 37983 / P2 = 37933 / P3 = 37974
6. 任何字节变化都必须 XML diff 定位原因，禁止更新 baseline 掩盖回归。
