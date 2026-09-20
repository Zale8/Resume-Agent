# Resume Renderer 控制地图（Control Map）

> 本文档基于 Phase 3A/3B-1..3B-4/3C 完成态的真实代码审计，**唯一依据**为下列文件：
>
> - `src/resume_generator/render_style.py`（832 行）
> - `src/resume_generator/skeletons.py`（756 行）
> - `src/resume_generator/layout_kit.py`（527 行）
> - `src/resume_generator/design/spec.py` / `presets.py` / `validator.py` / `__init__.py`
> - `tests/test_renderer_{typography,palette,spacing,component,stability}.py` + `test_design_spec.py` + `test_data_loader.py` + `smoke_layout_kit.py` + `check_privacy.py`
> - `docs/visual_qa/phase_3c_visual_qa.md`
>
> **铁律**：禁止凭空虚构参数、文件、函数或控制关系。未定义就写 `未定义` / `Schema Gap` / `Capability Gap` / `需要进一步确认`。
> 本文档不修改 Renderer 代码，仅记录已有控制关系。

---

## 1. 总体架构图

依据实际代码审计修正（非机械复制）：

```text
DesignSpec (design/spec.py)
   │
   ↓  validate_spec()  (design/validator.py)
   │
   ↓  _build_from_spec()  (skeletons.py:154)
   │     ── PARADIGM_TO_SKELETON  (skeletons.py:73)
   │     ── 几何覆盖：RenderOverrides.margins_cm / photo_box_cm
   │
   ↓  resolve_style_for_spec()  (render_style.py:723)
   │     ── _num / _bold                → Typography 字段
   │     ── _resolve_colors_for_spec    → RenderPalette  (3B-2)
   │     ── _resolve_spacing_for_spec   → RenderSpacing  (3B-3)
   │     ── _resolve_components_for_spec→ RenderComponents (3B-4)
   │     ── resolve_font_family         → font_family
   │
   ↓  RenderStyle (frozen dataclass)
   │     ├── font_family / *_size / line_* / w_*
   │     ├── palette:   RenderPalette
   │     ├── spacing:   RenderSpacing
   │     └── components:RenderComponents
   │
   ↓  _resolve_context() (skeletons.py:101)  旧路径在此挂 Skeleton Default Palette
   ↓  _resolve_layout()  (skeletons.py:204)  几何单一来源
   │
   ↓  build_banner_card / build_minimal / build_sidebar  (skeletons.py)
   │     ── _section_title / _numbered_title / _main_title
   │     ── _add_experience_header / _experience_section / _experience_blocks_minimal / _experience_in_cell
   │     ── _body_bullet / _bullet_section
   │     ── _skills_certs / _side_label / _education
   │     ─  _apply_align / _bottom_border / _set_doc_default_font
   │
   ↓  layout_kit.py 原语
   │     setup_a4 / usable_width_cm / split_columns_cm / cell_text_width_cm
   │     add_right_tab_stop / add_hairline / shade_cell
   │     set_cell_margins / set_cell_width / set_table_fixed_layout / clear_table_borders
   │     set_run_font / set_paragraph_spacing / add_text / hex_rgb
   │     insert_photo / count_pages_com
   │
   ↓  DOCX
```

关键链路事实：

- **Spec 路径**先经 `validate_spec` 校验，再由 `_build_from_spec` 将范式映射到现有骨架（`PARADIGM_TO_SKELETON` 仅覆盖 `p1_banner_single`/`p2_sidebar_two_column`，P3 minimal 无对应范式 → 旧路径消费）。
- **几何覆盖**仅在 Spec 的四个边距都已确定时才覆盖 `_LAYOUT_CONFIG` 的 margins；照片在 `display_shape="circle"` 时按 `photo.fallback.width/height` 覆盖 photo_box，否则按 `photo.width/height`。
- **RenderStyle 是 Renderer 唯一可读的排版参数包**；`skeletons.py` 内禁止字号/字体/行距字面量（`MIN_BODY_PT` 是工程兜底常量，非视觉决策）。
- **Schema Gap / undetermined 字段**一律回退 `SKELETON_DEFAULT_STYLE[skeleton_id]` 并登记到 `RenderStyle.spec_fallbacks` 元组，供后续审计。
- **paper 角色**当前无渲染消费点（render_style.py:168 注释明示）。

---

## 2. 核心控制表

> 字段说明：
> - 控制参数：使用代码中的真实参数名（render_style.py / design/spec.py 字段）。
> - Owner Layer：Typography / Palette / Spacing / Components / Skeleton / Layout / Photo。
> - 影响模板：P1=banner_card / P2=two_column_sidebar / P3=single_column_minimal。
> - 对应测试：使用 `tests/` 下真实文件名 + 函数名缩写。
> - 状态：已控制 / Schema Gap / Capability Gap / Profile 固定 / Renderer 内部实现 / 需要进一步确认。

| 视觉元素                | 控制参数                                      | Owner Layer   | Owner File                       | Owner Function/Class                                  | 影响模板  | 对应测试                                                                                              | 状态              |
| ----------------------- | --------------------------------------------- | ------------- | -------------------------------- | ------------------------------------------------------ | --------- | ----------------------------------------------------------------------------------------------------- | ----------------- |
| 姓名字号                | `TypographySpec.name_size` → `RenderStyle.name_size`                | Typography    | render_style.py:805              | `resolve_style_for_spec` / `_num`                     | P1/P2     | test_renderer_typography.test_07_p1_spec_typography_applied / test_08_p2_spec_typography_and_fallbacks | 已控制            |
| 正文字号                | `TypographySpec.body_size` → `RenderStyle.body_size`                | Typography    | render_style.py:814              | `resolve_style_for_spec` / `_num`                     | P1/P2/P3  | test_renderer_typography.test_07 / test_08                                                             | 已控制            |
| 联系方式字号            | `TypographySpec.header_meta_sizes[0]` → `RenderStyle.contact_size`  | Typography    | render_style.py:745-750          | `resolve_style_for_spec`（P2 header_meta_sizes=None → Profile）| P1/P2     | test_renderer_typography.test_07 / test_08                                                             | 已控制（P1）/ Schema Gap（P2：header_meta_sizes=None，回退 Profile） |
| 意向字号                | `TypographySpec.intent_size` 无字段           | Typography    | render_style.py:740-742          | `resolve_style_for_spec`（显式 fb `typography.intent_size<spec_missing>`）| P1/P2/P3  | 无（intent_size 无 Spec 路径）                                                                        | Schema Gap        |
| 板块标题字号            | `TypographySpec.title_size` → `RenderStyle.title_size`              | Typography    | render_style.py:810              | `resolve_style_for_spec` / `_num`                     | P1/P2/P3  | test_renderer_typography.test_07 / test_08                                                             | 已控制            |
| 机构字号                | `TypographySpec.organization_size` → `RenderStyle.org_size`         | Typography    | render_style.py:811              | `resolve_style_for_spec` / `_num`                     | P1/P2     | test_renderer_typography.test_07 / test_08                                                             | 已控制            |
| 角色字号                | `TypographySpec.role_size` → `RenderStyle.role_size`               | Typography    | render_style.py:813              | `resolve_style_for_spec` / `_num`                     | P1/P2     | test_renderer_typography.test_07 / test_08                                                             | 已控制            |
| 元数据字号              | `TypographySpec.metadata_size` → `RenderStyle.meta_size`           | Typography    | render_style.py:815              | `resolve_style_for_spec` / `_num`                     | P1/P2     | test_renderer_typography.test_07 / test_08                                                             | 已控制            |
| 标签链字号              | `ExperienceSpec.tags.size` → `RenderStyle.tags_size`              | Typography    | render_style.py:752-757         | `resolve_style_for_spec`（P2 tags.enabled=False → 不渲染）| P1        | test_renderer_typography.test_07                                                                      | 已控制（P1）/ Profile 固定（P2 不渲染） |
| 侧栏分组标签字号        | `TypographySpec.sidebar_group_label_size` → `RenderStyle.side_label_size` | Typography | render_style.py:760-762         | `resolve_style_for_spec`                              | P2        | test_renderer_typography.test_08（P2 undetermined → Profile）                                       | Schema Gap（P2 sidebar_group_label_size undetermined） |
| 侧栏正文字号            | `TypographySpec.sidebar_body_size` → `RenderStyle.sidebar_body_size` | Typography    | render_style.py:763-764         | `resolve_style_for_spec`                              | P2        | test_renderer_typography.test_08                                                                     | 已控制            |
| 字体族                  | `TypographySpec.font_family` → `resolve_font_family` → `RenderStyle.font_family` | Typography | render_style.py:806              | `resolve_font_family` / `_FONT_TOKEN_MAP`            | P1/P2/P3  | test_renderer_typography.test_06_font_token_mapping                                                  | 已控制            |
| 字重                    | `TypographyWeights.{name,section_title,organization,role,sidebar_group_label}` → `RenderStyle.w_{name,title,org,role,side_label}` | Typography | render_style.py:778-790 | `_bold`                                               | P1/P2/P3  | test_renderer_typography.test_09_p2_role_undetermined_renders_bold                                    | 已控制（P2 role 可 undetermined → 回退 Profile） |
| 行距                    | `TypographySpec.line_spacing.{body,title,sidebar_body}` → `RenderStyle.line_{body,title,sidebar}` | Typography | render_style.py:767-775         | `resolve_style_for_spec`                              | P1/P2/P3  | test_renderer_typography.test_07 / test_08                                                             | 已控制（P2 sidebar_body=None 时 line_sidebar=line_body） |
| 主色                    | `ColorSpec.accent` → `RenderPalette.accent`                          | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1/P2/P3  | test_renderer_palette.test_02_p1_spec_colors_reach_renderer_and_xml / test_03_p2_spec_colors_reach_renderer_and_xml | 已控制            |
| 正文文字颜色            | `ColorSpec.ink` → `RenderPalette.ink`                                | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1/P2/P3  | test_renderer_palette.test_02 / test_03                                                               | 已控制            |
| 次要文字颜色            | `ColorSpec.muted` → `RenderPalette.muted`                            | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1/P2/P3  | test_renderer_palette.test_02 / test_03                                                               | 已控制            |
| Banner 深块底色         | `ColorSpec.dark_block` → `RenderPalette.dark_block`                  | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1        | test_renderer_palette.test_02_p1_spec_colors_reach_renderer_and_xml                                  | 已控制（P2 dark_block=None → 不消费） |
| Banner 深块上的姓名色    | `ColorSpec.on_dark_primary` → `RenderPalette.on_dark_primary`        | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1        | test_renderer_palette.test_02                                                                         | 已控制            |
| Banner 深块上的联系方式色| `ColorSpec.on_dark_secondary` → `RenderPalette.on_dark_secondary`     | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1        | test_renderer_palette.test_02                                                                         | 已控制            |
| Banner 深块上的意向色     | `ColorSpec.on_dark_tertiary` → `RenderPalette.on_dark_tertiary`      | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1        | test_renderer_palette.test_02                                                                         | 已控制（P1 observed，非 v1 通用 token） |
| Sidebar 浅底色           | `ColorSpec.light_sidebar` → `RenderPalette.light_sidebar`           | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P2        | test_renderer_palette.test_03                                                                         | 已控制            |
| Sidebar 分组标签文字色    | `sidebar_heading`（ColorSpec 无对应角色）                            | Palette       | render_style.py:163-166         | `_resolve_colors_for_spec`（fb `colors.sidebar_heading<schema_gap>`）| P2        | test_renderer_palette.test_04_missing_color_falls_back_with_log / test_05                            | Schema Gap（永远 Profile，禁止新增 Schema） |
| 发丝线颜色                | `ColorSpec.hairline` → `RenderPalette.hairline`                      | Palette       | render_style.py:139-180         | `_resolve_colors_for_spec`                            | P1/P2/P3  | test_renderer_palette.test_02 / test_03                                                               | 已控制            |
| 纸张底色                  | `ColorSpec.paper` → `RenderPalette.paper`                            | Palette       | render_style.py:168-172         | `_resolve_colors_for_spec`                            | —         | 无（render_style.py:168 注释明示 paper 当前无渲染消费点）                                              | 需要进一步确认（透传备用，无消费点） |
| Section 段前              | `SectionSpec.spacing_before` → `RenderSpacing.section_before`       | Spacing       | render_style.py:247             | `_resolve_spacing_for_spec`                           | P1/P2/P3  | test_renderer_spacing.test_01_spec_spacing_resolves_to_renderstyle / test_04_xml_paragraph_spacing_matches_renderstyle | 已控制            |
| Section 标题 → 首行间距   | `SectionSpec.divider_to_first_line` → `RenderSpacing.hairline_after` | Spacing       | render_style.py:248            | `_resolve_spacing_for_spec`                           | P1/P2/P3  | test_renderer_spacing.test_01 / test_04                                                               | 已控制            |
| Divider 厚度              | `SectionSpec.divider.weight` → `RenderSpacing.hairline_sz`（×8 1/8pt）| Spacing       | render_style.py:249 / 316-347  | `_resolve_spacing_for_spec`（`_SPACING_EIGHTH_PT`）   | P1/P2/P3  | test_renderer_spacing.test_06_xml_divider_thickness_matches_renderstyle                              | 已控制            |
| Section 标题段后          | `RenderSpacing.title_after`（无 Spec 路径）                          | Spacing       | render_style.py:195            | `_resolve_spacing_for_spec`（fb `spacing.title_after<schema_gap>`）| P1/P2/P3  | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| 独立 divider 段前         | `RenderSpacing.hairline_before`（无 Spec 路径）                     | Spacing       | render_style.py:196            | 同上                                                  | P1/P3     | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| 经历条目前间距            | `ExperienceSpec.entry_spacing` → `RenderSpacing.entry_before`       | Spacing       | render_style.py:250            | `_resolve_spacing_for_spec`                           | P1/P2/P3  | test_renderer_spacing.test_01 / test_04                                                               | 已控制            |
| 经历条目段后              | `RenderSpacing.entry_after`（无 Spec 路径）                          | Spacing       | render_style.py:200            | `_resolve_spacing_for_spec`（fb `<schema_gap>`）     | P1/P2/P3  | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Bullet 段前               | `RenderSpacing.bullet_before`（无 Spec 路径）                        | Spacing       | render_style.py:201            | 同上                                                  | P1/P2/P3  | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Bullet 段后               | `ExperienceSpec.bullet_spacing_after` → `RenderSpacing.bullet_after`| Spacing       | render_style.py:251            | `_resolve_spacing_for_spec`                           | P1/P2/P3  | test_renderer_spacing.test_01 / test_04                                                               | 已控制            |
| Banner 身份区底部色条段前  | `RenderSpacing.bar_before`（无 Spec 路径）                           | Spacing       | render_style.py:223            | `_resolve_spacing_for_spec`（fb `<schema_gap>`）     | P1        | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Banner 身份区底部色条段后  | `RenderSpacing.bar_after`（无 Spec 路径）                            | Spacing       | render_style.py:224            | 同上                                                  | P1        | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Banner 身份区底部色条厚度  | `HeaderSpec.accent_line.height` → `RenderSpacing.bar_sz`（×8 1/8pt） | Spacing       | render_style.py:252-254        | `_resolve_spacing_for_spec`                           | P1        | test_renderer_spacing.test_06                                                                         | 已控制（accent_line.enabled=False 时取 None → Profile） |
| Minimal 身份区分隔线段前   | `RenderSpacing.rule_before`（永久 Profile）                          | Spacing       | render_style.py:227            | `_resolve_spacing_for_spec`（fb `<schema_gap>`）     | P3        | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Minimal 身份区分隔线厚度   | `RenderSpacing.rule_sz`（永久 Profile）                              | Spacing       | render_style.py:229            | 同上                                                  | P3        | test_renderer_spacing.test_06                                                                         | Schema Gap        |
| Sidebar 分组标签段前       | `RenderSpacing.side_label_before`（永久 Profile）                    | Spacing       | render_style.py:231            | 同上                                                  | P2        | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Sidebar 分组标签下边框厚度 | `RenderSpacing.side_label_sz`（永久 Profile）                        | Spacing       | render_style.py:233            | 同上                                                  | P2        | test_renderer_spacing.test_06                                                                         | Schema Gap        |
| Sidebar 非经历条目段后     | `RenderSpacing.sidebar_item_after`（永久 Profile）                   | Spacing       | render_style.py:235            | 同上                                                  | P2        | test_renderer_spacing.test_01                                                                         | Schema Gap        |
| Cell 左内边距              | `RenderSpacing.cell_left_cm`（永久 Profile）                         | Spacing       | render_style.py:239            | `_resolve_spacing_for_spec`（fb `<schema_gap>`）     | P1/P2     | test_renderer_spacing.test_05_xml_cell_margins_match_renderstyle                                       | Schema Gap        |
| Cell 右内边距              | `RenderSpacing.cell_right_cm`（永久 Profile）                        | Spacing       | render_style.py:240            | 同上                                                  | P1/P2     | test_renderer_spacing.test_05                                                                         | Schema Gap        |
| Bullet 符号                | `ExperienceSpec.bullet.symbol` → `RenderComponents.bullet_symbol`   | Components    | render_style.py:389            | `_resolve_components_for_spec`                        | P1/P2/P3  | test_renderer_component.test_08_bullet_prefix                                                         | 已控制            |
| Bullet 间距                | `RenderComponents.bullet_gap`（Spec 无对应字段）                      | Components    | render_style.py:363            | `_resolve_components_for_spec`（fb `<schema_gap>`）   | P1/P2/P3  | test_renderer_component.test_08                                                                       | Schema Gap        |
| Bullet marker 独立着色     | `BulletStyle.symbol_color_role` 未被 Renderer 消费                   | Components    | 未消费                          | `_resolve_components_for_spec` 未读取此字段            | P1/P2/P3  | 无                                                                                                    | Capability Gap（bullet 与正文同 run 同色） |
| Bullet hanging indent     | `ExperienceSpec.bullet_indent` 未被 Renderer 消费                     | Spacing       | 未消费                          | `_SPACING_SPEC_SOURCES` 无 `bullet_indent`             | P1/P2/P3  | 无                                                                                                    | Capability Gap（无悬挂缩进原语） |
| Section Title（符号式）   | `SectionSpec.prefix` → `RenderComponents.section_title_symbol` + `section_title_gap` | Components    | render_style.py:390 / 362-363  | `_resolve_components_for_spec`                        | P1/P2     | test_renderer_component.test_06_section_title_symbol_and_numbering                                     | 已控制            |
| Section Title（编号式）    | `RenderComponents.title_numbering_template` + `title_numbering_gap`（永久 Profile） | Components | render_style.py:365-366      | `_resolve_components_for_spec`（fb `<schema_gap>`）   | P3        | test_renderer_component.test_06                                                                       | Schema Gap        |
| Section Title（图标式）     | `SectionSpec.title_style="icon_hairline"` + `IconSpec.resource`（永久 undetermined） | Components | render_style.py:481-487       | `_resolve_components_for_spec`（fb `components.section_icon<capability_gap>`）| P2        | test_renderer_component.test_05c_p2_icon_title_capability_gap_registered | Capability Gap（无图标库，回退符号标题） |
| Divider（组件层）          | `add_hairline()`                                  | Components / Spacing | layout_kit.py:219 / skeletons.py:584-586 | `add_hairline(doc, color, before_pt, after_pt, sz)`   | P1/P3     | test_renderer_spacing.test_06 / test_renderer_component.test_11_accent_bar_bottom_border | 已控制（原语层） |
| Sidebar 标题下边框        | `_bottom_border()` 直接在标题段附加                          | Components    | skeletons.py:743              | `_main_title` / `_side_label`                         | P2        | test_renderer_component.test_11_accent_bar_bottom_border                                              | Renderer 内部实现（sz 由 `side_label_sz`/`hairline_sz` 决定） |
| 日期右对齐（制表位）       | `ExperienceSpec.date_alignment` → `RenderComponents.date_mode` → `add_right_tab_stop` | Components + Layout | render_style.py:393 / layout_kit.py:177 | `_resolve_components_for_spec` / `_add_experience_header` / `add_right_tab_stop` | P1/P2/P3 | test_renderer_component.test_07_experience_header_separator_and_date                                  | 已控制（`tab_stop`/`column` 当前共用右缘制表位） |
| 日期 run 前缀             | `RenderComponents.date_prefix`（永久 Profile，禁止空格推位置）       | Components    | render_style.py:370            | `_resolve_components_for_spec`（fb `<schema_gap>`）   | P1/P2/P3  | test_renderer_component.test_07                                                                       | Schema Gap        |
| 角色分隔符                 | `ExperienceSpec.role.separator` → `RenderComponents.role_separator` | Components    | render_style.py:391            | `_resolve_components_for_spec`                        | P1/P2/P3  | test_renderer_component.test_07_experience_header_separator_and_date                                 | 已控制（P3 minimal 默认两空格，Spec 未覆盖时沿用 Profile） |
| 证书 label                | `RenderComponents.cert_label`（永久 Profile）                        | Components    | render_style.py:375            | `_resolve_components_for_spec`（fb `<schema_gap>`）   | P1/P3     | test_renderer_component.test_13_cert_line_labels                                                      | Schema Gap        |
| 证书分隔符                 | `RenderComponents.cert_separator`（永久 Profile）                    | Components    | render_style.py:376            | 同上                                                  | P1/P3     | test_renderer_component.test_13                                                                       | Schema Gap        |
| Sidebar 分组标签大小写变换 | `RenderComponents.side_label_transform`（永久 Profile）              | Components    | render_style.py:378            | 同上                                                  | P2        | test_renderer_component.test_14_side_label_ascii_uppercase                                            | Schema Gap        |
| 身份文字对齐               | `HeaderSpec.identity_alignment` → `RenderComponents.identity_text_align`（复合字段） | Components | render_style.py:396-400 / 458-470 | `_resolve_components_for_spec`（复合字段一次解析 photo_align）| P1/P2/P3 | test_renderer_component.test_05_explicit_component_values / test_05b_identity_alignment_unknown_falls_back | 已控制            |
| 联系方式对齐               | `RenderComponents.contact_align`（永久 Profile）                     | Components    | render_style.py:381            | `_resolve_components_for_spec`（fb `<schema_gap>`）   | P1/P2/P3  | test_renderer_component.test_12_contact_block_plain_paragraphs                                        | Schema Gap        |
| 照片对齐                  | `HeaderSpec.identity_alignment` → `RenderComponents.photo_align`（复合字段） | Components | render_style.py:396-400 / 458-470 | 同上                                                  | P1/P2/P3  | test_renderer_component.test_05 / test_05b                                                            | 已控制            |
| 照片等比保护               | `PhotoSpec.distortion_allowed` → `RenderComponents.photo_preserve_aspect`（反值） | Components | render_style.py:473-478        | `_resolve_components_for_spec`                        | P1/P2/P3  | test_renderer_component.test_10_photo_insertion_and_missing_behavior                                  | 已控制            |
| Tag 行（能力标签链）        | `ExperienceSpec.tags.enabled/size/separator` → 走 `RenderStyle.tags_size` / `RenderSpacing.tags_*` | Components / Typography | skeletons.py:659-665 | `_experience_section`                                 | P1（P2 tags.enabled=False → 不渲染）| test_renderer_component.test_09_tag_is_plain_muted_text_line                                         | 已控制（仅 plain 文本，无 chip 边框/填充） |
| Tag chip 边框/填充        | 未定义                                       | Components    | 未定义                          | 无                                                    | —         | 无                                                                                                    | Capability Gap    |
| ContactBlock 图标          | 未定义                                       | Components    | 未定义                          | 无                                                    | —         | 无                                                                                                    | Capability Gap（contact_lines 仍为单字符串拼接） |
| AchievementBanner          | `AchievementSpec.enabled/maximum_count/height` Spec 中存在，但 `RenderComponents` 无 banner 结构槽位 | Components | spec.py:379-388 | `_resolve_components_for_spec` 不读取 AchievementSpec | —         | 无                                                                                                    | Capability Gap（零渲染实现，Spec 出现 banner 字段会走 fallback 不渲染） |
| 页面边距（margins）        | `PageSpec.margins.{top,bottom,left,right}`（四值全确定时覆盖 _LAYOUT_CONFIG） | Layout / Skeleton | skeletons.py:174-177 | `_build_from_spec` / `_resolve_layout`               | P1（P2 bleed undetermined → 不覆盖）| test_design_spec / smoke_layout_kit                                                                  | 已控制（P1）/ Schema Gap（P2 bleed undetermined） |
| 页面 bleed                 | `PageSpec.bleed`（P1=0.0；P2 undetermined）                           | Layout        | spec.py:249                    | `_build_from_spec` 不读 bleed                          | P2        | test_design_spec                                                                                      | Schema Gap（缺口 #2） |
| 列宽比例（col_ratios）     | `_LAYOUT_CONFIG[skeleton_id]["col_ratios"]`（Spec 路径不覆盖）       | Skeleton      | skeletons.py:54-70            | `_resolve_layout` / `split_columns_cm`                | P1/P2/P3  | smoke_layout_kit / test_renderer_stability                                                            | Profile 固定（Spec 路径覆盖 margins 但不覆盖 col_ratios） |
| 表格宽度（usable_width）   | `usable_width_cm(left, right)`                                       | Layout        | skeletons.py:210 / layout_kit.py:153 | `_resolve_layout` / `usable_width_cm` / `set_table_fixed_layout` | P1/P2/P3 | smoke_layout_kit                                                                                      | 已控制（单一来源） |
| 单元格文本区宽             | `cell_text_width_cm(cell_w, left, right)`                            | Layout        | skeletons.py:412 / layout_kit.py:171 | `_experience_in_cell` / `add_right_tab_stop`         | P2        | smoke_layout_kit                                                                                      | 已控制            |
| 照片盒尺寸（photo_box_cm） | `_LAYOUT_CONFIG[skeleton_id]["photo_box_cm"]` + `PhotoSpec.{width,height}` 或 `PhotoSpec.fallback.{width,height}`（circle 时） | Layout / Photo | skeletons.py:180-188 / layout_kit.py:396 | `_build_from_spec` / `insert_photo`                  | P1/P2/P3  | test_renderer_component.test_10_photo_insertion_and_missing_behavior                                  | 已控制            |
| 照片形状（rect/circle）    | `PhotoSpec.display_shape` → `display_shape=="circle"` 走 fallback 盒（不实现真圆形裁切） | Photo         | skeletons.py:182-186 / layout_kit.py:insert_photo | `_build_from_spec` / `insert_photo`                  | P2（P1=rect）| test_renderer_component.test_10                                                                       | Capability Gap（无 `a:srcRect` 椭圆遮罩） |
| A4 页面尺寸                | `A4_WIDTH_CM=21.0` / `A4_HEIGHT_CM=29.7` / `setup_a4(margins_cm)`    | Layout        | layout_kit.py:90-91 / 128      | `setup_a4`                                            | P1/P2/P3  | smoke_layout_kit                                                                                      | 已控制（常量） |
| 正文最小字号硬下限        | `MIN_BODY_PT=9.0` + `ConstraintsSpec.minimum_body_font_size_pt=9.0` | Layout / Validator | layout_kit.py:89 / validator.py:208-222 | `set_run_font` 兜底 + Validator RULE_BODY_FONT_SIZE   | P1/P2/P3  | test_design_spec                                                                                      | 已控制            |
| 单元格底纹                 | `shade_cell(cell, hex_color)`                                       | Layout        | layout_kit.py:243             | `shade_cell`                                          | P1/P2     | smoke_layout_kit                                                                                      | 已控制（原语层） |
| 单元格内边距（twips 换算） | `set_cell_margins(cell, top/bottom/left/right)`                      | Layout        | layout_kit.py:255             | `set_cell_margins`（值由 `RenderSpacing.cell_*_cm` 决定）| P1/P2     | test_renderer_spacing.test_05                                                                         | 已控制（原语层） |
| 表格固定布局               | `set_table_fixed_layout(table, total, col_widths)`                  | Layout        | layout_kit.py:278             | `set_table_fixed_layout`（重写 tblGrid）              | P1/P2/P3  | smoke_layout_kit                                                                                      | 已控制（原语层） |
| 单元格宽度                 | `set_cell_width(cell, width_cm)`                                     | Layout        | layout_kit.py:327             | `set_cell_width`                                      | P1/P2/P3  | smoke_layout_kit                                                                                      | 已控制（原语层） |
| Word/WPS 实测页数          | `count_pages_com(docx_path)`                                        | Layout        | layout_kit.py:473             | `count_pages_com`（COM 不可用时返回 None）            | 全部      | 无（Phase 3C 用人工 XML 检查替代）                                                                    | 需要进一步确认（依赖 Windows COM） |

控制点汇总：共 60 个视觉元素控制点。
- 已控制：30 个
- Schema Gap：18 个
- Capability Gap：8 个
- Profile 固定：1 个（col_ratios）
- Renderer 内部实现：1 个（sidebar 标题下边框）
- 需要进一步确认：2 个（paper 角色 / Word COM 页数）

---

## 3. 问题定位地图

> 流程：发现问题 → 检查什么 → 对应参数 → Owner → 修改位置 → 验证方式。
> 真实代码路径已替换示例占位。

### 例 1：姓名字号过大

```text
姓名字号过大
  ↓
Typography
  ↓
TypographySpec.name_size（design/spec.py:304）
  ↓
render_style.py:805  resolve_style_for_spec → _num → RenderStyle.name_size
  ↓
若旧路径：SKELETON_DEFAULT_STYLE[skeleton_id].name_size（render_style.py:581-698）
若 Spec 路径：build_p1_spec() / build_p2_spec()（design/presets.py）
  ↓
修改对应文件后重新生成 DOCX
  ↓
验证：
  python -m unittest tests.test_renderer_typography
  python -m unittest tests.test_renderer_stability tests.test_design_spec
  python tests/smoke_layout_kit.py  （字节对比 P1=37983 / P2=37933 / P3=37974）
```

### 例 2：Bullet 段后过松

```text
Bullet 段后过松
  ↓
Spacing
  ↓
ExperienceSpec.bullet_spacing_after（design/spec.py:375）
  ↓
render_style.py:251 _SPACING_SPEC_SOURCES["bullet_after"] → _resolve_spacing_for_spec → RenderSpacing.bullet_after
  ↓
旧路径：_DEFAULT_SPACING[skeleton_id].bullet_after（render_style.py:587-630，banner=1.5/minimal=1.5/sidebar=1.0）
Spec 路径：build_p1_spec()（6pt derived） / build_p2_spec()（8pt derived）
  ↓
修改对应文件后重新生成 DOCX
  ↓
验证：
  python -m unittest tests.test_renderer_spacing
  python -m unittest tests.test_renderer_stability
  python tests/smoke_layout_kit.py
```

### 例 3：两栏比例不对

```text
左右栏比例异常
  ↓
Skeleton Geometry
  ↓
_LAYOUT_CONFIG[skeleton_id]["col_ratios"]（skeletons.py:54-70）
   P1 banner: (8.4/18.8, 10.4/18.8)
   P2 sidebar: (5.9/19.4, 13.5/19.4)
   P3 minimal: (13.0/18.0, 5.0/18.0)
  ↓
Spec 路径不覆盖 col_ratios（_build_from_spec 只覆盖 margins/photo_box，不覆盖 col_ratios）
  ↓
修改 skeletons.py 的 _LAYOUT_CONFIG
  ↓
验证：
  python -m unittest tests.test_renderer_stability tests.test_renderer_component
  python tests/smoke_layout_kit.py  （三骨架字节必须 byte-perfect）
```

注：GridSpec.column_ratio 在 Validator 中校验合法性（validator.py:266-289），但 Renderer 不消费 Spec 的 column_ratio，仅消费 `_LAYOUT_CONFIG.col_ratios`。如需 Spec 驱动 col_ratios，属 Capability Gap / Renderer 改造。

### 例 4：照片无法变圆

```text
照片无法圆形裁切
  ↓
检查 DesignSpec 是否正确传递：PhotoSpec.display_shape="circle"（design/spec.py:343）→ _build_from_spec 命中 skeletons.py:182
  ↓
检查 Renderer 是否正确读取：_build_from_spec 读取 photo.fallback.width/height 覆盖 photo_box_cm（skeletons.py:183-186）
  ↓
检查 layout_kit.insert_photo（layout_kit.py:396）是否有圆形裁切原语
  ↓
结论：参数链路正常，layout_kit.insert_photo 未实现 a:srcRect + a:fill 椭圆遮罩
  ↓
分类：Capability Gap
  ↓
禁止修改无关参数（photo_box_cm / photo_preserve_aspect 不要动）
  ↓
需要扩展 layout_kit.insert_photo 增加 circle 形态分支（属下一阶段任务，本阶段禁止修改）
```

### 例 5：Sidebar bullet 字号与主栏不对称（17pt vs 19pt）

```text
Sidebar bullet 17pt vs main bullet 19pt
  ↓
Skeleton Geometry 设计决策（skeletons.py:685-692 sidebar bullet 用 style.body_size， skeletons.py:719-728 _body_bullet 也用 style.body_size）
  ↓
实际：sidebar bullet 走 style.body_size（与主栏一致），phase_3c_visual_qa.md Issue 005 报告 17pt/19pt 来自 legacy XML 实测
  ↓
检查 SKELETON_DEFAULT_STYLE[SKELETON_SIDEBAR].body_size（render_style.py:691 = 9.5pt）与 sidebar_body_size（=8.5pt）
  ↓
推测：sidebar cell 内 bullet 实际走 sidebar_body_size，_experience_in_cell 在 skeletons.py:679-692 中使用 style.body_size
  ↓
定位：skeletons.py:691（_experience_in_cell 的 bullet 字段）vs skeletons.py:727（_body_bullet 的 max(style.body_size, MIN_BODY_PT)）
  ↓
修改 skeletons.py 的 _experience_in_cell 或 _body_bullet 的字号消费（属 Renderer 改造，本阶段禁止）
  ↓
若需 DesignSpec 驱动侧栏字号：当前 TypographySpec 无 sidebar bullet 字号角色 → Schema Gap
```

注：本例需要进一步确认。phase_3c_visual_qa.md Issue 005 实测 P2 legacy 17pt / 19pt 不对称；代码审计显示 `build_sidebar` 调用 `_experience_in_cell`（skeletons.py:679-692），其中 bullet 字号为 `style.body_size`（P2 默认 9.5pt）；但 `build_sidebar` 的侧栏技能/证书 bullet（skeletons.py:460-479）使用 `sidebar_body_size`（8.5pt）。XML 实测 17pt/19pt 与代码默认值不直接对应，属 Template Geometry 设计选择（D 类）。

---

## 4. 修改决策树

```text
发现视觉问题
   │
   ↓
参数是否已经在 DesignSpec / Skeleton Profile 中存在？
   ┌──────────┴──────────┐
   否                       是
   ↓                        ↓
Schema Gap                  参数是否正确生效？
或 Capability Gap            ┌──────┴──────┐
（需 Renderer 扩展）          否             是
   ↓                          ↓              ↓
   登记                       Renderer Bug    B：Preset /
   下一阶段                    （A 类）        DesignSpec /
   处理                                       Profile 取值
                                              问题
```

### A 类：Renderer Bug

满足全部 4 项才归类为 A：

1. DesignSpec / Profile 意图明确（参数存在且语义清楚）。
2. 参数已经正确传入（`resolve_style_for_spec` 已解析、`RenderStyle.spec_fallbacks` 未登记该字段为 undetermined）。
3. Renderer 没有正确执行（`skeletons.py` / `layout_kit.py` 实际消费时未使用该参数，或使用方式与 Spec 语义不符）。
4. 测试或实际 DOCX XML 输出能够证明（XML diff 显示参数未生效）。

Phase 3C 结论：**未发现 A 类 Bug**。

### B 类：DesignSpec / Preset 问题

参数存在且 Renderer 正确执行，但参数值本身不符合目标设计。
例：`build_p1_spec()` 的 `bullet_spacing_after=6pt`（derived） / `line_spacing.body=1.9` / `section.spacing_before=22pt` 在 Spec 路径生效但密度过松（phase_3c Issue 001/004）；`build_p2_spec()` 的 `name_size=26pt` 过大（Issue 003）；`colors.dark_block=#252525` 偏中性灰（Issue 002）。

### C 类：Capability Gap

Renderer 根本没有实现该能力。
例：真圆形照片裁切（`layout_kit.insert_photo` 无 `a:srcRect` 椭圆遮罩）/ Bullet marker 独立着色（bullet 与正文同 run）/ Tag chip 边框（`RenderComponents` 无 tag 结构）/ ContactBlock 图标 / AchievementBanner 渲染 / icon_hairline 图标集资源 / Bullet hanging indent。

### D 类：Template Geometry

属于模板结构、布局比例或特定 Skeleton 的设计选择。
例：P3 minimal `role_separator="  "` 用空格（Profile 显式登记，非 Bug）/ P2 sidebar bullet 字号不对称（`build_sidebar` 的设计选择）/ `_LAYOUT_CONFIG` 各骨架 col_ratios / minimal `rule_sz=12` 永久 Profile。

---

## 5. 修改优先级

```text
① 参数问题（B 类 Preset 取值）       — 改 build_p1_spec() / build_p2_spec()
② Profile 取值问题（D 类 Skeleton Geometry）— 改 _LAYOUT_CONFIG / SKELETON_DEFAULT_STYLE
③ Schema Gap（Spec 字段缺失）        — 扩展 design/spec.py 增加字段
④ Capability Gap（Renderer 未实现）  — 扩展 layout_kit.py / skeletons.py
⑤ Renderer 重构（A 类 Bug）          — 修 skeletons.py / layout_kit.py
```

**禁止自行改变现有架构**。Control Map 的作用是帮助后续 Agent 先定位、再修改。

---

## 6. 测试关联表

| 修改目标                | 直接测试                                                                                | Regression 套件                                                                                                              | Smoke                                           | Doctor                       | Privacy                |
| ----------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ---------------------------- | ---------------------- |
| Typography（字号/字体/字重/行距） | `tests.test_renderer_typography`（9 测试）                                              | `test_renderer_palette` / `test_renderer_spacing` / `test_renderer_component` / `test_renderer_stability` / `test_design_spec` / `test_data_loader` | `python tests/smoke_layout_kit.py`              | `python gen.py doctor`       | `python tests/check_privacy.py` |
| Palette（颜色角色）     | `tests.test_renderer_palette`（8 测试）                                                 | 同上                                                                                                                          | 同上                                            | 同上                         | 同上                   |
| Spacing（段前段后/cell/边框厚度） | `tests.test_renderer_spacing`（10 测试）                                                | 同上                                                                                                                          | 同上                                            | 同上                         | 同上                   |
| Components（marker/分隔符/对齐/编号） | `tests.test_renderer_component`（22 测试）                                              | 同上                                                                                                                          | 同上                                            | 同上                         | 同上                   |
| Skeleton Geometry（margins/col_ratios/photo_box） | `tests.test_renderer_stability`（8 测试）+ `tests.smoke_layout_kit.py`                  | 同上                                                                                                                          | 同上                                            | 同上                         | 同上                   |
| DesignSpec（spec.py 字段 / validator 规则） | `tests.test_design_spec`（8 测试）                                                      | 同上                                                                                                                          | 同上                                            | 同上                         | 同上                   |
| DataLoader（data_loader.py） | `tests.test_data_loader`（32 测试）                                                     | 同上                                                                                                                          | 同上                                            | 同上                         | 同上                   |

执行命令（PowerShell 不支持 `&&`，用 `;` 或分行）：

```powershell
python -m unittest tests.test_renderer_component tests.test_renderer_typography tests.test_renderer_palette tests.test_renderer_spacing tests.test_renderer_stability tests.test_design_spec tests.test_data_loader
python tests/smoke_layout_kit.py
python gen.py doctor
python tests/check_privacy.py
```

**Smoke 字节基线（必须 byte-perfect）**：

- P1 banner_card = 37983 bytes
- P2 two_column_sidebar = 37933 bytes
- P3 single_column_minimal = 37974 bytes

任何字节变化都必须 XML diff 定位原因，禁止更新 baseline 掩盖回归。

注：PowerShell 下 `python -m unittest` 在测试通过时仍可能输出红色 `NativeCommandError` 文本，属 stderr 写入习惯，**不代表失败**。看结尾 `OK` / `Ran N tests` 行为准。

---

## 7. Capability Gap

> 数据来源：真实代码审计 + `docs/visual_qa/phase_3c_visual_qa.md` 第 343-363 行。**以代码为准**。

| Capability Gap                        | 真实代码证据                                                                                                                                                                                                                              | 关联 Spec 字段（若有）                                                                   | Owner 扩展点                                          |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| 1. 真圆形照片裁切                     | `layout_kit.insert_photo`（layout_kit.py:396-470）仅实现 `inserted_equal` / `inserted_contain` / `inserted_width_only` / `distorted_forced` / `missing` 五种状态，无 `a:srcRect` + `a:fill` 椭圆遮罩。`_build_from_spec`（skeletons.py:182-186）在 `display_shape=="circle"` 时仅读取 `photo.fallback.width/height` 覆盖 photo_box，**不实现真圆形裁切**。 | `PhotoSpec.display_shape="circle"` + `PhotoSpec.fallback.width/height`                    | `layout_kit.insert_photo`                              |
| 2. Bullet marker 独立着色             | `RenderComponents.bullet_symbol`（render_style.py:372）只控制字符；`_body_bullet`（skeletons.py:719-728）/ `_experience_in_cell`（skeletons.py:679-692）将 `bullet_symbol + bullet_gap + text` 拼入同一 `add_text` run，与正文同色。`BulletStyle.symbol_color_role`（spec.py:211）存在但 Renderer 不消费。 | `BulletStyle.symbol_color_role`                                                            | `skeletons._body_bullet` / `_experience_in_cell`      |
| 3. Bullet hanging indent（悬挂缩进）  | `ExperienceSpec.bullet_indent`（spec.py:374）存在；`_SPACING_SPEC_SOURCES`（render_style.py:246-255）无 `bullet_indent` 路径；`_body_bullet` / `_experience_in_cell` 使用普通段落无悬挂缩进原语。                                                                                                                | `ExperienceSpec.bullet_indent`                                                            | `layout_kit`（需新增悬挂缩进原语）/ `skeletons._body_bullet` |
| 4. Tag chip 边框 / 填充 / padding    | `RenderComponents`（render_style.py:359-384）无 tag 结构参数；`_experience_section`（skeletons.py:659-665）将 `item.tags` 作为 plain `add_text` 输出。`TagLine.separator`（spec.py:206）存在但 Renderer 仅消费 `size`/`color_role`。                                                                                  | `ExperienceSpec.tags`                                                                     | `skeletons._experience_section` / `layout_kit`        |
| 5. ContactBlock 图标 / label-value 拆分 | `RenderComponents` 无 contact icon 资源与 label/value 拆分参数；`build_banner_card`（skeletons.py:256-263）/ `build_minimal`（skeletons.py:330-337）/ `build_sidebar`（skeletons.py:448-455）将 `blocks.contact_lines` 作为单字符串拼接。                                                                          | 无（DesignSpec 无 contact 结构字段）                                                       | `skeletons.build_*`（需扩展）/ `layout_kit`（图标原语） |
| 6. AchievementBanner 零渲染实现       | `AchievementSpec`（spec.py:379-388）含 enabled/maximum_count/height/background_role/text_color_role/alignment/inset；`RenderComponents`（render_style.py:359-384）无 banner 结构参数；`_resolve_components_for_spec`（render_style.py:446-522）不读取 `AchievementSpec`。`build_banner_card` / `build_minimal` / `build_sidebar` 均无 banner 渲染分支。 | `AchievementSpec.*`                                                                      | `skeletons.build_*`（需新增 banner 渲染分支）          |
| 7. icon_hairline 图标集资源           | `IconSpec.resource`（spec.py:190-197）默认 `Sourced.undetermined("v1 未定义图标集/尺寸/风格/文件格式")`；`_resolve_components_for_spec`（render_style.py:481-487）检测到 `title_style=="icon_hairline"` 时仅登记 `components.section_icon<capability_gap>` fb，渲染回退 `section.prefix` 符号标题。                                                | `SectionSpec.title_style="icon_hairline"` + `IconSpec.resource`                           | `layout_kit`（需图标资源）/ `skeletons._section_title` |

**与 phase_3c_visual_qa.md 第 343-363 行的一致性核对**：

- 真圆形裁切：一致（Issue 006 复核未新增）。
- Bullet marker 独立着色 / 悬挂缩进：一致（第 349-352 行）。
- Tag chip：一致（第 354-356 行）。
- ContactBlock 图标：一致（第 358-360 行）。
- AchievementBanner：一致（第 360-362 行）。
- icon_hairline 资源：一致（第 362 行）。

**无差异**。当前代码状态与 phase_3c_visual_qa.md 报告完全一致。

---

## 8. Agent Modification Protocol

以后任何 Agent 修改 Resume Renderer 前，必须按下列顺序执行：

1. 先读取 `docs/architecture/resume_control_map.md`（本文档）。
2. 根据视觉问题在「核心控制表」定位 Owner Layer / Owner File / Owner Function。
3. 确认参数是否真实存在于代码中（grep 真实参数名，禁止凭印象）。
4. 判断问题属于 A / B / C / D 哪一类（参见第 4 节决策树）。
5. 优先修改参数 / Preset 取值，而不是直接修改底层 Renderer。
6. 修改前记录当前值（用于回滚与 diff 比对）。
7. 修改后运行第 6 节「测试关联表」中对应类别的直接测试。
8. 再运行完整 Regression（7 套件 97/97）。
9. 再运行 Smoke（必须 byte-perfect：P1=37983 / P2=37933 / P3=37974）。
10. 如果发现新的控制点或 Owner 发生变化，**同步更新本 Control Map**。
11. 如果无法确定控制位置，**不允许猜测修改**。先标记「需要进一步确认」并停止。

核心原则：

```text
先定位
  → 再修改
  → 再验证
  → 再更新地图
```

---

## 9. 谁负责什么（速查）

> 以代码审计为准。

| 视觉问题类别        | 负责 Layer        | Owner File / 模块                                       | 备注                                                                                            |
| ------------------- | ----------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 字体大小/字重/行距/字体族 | Typography        | `render_style.py` + `design/spec.py` TypographySpec    | Spec 字段缺失（如 intent_size）→ Schema Gap，回退 SKELETON_DEFAULT_STYLE                            |
| 颜色（ink/accent/muted/dark_block/on_dark_*/light_sidebar/hairline） | Palette           | `render_style.py` + `design/spec.py` ColorSpec          | `sidebar_heading` 是 Schema Gap，永远 Profile；`paper` 当前无渲染消费点                          |
| 间距（段前段后/cell 内边距/边框厚度） | Spacing           | `render_style.py` + `design/spec.py` SectionSpec/ExperienceSpec/HeaderSpec.AccentLine | 永久 Profile 槽位（cell_*_cm / rule_* / side_label_* / bar_before/after 等）→ Schema Gap           |
| 组件样式（marker / 分隔符 / 编号 / 对齐 / 等比保护） | Components        | `render_style.py` RenderComponents + `design/spec.py` ExperienceSpec/SectionSpec/PhotoSpec | `bullet_gap`/`cert_label`/`date_prefix`/`contact_align`/`side_label_transform`/`title_numbering_*` 均为 Schema Gap |
| 模板比例（margins / col_ratios / photo_box_cm） | Skeleton          | `skeletons.py` `_LAYOUT_CONFIG`                         | Spec 路径覆盖 margins（仅 P1 四值全确定时）与 photo_box_cm（circle 走 fallback）；col_ratios 永远 Profile |
| DOCX 底层行为（setup_a4 / set_table_fixed_layout / shade_cell / set_cell_margins / add_hairline / add_right_tab_stop / insert_photo） | Layout            | `layout_kit.py`                                          | 原语层，所有视觉参数由调用方注入；`add_hairline` 默认值保持工具层历史原值，视觉决策归 `RenderSpacing`        |
| 照片能力            | Photo / Layout Kit | `layout_kit.insert_photo` + `skeletons._build_from_spec` | 真圆形裁切属 Capability Gap；等比保护与 contain fallback 已实现；`distortion_allowed` Validator 强制 False    |
| JD 内容 / 经历层    | **不在本地图**     | `data_loader.py` + `data/` 资产库                      | Renderer 不读个人事实，`ResumeBlocks` 由调用方填入                                              |
| 模板选择            | **不在本地图**     | `agent_entry.md` + `gen.py`（已删除）                  | Phase 3A 后由 Agent 动态选择骨架，不再走固定模板路径                                            |
| 字号下限硬约束      | Validator         | `design/validator.py` RULE_BODY_FONT_SIZE               | `ConstraintsSpec.minimum_body_font_size_pt=9.0` + `layout_kit.MIN_BODY_PT=9.0` 工程兜底        |
| 单页页数            | Layout            | `layout_kit.count_pages_com`（COM 不可用返回 None）     | 最终以 Word/WPS `ComputeStatistics(2)` 实测为准；本阶段无自动化测试，需人工 XML 检查            |
