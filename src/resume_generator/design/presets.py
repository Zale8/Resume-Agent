# -*- coding: utf-8 -*-
"""presets.py — Resume Design Knowledge v1 的两份正式 DesignSpec 实例。

build_p1_spec() —— P1 深色身份横幅 + 单栏叙事（Renderer-ready）
build_p2_spec() —— P2 浅色档案侧栏 + 双栏叙事（5 个知识缺口显式 undetermined，
                   圆形照片 / 符号标题均内置 fallback）

本文件只承载“怎么设计”的取值，不含任何个人事实。
取值口径：
    kv1(...)       v1 明文范围/规则（多为样本 A 实测锚点，confidence=high）
    observed(...)  样本直接观察但落在 v1 通用范围之外（如深底第三级灰）
    derived(...)   由 v1 规则推导（Validator 会给 WARNING）
    undetermined   v1 缺口，禁止填值（Validator 会给 WARNING，Renderer 走 fallback）
"""
from __future__ import annotations

from typing import Optional

from .spec import (
    CONF_HIGH,
    CONF_MEDIUM,
    DENSITY_COMPACT,
    DENSITY_MEDIUM,
    DATE_COLUMN,
    DATE_TAB_STOP,
    AccentLine,
    AchievementSpec,
    ArchitectureSpec,
    BulletStyle,
    ColorSpec,
    ConstraintsSpec,
    DensitySpec,
    DesignSpec,
    Divider,
    ExperienceSpec,
    GridSpec,
    HeaderSpec,
    IconSpec,
    LineSpacing,
    Margins,
    MetaSpec,
    PageSpec,
    PhotoFallback,
    PhotoSpec,
    SafeArea,
    SectionSpec,
    Sourced,
    TagLine,
    TextStyle,
    TypographySpec,
    TypographyWeights,
)

# 板块内容优先级（与 AGENT.md 核心四板块约束一致，超页删改按此顺序）
_CONTENT_PRIORITY = [
    "个人信息", "教育经历", "实习经历", "项目经历",
    "专业技能", "证书奖项", "校园经历", "自我评价",
]
_OVERFLOW_STRATEGY = [
    "1. 删除与 JD 低相关内容",
    "2. 收紧 section / 条目间距",
    "3. 行内压缩低优先级板块（技能/证书/校园）",
    "4. 最后才调整字号，正文不得低于 9pt",
]


# ===========================================================================
# P1：深色身份横幅 + 单栏叙事
# ===========================================================================

def build_p1_spec() -> DesignSpec:
    # --- page ---
    margins = Margins(
        top=Sourced.kv1(0.5, "cm", CONF_HIGH, "样本A实测 0.5cm；通顶色块取范围下限"),
        bottom=Sourced.kv1(1.2, "cm", CONF_HIGH, "样本A实测约 1.2cm"),
        left=Sourced.kv1(1.4, "cm", CONF_HIGH, "样本A实测 1.4cm"),
        right=Sourced.kv1(1.4, "cm", CONF_HIGH, "样本A实测 1.4cm"),
    )
    safe = SafeArea(
        top=Sourced.derived(0.5, "cm"),
        bottom=Sourced.derived(1.2, "cm"),
        left=Sourced.derived(1.4, "cm"),
        right=Sourced.derived(1.4, "cm"),
        content_width=Sourced.derived(18.2, "cm",
                                      notes="21.0 - 1.4 - 1.4，表宽唯一来源"),
    )
    page = PageSpec(
        size=Sourced.kv1("A4", confidence=CONF_HIGH),
        width_cm=Sourced.kv1(21.0, "cm"),
        height_cm=Sourced.kv1(29.7, "cm"),
        orientation="portrait",
        target_pages=Sourced.kv1(1, "pages", CONF_HIGH,
                                 "目标声明；最终以 Word COM ComputeStatistics(2) 实测为准"),
        margins=margins,
        bleed=Sourced.kv1(0.0, "cm", CONF_HIGH,
                          "P1 无出血：深色横幅在页面边距内放置（样本A实测）"),
        safe_area=safe,
    )

    # --- architecture / grid ---
    architecture = ArchitectureSpec(
        paradigm="p1_banner_single",
        column_count=1,
        content_flow=["身份横幅", "个人优势", "教育经历", "实习经历",
                      "项目经历", "校园经历", "技能证书"],
        sidebar_enabled=False,
        main_contains=["全部板块"],
    )
    grid = GridSpec(
        column_ratio=[1.0],
        gutter=Sourced.kv1(0.0, "cm"),
        width_rule="column_widths = A4_width - margin_left - margin_right",
        column_widths_cm=Sourced.derived([18.2], "cm",
                                         notes="身份区内部表格同为 18.2cm（信息格弹性+照片格固定）"),
    )

    # --- header ---
    header = HeaderSpec(
        type="dark_identity_banner",
        height=Sourced.kv1(4.35, "cm", CONF_HIGH,
                           "样本A实测 4.35cm；v1 范围为页高 14–16%"),
        background_role="dark_block",
        accent_line=AccentLine(
            enabled=True,
            height=Sourced.kv1(2.16, "pt", CONF_HIGH, "样本A实测 2.16pt"),
        ),
        identity_alignment="left_text_right_photo",
        photo_zone="header_right_cell_fixed_width",
        text_inset=Sourced.kv1(0.38, "cm", CONF_MEDIUM,
                               "样本A实测文字相对页边距再内缩约 0.38cm"),
    )

    # --- typography（字号取样本A实测原值）---
    typography = TypographySpec(
        font_family=Sourced.kv1("Microsoft YaHei", confidence=CONF_HIGH,
                                notes="单字体族常规+粗体；Renderer 应以 sans_zh 字体令牌映射，"
                                      "按机器可用字体替换为同族字体"),
        weights=TypographyWeights(),
        name_size=Sourced.kv1(19.56, "pt", CONF_HIGH, "样本A实测"),
        title_size=Sourced.kv1(11.52, "pt", CONF_HIGH, "样本A实测"),
        organization_size=Sourced.kv1(10.56, "pt", CONF_HIGH, "样本A实测"),
        role_size=Sourced.kv1(9.96, "pt", CONF_HIGH, "样本A实测"),
        body_size=Sourced.kv1(9.48, "pt", CONF_HIGH,
                              "compact 档取偏小正文，靠 1.9 倍宽行距补偿"),
        metadata_size=Sourced.kv1(9.0, "pt", CONF_HIGH, "日期/标签链/符号"),
        line_spacing=LineSpacing(
            body=Sourced.kv1(1.9, "ratio", CONF_HIGH,
                             "样本A实测约 1.9；v1 规则：字越小行距越大"),
            title=Sourced.kv1(1.05, "ratio", CONF_HIGH, "样本A实测 1.0–1.05"),
        ),
        minimum_body_size=Sourced.kv1(9.0, "pt"),
        header_meta_sizes=[
            Sourced.kv1(8.04, "pt", CONF_HIGH, "深块内联系/人口信息行（样本A实测）"),
            Sourced.kv1(8.52, "pt", CONF_HIGH, "深块内教育背景行（样本A实测）"),
        ],
    )

    # --- colors ---
    colors = ColorSpec(
        ink=Sourced.kv1("#1A1A1A", confidence=CONF_HIGH, notes="样本A实测"),
        accent=Sourced.kv1("#E31937", confidence=CONF_HIGH,
                           notes="暖/执行系红；P1 面向销售/交付/制造执行岗"),
        muted=Sourced.kv1("#8A8A8A", confidence=CONF_HIGH, notes="日期/标签链"),
        paper=Sourced.kv1("#FFFFFF", confidence=CONF_HIGH),
        dark_block=Sourced.kv1("#252525", confidence=CONF_HIGH,
                               notes="近黑炭灰，非纯黑"),
        light_sidebar=None,
        hairline=Sourced.kv1("#DFDFDF", confidence=CONF_HIGH,
                             notes="样本A实测发丝线"),
        on_dark_primary=Sourced.kv1("#FFFFFF", confidence=CONF_HIGH,
                                    notes="深块上的姓名"),
        on_dark_secondary=Sourced.kv1("#E8E8E8", confidence=CONF_HIGH,
                                     notes="深块上的联系方式行"),
        on_dark_tertiary=Sourced.observed(
            "#BBBBBB", confidence=CONF_MEDIUM,
            notes="样本A实测的深底第三级灰（意向标签）；低于 v1 通用浅灰范围 "
                  "#E0E0E0–#EDEDED，属样本观察值而非通用 token；教育行为 #CCCCCC 同档"),
    )

    # --- photo ---
    photo = PhotoSpec(
        enabled=True,
        position="header_right_cell",
        width=Sourced.kv1(2.86, "cm", CONF_HIGH, "样本A实测 2.858cm"),
        height=Sourced.kv1(3.98, "cm", CONF_HIGH, "样本A实测 3.977cm"),
        aspect_ratio=Sourced.kv1(0.718, "ratio", CONF_HIGH,
                                 "竖版证件照；v1 要求 0.70–0.75"),
        container="dark_cell_no_border_no_radius",
        display_shape="rect",
        distortion_allowed=False,
        crop_allowed=False,
        source_crop="none",
        fallback=None,
    )

    # --- section ---
    section = SectionSpec(
        title_style="symbol_hairline",
        prefix=Sourced.kv1("▍", confidence=CONF_HIGH),
        icon=IconSpec(primary="none", fallback="symbol_hairline",
                      resource=Sourced.not_applicable("P1 不使用语义图标")),
        divider=Divider(
            weight=Sourced.kv1(0.0, "pt", CONF_HIGH,
                               "Phase 2B-1 修正：PDF_3 样本实测 line_count=0，"
                               "无 hairline divider；0pt 表达禁用"),
            color_role="hairline",
            width_rule="content_width",
            bleed=Sourced.kv1(0.05, "cm", CONF_MEDIUM,
                              "样本A实测发丝线左右各外伸约 0.05cm"),
        ),
        title_color_role="ink",
        symbol_color_role="accent",
        title_indent=Sourced.kv1(0.25, "cm", CONF_HIGH,
                                 "样本A实测符号到标题文字约 0.25cm"),
        spacing_before=Sourced.kv1(22, "pt", CONF_HIGH,
                                   "样本A实测段前约 22–25pt"),
        divider_to_first_line=Sourced.kv1(6, "pt", CONF_HIGH,
                                          "样本A实测 5–6pt"),
        title_spacing_after=Sourced.kv1(1, "pt", CONF_HIGH,
                                        "banner Profile title_after=1"),
    )

    # --- experience ---
    experience = ExperienceSpec(
        organization=TextStyle(
            size=Sourced.kv1(10.56, "pt", CONF_HIGH),
            weight="bold", color_role="ink"),
        role=TextStyle(
            size=Sourced.kv1(9.96, "pt", CONF_HIGH),
            weight="bold", color_role="accent", separator="｜"),
        date=TextStyle(
            size=Sourced.kv1(9.0, "pt", CONF_HIGH),
            weight="regular", color_role="muted"),
        # 样本A原本是空格流式（反模式），Spec 按 v1 硬规则修正为制表位
        date_alignment=DATE_TAB_STOP,
        tags=TagLine(
            enabled=True,
            size=Sourced.kv1(9.0, "pt", CONF_HIGH),
            color_role="muted", separator="·"),
        bullet=BulletStyle(
            symbol="•", symbol_color_role="ink",
            text_size=Sourced.kv1(9.48, "pt", CONF_HIGH),
            text_color_role="ink", count_min=1, count_max=4),
        bullet_indent=Sourced.kv1(0.35, "cm", CONF_HIGH,
                                  "样本A实测符号到正文约 0.35cm"),
        bullet_spacing_after=Sourced.derived(
            6, "pt", notes="compact 档取范围 6–12pt 下限，节奏主要由行距承担"),
        entry_spacing=Sourced.kv1(20, "pt", CONF_MEDIUM,
                                  "样本A实测推算约 20pt；范围 16–24"),
        entry_spacing_after=Sourced.kv1(1, "pt", CONF_HIGH,
                                       "banner Profile entry_after=1"),
    )

    # --- achievement ---
    achievement = AchievementSpec(
        enabled=True,
        maximum_count=1,
        height=Sourced.kv1(0.59, "cm", CONF_HIGH, "样本A实测 0.59cm"),
        background_role="accent",
        text_color_role="on_dark_primary",
        alignment="center",
        inset=Sourced.kv1(0.1, "cm", CONF_MEDIUM, "样本A实测左右内缩约 0.1cm"),
    )

    density = DensitySpec(
        level=DENSITY_COMPACT,
        body_line_spacing=Sourced.kv1(1.9, "ratio", CONF_HIGH),
        section_spacing=Sourced.kv1(22, "pt", CONF_HIGH),
        content_priority=list(_CONTENT_PRIORITY),
        overflow_strategy=list(_OVERFLOW_STRATEGY),
    )

    return DesignSpec(
        metadata=MetaSpec(
            spec_id="designspec_p1_dark_banner_single",
            version="0.1",
            paradigm="p1_banner_single",
            confidence=CONF_HIGH,
            notes="Renderer-ready；所有数值来自 v1（样本A实测锚点），"
                  "仅日期定位/列宽/少量间距为 derived",
        ),
        page=page,
        architecture=architecture,
        grid=grid,
        header=header,
        typography=typography,
        colors=colors,
        photo=photo,
        section=section,
        experience=experience,
        achievement=achievement,
        density=density,
        constraints=ConstraintsSpec(),
        design_intent=(
            "在高信息密度下，用深色身份横幅在 0.5 秒内完成身份识别，"
            "用单一红色只标记角色、意向与最强成果；正文小而行距宽，密度高但不显拥挤。"
        ),
        tradeoffs=[
            "信息密度高（compact），经历较少时版面会显空",
            "视觉装饰极少，品牌亲和感弱于 P2",
            "DOCX 工程稳定性最高：单表格身份区 + 段落边框 + 字符符号，无外部资源",
            "深底文字明度下限敏感，打印需验证",
        ],
    )


# ===========================================================================
# P2：浅色档案侧栏 + 双栏叙事（5 个知识缺口保持 undetermined）
# ===========================================================================

def build_p2_spec() -> DesignSpec:
    # --- page：bleed / margins / safe_area 全部为 v1 缺口，禁止填值 ---
    undetermined_margin = Sourced.undetermined(
        "P2 侧栏疑似通页出血，而 v1 只定义了内容边距范围（左右 1.0–1.6cm），"
        "未定义出血/安全区规则；待 v1.1 补充，候选：0cm 出血或常规内容边距")
    margins = Margins(
        top=Sourced.undetermined("依赖 bleed 结论（缺口 #2）"),
        bottom=Sourced.undetermined("依赖 bleed 结论（缺口 #2）"),
        left=Sourced.undetermined("依赖 bleed 结论（缺口 #2）"),
        right=Sourced.undetermined("依赖 bleed 结论（缺口 #2）"),
    )
    safe = SafeArea(
        top=undetermined_margin, bottom=undetermined_margin,
        left=undetermined_margin, right=undetermined_margin,
        content_width=Sourced.undetermined(
            "依赖 page margins；bleed 未确定前不得计算列宽"),
    )
    page = PageSpec(
        size=Sourced.kv1("A4", confidence=CONF_HIGH),
        width_cm=Sourced.kv1(21.0, "cm"),
        height_cm=Sourced.kv1(29.7, "cm"),
        orientation="portrait",
        target_pages=Sourced.kv1(1, "pages", CONF_HIGH,
                                 "目标声明；最终以 Word COM 实测为准"),
        margins=margins,
        bleed=Sourced.undetermined(
            "缺口 #2：样本B侧栏底色疑似上下通页出血，v1 无 bleed 规则"),
        safe_area=safe,
    )

    # --- architecture / grid ---
    architecture = ArchitectureSpec(
        paradigm="p2_sidebar_two_column",
        column_count=2,
        content_flow=["身份带", "求职意向", "教育经历", "实习经历",
                      "项目经历", "校园经历", "自我评价"],
        sidebar_enabled=True,
        sidebar_contains=["照片", "基本信息", "专业技能", "证书", "荣誉奖项"],
        main_contains=["姓名", "联系方式", "求职意向", "教育经历",
                       "实习经历", "项目经历", "校园经历", "自我评价"],
    )
    grid = GridSpec(
        column_ratio=[0.32, 0.68],
        gutter=Sourced.derived(
            1.0, "pt", notes="v1 允许中缝 0.5–1pt 竖线，取上限"),
        width_rule="column_widths = (A4_width - margin_left - margin_right) * ratio",
        column_widths_cm=Sourced.undetermined(
            "page margins（bleed）未确定，禁止预计算列宽"),
    )

    # --- header：身份带高度为缺口 #1 ---
    header = HeaderSpec(
        type="two_column_identity_split",
        height=Sourced.undetermined(
            "缺口 #1：v1 只给了 P1 Header 的 14–16%，"
            "P2 身份带高度无规则，渲染时由姓名/联系方式行数与内边距派生"),
        background_role=None,
        accent_line=AccentLine(
            enabled=False,
            height=Sourced.not_applicable("P2 无顶部强调线"),
        ),
        identity_alignment="photo_center_aligns_name_baseline_band",
        photo_zone="sidebar_top_centered",
        text_inset=None,
    )

    # --- typography ---
    typography = TypographySpec(
        font_family=Sourced.kv1(
            "sans_zh", confidence=CONF_MEDIUM,
            notes="单字体族；样本B实际字体无法从图片识别，"
                  "具体字体名由 Renderer 按机器可用字体映射（候选 Microsoft YaHei）"),
        weights=TypographyWeights(
            role="undetermined",  # 缺口：样本B角色行是否加粗无法确认
        ),
        name_size=Sourced.kv1(26, "pt", CONF_MEDIUM,
                              "样本B目测 24–28；白底靠字号建立第一层级，取中值"),
        title_size=Sourced.kv1(14, "pt", CONF_MEDIUM, "图标风标题目测 13–15"),
        organization_size=Sourced.derived(11.0, "pt", notes="取 v1 范围 10–11.5"),
        role_size=Sourced.derived(10.0, "pt", notes="取 v1 范围 9.5–10.5"),
        body_size=Sourced.derived(10.0, "pt", notes="medium 密度档取范围 9–10.5 中值"),
        metadata_size=Sourced.derived(9.0, "pt", notes="取范围 8.5–9.5"),
        line_spacing=LineSpacing(
            body=Sourced.derived(1.5, "ratio", notes="10pt 正文取 1.4–1.9 中段"),
            title=Sourced.derived(1.15, "ratio", notes="取 1.0–1.2 中段"),
            sidebar_body=Sourced.derived(1.4, "ratio",
                                         notes="侧栏 9pt 按规则反向补偿"),
        ),
        minimum_body_size=Sourced.kv1(9.0, "pt"),
        header_meta_sizes=None,
        sidebar_body_size=Sourced.kv1(
            9.0, "pt", CONF_MEDIUM,
            "侧栏比主栏小 0.5–1.0pt 且不低于 8.5；样本B目测 8.5–9.5"),
        sidebar_group_label_size=Sourced.undetermined(
            "缺口 #5：v1 未给侧栏分组小标题字号"),
    )

    # --- colors ---
    colors = ColorSpec(
        ink=Sourced.kv1("#222222", confidence=CONF_MEDIUM,
                        notes="样本B目测深灰文字，取 v1 范围边界"),
        accent=Sourced.kv1("#24406B", confidence=CONF_MEDIUM,
                           notes="冷/职能系深蓝；v1 范围 #1B4F72–#24406B 与目测区间交集"),
        muted=Sourced.derived("#888888", notes="取 v1 muted 范围中值"),
        paper=Sourced.kv1("#FFFFFF", confidence=CONF_HIGH, notes="主栏白底"),
        dark_block=None,
        light_sidebar=Sourced.kv1("#EFF2F7", confidence=CONF_MEDIUM,
                                  notes="样本B目测浅蓝灰底；v1 范围 #EDF1F7–#F4F6F8"),
        hairline=Sourced.kv1("#DDE2E8", confidence=CONF_MEDIUM,
                             notes="冷灰发丝线，取 v1 范围偏冷值"),
        on_dark_primary=None,
        on_dark_secondary=None,
        on_dark_tertiary=None,
    )

    # --- photo：圆形主方案 + 直角降级 ---
    photo = PhotoSpec(
        enabled=True,
        position="sidebar_top_centered",
        width=Sourced.kv1(4.2, "cm", CONF_MEDIUM,
                          "样本B目测圆形头像直径 4.0–4.8cm"),
        height=Sourced.kv1(4.2, "cm", CONF_MEDIUM, "圆形显示框直径=宽"),
        aspect_ratio=Sourced.kv1(1.0, "ratio", CONF_MEDIUM,
                                 "显示为正方形裁切后圆形；源证件照仍须 0.70–0.75"),
        container="circle_on_sidebar_surface",
        display_shape="circle",
        distortion_allowed=False,
        crop_allowed=True,
        source_crop="center_crop_to_square_then_circle",
        fallback=PhotoFallback(
            container="rect_no_radius_on_sidebar_surface",
            width=Sourced.derived(3.2, "cm", notes="v1 侧栏照片范围下限"),
            height=Sourced.derived(4.4, "cm", notes="按证件照比例 0.73 反推"),
            aspect_ratio=Sourced.derived(0.73, "ratio",
                                         notes="v1 证件照比例 0.70–0.75"),
        ),
    )

    # --- section：图标首选（资源缺口 #3），符号标题兜底 ---
    section = SectionSpec(
        title_style="icon_hairline",
        prefix=Sourced.kv1("▍", confidence=CONF_HIGH,
                           notes="仅 fallback 到 symbol_hairline 时使用"),
        icon=IconSpec(
            primary="semantic_icon",
            fallback="symbol_hairline",
            resource=Sourced.undetermined(
                "缺口 #3：v1 允许 P2 使用语义图标，但未定义图标集来源/尺寸/风格/"
                "文件格式/缺失降级；禁止自行创造图标库"),
        ),
        divider=Divider(
            weight=Sourced.derived(0.5, "pt", notes="取 v1 允许范围 0.4–0.75"),
            color_role="hairline",
            width_rule="within_each_column",
            bleed=Sourced.kv1(0.0, "cm"),
        ),
        title_color_role="accent",
        symbol_color_role="accent",
        title_indent=Sourced.kv1(0.2, "cm", CONF_MEDIUM,
                                 "样本B目测图标与文字间距"),
        spacing_before=Sourced.derived(20, "pt", notes="medium 档取 18–26 中值"),
        divider_to_first_line=Sourced.derived(6, "pt", notes="取 4–8 中值"),
        title_spacing_after=Sourced.kv1(2, "pt", CONF_HIGH,
                                        "sidebar Profile title_after=2"),
    )

    # --- experience ---
    experience = ExperienceSpec(
        organization=TextStyle(
            size=Sourced.derived(11.0, "pt"),
            weight="bold", color_role="ink"),
        role=TextStyle(
            size=Sourced.derived(10.0, "pt"),
            weight="undetermined",  # 缺口 #5：样本B无法确认角色字重
            color_role="ink",
            separator=None),
        date=TextStyle(
            size=Sourced.derived(9.0, "pt"),
            weight="regular", color_role="muted"),
        date_alignment=DATE_COLUMN,  # 样本B实测双基准线：机构左对齐/日期贴栏右缘
        tags=TagLine(
            enabled=False,
            size=Sourced.not_applicable("P2 不使用能力标签链行"),
            color_role="muted", separator="·"),
        bullet=BulletStyle(
            symbol="•", symbol_color_role="accent",
            text_size=Sourced.kv1(10.0, "pt", CONF_MEDIUM,
                                  "样本B目测正文 9.5–10.5"),
            text_color_role="ink", count_min=1, count_max=4),
        bullet_indent=Sourced.derived(0.4, "cm", notes="取 v1 范围 0.3–0.4 上限"),
        bullet_spacing_after=Sourced.derived(8, "pt", notes="medium 档取 6–12 中段"),
        entry_spacing=Sourced.derived(20, "pt", notes="取 16–24 中段"),
        entry_spacing_after=Sourced.kv1(1, "pt", CONF_HIGH,
                                       "sidebar Profile entry_after=1"),
    )

    achievement = AchievementSpec(
        enabled=False,  # 样本B未使用；如开启仍受 maximum_count=1 约束
        maximum_count=1,
        height=Sourced.derived(0.6, "cm", notes="备用值，取 v1 范围 0.5–0.7"),
        background_role="accent",
        text_color_role="on_dark_primary",
        alignment="center",
        inset=None,
    )

    density = DensitySpec(
        level=DENSITY_MEDIUM,
        body_line_spacing=Sourced.derived(1.5, "ratio"),
        section_spacing=Sourced.derived(20, "pt"),
        content_priority=list(_CONTENT_PRIORITY),
        overflow_strategy=list(_OVERFLOW_STRATEGY),
    )

    return DesignSpec(
        metadata=MetaSpec(
            spec_id="designspec_p2_light_sidebar_two_column",
            version="0.1",
            paradigm="p2_sidebar_two_column",
            confidence=CONF_MEDIUM,
            notes="含 5 个 v1 缺口（身份带高度/bleed/图标资源/深底灰/侧栏令牌）；"
                  "在缺口补齐前以 fallback 执行：非出血侧栏 + 符号标题 + 直角照片",
        ),
        page=page,
        architecture=architecture,
        grid=grid,
        header=header,
        typography=typography,
        colors=colors,
        photo=photo,
        section=section,
        experience=experience,
        achievement=achievement,
        density=density,
        constraints=ConstraintsSpec(
            narrow_column_min_ratio=0.28,
            column_height_imbalance_max_lines=3,
        ),
        design_intent=(
            "用浅色侧栏收纳全部静态档案，让主栏成为连续经历叙事；姓名靠超大字号建立"
            "第一层级，日期右对齐形成双基准线的表格式工整，气质亲和、扫读快。"
        ),
        tradeoffs=[
            "亲和力与扫读效率高，但圆形裁切与图标体系是 DOCX/WPS 两个风险点，均已内置降级",
            "双栏天然高度不平衡，两栏高差超过约 3 行须重分配板块",
            "侧栏底色通高在分页处可能出现半截色块，需 Renderer 整行底纹方案",
            "图标资源契约缺失前，标题样式实际以 symbol_hairline 兜底",
        ],
    )


# ===========================================================================
# P3：极简编辑风单栏（minimal editorial）
# ===========================================================================

def build_p3_spec() -> DesignSpec:
    """P3 minimal editorial：纯白底 + 单一深绿 accent + ▌ 前缀编号标题。

    以 PDF_2 为样本 A；latin_font / page_background / light_sidebar_secondary
    字段已建立但 Renderer 本阶段不消费，仅 schema 层表达。
    """
    # --- page：margins 来自 PDF_2 实测 L14.99/T13.58/R11.82/B13.72mm ---
    margins = Margins(
        top=Sourced.kv1(1.358, "cm", CONF_HIGH, "PDF_2 实测 T13.58mm"),
        bottom=Sourced.kv1(1.372, "cm", CONF_HIGH, "PDF_2 实测 B13.72mm"),
        left=Sourced.kv1(1.499, "cm", CONF_HIGH, "PDF_2 实测 L14.99mm"),
        right=Sourced.kv1(1.182, "cm", CONF_HIGH, "PDF_2 实测 R11.82mm"),
    )
    safe = SafeArea(
        top=Sourced.derived(1.358, "cm", notes="派生自 margin.top"),
        bottom=Sourced.derived(1.372, "cm", notes="派生自 margin.bottom"),
        left=Sourced.derived(1.499, "cm", notes="派生自 margin.left"),
        right=Sourced.derived(1.182, "cm", notes="派生自 margin.right"),
        content_width=Sourced.derived(
            18.319, "cm",
            notes="21.0 - 1.499 - 1.182；表宽唯一来源"),
    )
    page = PageSpec(
        size=Sourced.kv1("A4", confidence=CONF_HIGH),
        width_cm=Sourced.kv1(21.0, "cm"),
        height_cm=Sourced.kv1(29.7, "cm"),
        orientation="portrait",
        target_pages=Sourced.kv1(1, "pages", CONF_HIGH,
                                 "目标声明；最终以 Word COM 实测为准"),
        margins=margins,
        bleed=Sourced.kv1(0.0, "cm", CONF_HIGH, "PDF_2 无出血"),
        safe_area=safe,
    )

    # --- architecture / grid ---
    architecture = ArchitectureSpec(
        paradigm="p3_minimal_editorial",
        column_count=1,
        content_flow=["个人信息", "教育经历", "实习经历", "项目经历",
                      "专业技能", "证书奖项", "自我评价"],
        sidebar_enabled=False,
        main_contains=["全部板块"],
    )
    grid = GridSpec(
        column_ratio=[1.0],
        gutter=Sourced.kv1(0.0, "cm"),
        width_rule="column_widths = A4_width - margin_left - margin_right",
        column_widths_cm=Sourced.derived(
            [18.319], "cm",
            notes="单栏；21.0 - 1.499 - 1.182"),
    )

    # --- header：plain_inline_header（无 banner，无 accent_line）---
    header = HeaderSpec(
        type="plain_inline_header",
        height=Sourced.derived(
            1.5, "cm",
            notes="PDF_2 无独立身份区高度；由姓名+意向+联系方式行数派生"),
        background_role=None,
        accent_line=AccentLine(
            enabled=False,
            height=Sourced.not_applicable("P3 无顶部强调线"),
        ),
        identity_alignment="left_text_only",
        photo_zone="none",
        text_inset=None,
    )

    # --- typography ---
    typography = TypographySpec(
        font_family=Sourced.kv1("Microsoft YaHei", confidence=CONF_HIGH,
                                notes="单字体族常规+粗体"),
        latin_font=Sourced.kv1(
            "ArialMT", confidence=CONF_HIGH,
            notes="PDF_2 实测西文用 ArialMT/Arial-BoldMT；"
                  "本阶段 Renderer 不消费，仅 Spec 层表达"),
        weights=TypographyWeights(),
        name_size=Sourced.kv1(17.04, "pt", CONF_HIGH, "PDF_2 实测"),
        title_size=Sourced.kv1(10.56, "pt", CONF_HIGH, "PDF_2 实测"),
        organization_size=Sourced.derived(10.56, "pt",
                                          notes="与 title_size 同档（PDF_2 实测）"),
        role_size=Sourced.derived(9.0, "pt", notes="与 body_size 同档"),
        body_size=Sourced.kv1(9.0, "pt", CONF_HIGH, "PDF_2 实测"),
        metadata_size=Sourced.kv1(8.52, "pt", CONF_HIGH, "PDF_2 实测"),
        line_spacing=LineSpacing(
            body=Sourced.derived(
                1.4, "ratio",
                notes="PDF_2 目测约 1.4；样本行距规则未在 v1 中明文覆盖，"
                      "待 Renderer 落地回归验证"),
            title=Sourced.derived(1.15, "ratio", notes="取 1.0–1.2 中段"),
        ),
        minimum_body_size=Sourced.kv1(9.0, "pt"),
        header_meta_sizes=[
            Sourced.kv1(8.52, "pt", CONF_HIGH, "PDF_2 实测副信息行")],
        sidebar_body_size=None,
        sidebar_group_label_size=None,
    )

    # --- colors ---
    colors = ColorSpec(
        ink=Sourced.kv1("#000000", confidence=CONF_HIGH, notes="PDF_2 实测纯黑"),
        accent=Sourced.kv1("#0A6B3C", confidence=CONF_HIGH,
                           notes="PDF_2 实测深绿；P3 面向产品/运营岗"),
        muted=Sourced.kv1("#444444", confidence=CONF_HIGH, notes="PDF_2 实测中灰"),
        paper=Sourced.kv1("#FFFFFF", confidence=CONF_HIGH, notes="PDF_2 纯白底"),
        dark_block=None,
        light_sidebar=None,
        hairline=Sourced.kv1(
            "#007A37", confidence=CONF_HIGH,
            notes="Golden Sample CL-02：分割线绿 #007A37（区别于 accent #0A6B3C）"),
        on_dark_primary=None,
        on_dark_secondary=None,
        on_dark_tertiary=None,
        page_background=None,  # PDF_2 纯白，本阶段 Renderer 不消费
        light_sidebar_secondary=None,
    )

    # --- photo ---
    photo = PhotoSpec(
        enabled=False,
        position="none",
        width=Sourced.not_applicable("P3 不使用照片"),
        height=Sourced.not_applicable("P3 不使用照片"),
        aspect_ratio=Sourced.not_applicable("P3 不使用照片"),
        container="none",
        display_shape="rect",
        distortion_allowed=False,
        crop_allowed=False,
        source_crop="none",
        fallback=None,
    )

    # --- section：▌ 前缀 + 标题下 2.25pt 绿色分割线（Golden Sample CL-02）---
    section = SectionSpec(
        title_style="symbol_hairline",
        prefix=Sourced.kv1(
            "▌", confidence=CONF_HIGH,
            notes="PDF_2 实测，U+2588 FULL BLOCK 左半实心；区别于 P1 的 ▍ U+254D"),
        icon=IconSpec(primary="none", fallback="symbol_hairline",
                      resource=Sourced.not_applicable("P3 不使用语义图标")),
        divider=Divider(
            weight=Sourced.kv1(
                2.25, "pt", CONF_HIGH,
                "Golden Sample CL-02：板块标题下 2.25pt 实线；0pt 表达禁用"),
            color_role="hairline",
            width_rule="content_width",
            bleed=Sourced.kv1(0.0, "cm"),
        ),
        title_color_role="ink",
        symbol_color_role="accent",
        title_indent=Sourced.kv1(
            0.15, "cm", CONF_MEDIUM,
            "PDF_2 实测符号到文字约 0.15cm；小于 P1 的 0.25cm"),
        spacing_before=Sourced.derived(
            10, "pt",
            notes="PDF_2 单栏紧凑，section 段前约 8-12pt；远小于 P1 的 22pt"),
        divider_to_first_line=Sourced.derived(
            4, "pt", notes="PDF_2 取 4-6pt 下限"),
        title_spacing_after=Sourced.kv1(1, "pt", CONF_HIGH,
                                        "minimal Profile title_after=1"),
        styles_per_document=Sourced.kv1(1, "count"),
    )

    # --- experience ---
    experience = ExperienceSpec(
        organization=TextStyle(
            size=Sourced.kv1(10.56, "pt", CONF_HIGH),
            weight="bold", color_role="ink"),
        role=TextStyle(
            size=Sourced.kv1(9.0, "pt", CONF_HIGH),
            weight="bold", color_role="accent", separator="｜"),
        date=TextStyle(
            size=Sourced.kv1(8.52, "pt", CONF_HIGH),
            weight="regular", color_role="muted"),
        date_alignment=DATE_TAB_STOP,  # v1 硬规则
        tags=TagLine(
            enabled=True,
            size=Sourced.kv1(9.0, "pt", CONF_HIGH),
            color_role="muted", separator="·"),
        bullet=BulletStyle(
            symbol="•", symbol_color_role="ink",
            text_size=Sourced.kv1(9.0, "pt", CONF_HIGH),
            text_color_role="ink", count_min=1, count_max=4),
        bullet_indent=Sourced.kv1(0.15, "cm", CONF_MEDIUM,
                                  "PDF_2 实测缩进约 0.15cm"),
        bullet_spacing_after=Sourced.derived(
            6, "pt", notes="medium 档取 6-12 下限"),
        entry_spacing=Sourced.derived(
            14, "pt", notes="PDF_2 单栏紧凑，小于 P1 的 20pt"),
        entry_spacing_after=Sourced.kv1(1, "pt", CONF_HIGH,
                                       "minimal Profile entry_after=1"),
    )

    # --- achievement ---
    achievement = AchievementSpec(
        enabled=False,
        maximum_count=1,
        height=Sourced.not_applicable("P3 不使用成果横幅"),
        background_role="accent",
        text_color_role="on_dark_primary",
        alignment="center",
        inset=None,
    )

    density = DensitySpec(
        level=DENSITY_MEDIUM,
        body_line_spacing=Sourced.derived(1.4, "ratio"),
        section_spacing=Sourced.derived(10, "pt"),
        content_priority=list(_CONTENT_PRIORITY),
        overflow_strategy=list(_OVERFLOW_STRATEGY),
    )

    return DesignSpec(
        metadata=MetaSpec(
            spec_id="designspec_p3_minimal_editorial",
            version="0.1",
            paradigm="p3_minimal_editorial",
            confidence=CONF_MEDIUM,
            notes="Renderer-ready P3 minimal editorial；以 PDF_2 为样本 A；"
                  "latin_font/page_background/light_sidebar_secondary 字段已建立"
                  "但 Renderer 本阶段不消费",
        ),
        page=page,
        architecture=architecture,
        grid=grid,
        header=header,
        typography=typography,
        colors=colors,
        photo=photo,
        section=section,
        experience=experience,
        achievement=achievement,
        density=density,
        constraints=ConstraintsSpec(),
        design_intent=(
            "用纯白底+单一深绿 accent+▌ 前缀编号标题+ArialMT 西文，"
            "在单栏内以编辑风排版完成产品/运营岗位的叙事；"
            "姓名靠 accent 色 + 17pt 字号建立弱视觉锚点，"
            "留白由内容密度自适应。"
        ),
        tradeoffs=[
            "拉丁字体 Renderer 本阶段不消费，仅 Spec 层表达；"
            "后续若要落地需扩展 set_run_font 写 w:ascii/w:hAnsi",
            "正文 9.0pt 已触下限，长内容时无字号余量，"
            "必须靠 section spacing 与 bullet spacing 收缩",
            "板块分隔 = ▌ 前缀 + 标题下 2.25pt 绿色分割线（Golden Sample CL-02）",
        ],
    )


def build_p3_compact_spec(
    body_line_spacing: float = 1.2,
    bullet_spacing_after_pt: Optional[int] = None,
    entry_spacing_pt: Optional[int] = None,
    section_spacing_before_pt: Optional[int] = None,
    divider_to_first_line_pt: Optional[int] = None,
) -> DesignSpec:
    """P3 Compact：P3 minimal editorial 的紧凑变体。

    在 build_p3_spec() 基础上选择性收紧 line_spacing 与 spacing 参数，
    用于内容密度高的简历场景。P3 原始行为完全保留（build_p3_spec() 函数体未修改）。

    候选参数：
      body_line_spacing      P3 1.4 → 1.2（默认开启）
      bullet_spacing_after_pt  P3 6 → 4（None=不调）
      entry_spacing_pt          P3 14 → 8
      section_spacing_before_pt P3 10 → 6
      divider_to_first_line_pt P3 4 → 0
    """
    from dataclasses import replace

    base = build_p3_spec()

    # line_spacing.body（TypographySpec + DensitySpec 同步）
    new_typo = replace(
        base.typography,
        line_spacing=replace(
            base.typography.line_spacing,
            body=Sourced.derived(
                body_line_spacing, "ratio",
                notes=f"P3 Compact: P3 的 1.4 → {body_line_spacing}"),
        ),
    )
    new_density = replace(
        base.density,
        body_line_spacing=Sourced.derived(
            body_line_spacing, "ratio",
            notes="P3 Compact: 同步 typography.line_spacing.body"),
    )

    new_section = base.section
    if section_spacing_before_pt is not None:
        new_section = replace(
            new_section,
            spacing_before=Sourced.derived(
                section_spacing_before_pt, "pt",
                notes=f"P3 Compact: P3 的 10 → {section_spacing_before_pt}"),
        )
    if divider_to_first_line_pt is not None:
        new_section = replace(
            new_section,
            divider_to_first_line=Sourced.derived(
                divider_to_first_line_pt, "pt",
                notes=f"P3 Compact: P3 的 4 → {divider_to_first_line_pt}"),
        )

    new_experience = base.experience
    if bullet_spacing_after_pt is not None:
        new_experience = replace(
            new_experience,
            bullet_spacing_after=Sourced.derived(
                bullet_spacing_after_pt, "pt",
                notes=f"P3 Compact: P3 的 6 → {bullet_spacing_after_pt}"),
        )
    if entry_spacing_pt is not None:
        new_experience = replace(
            new_experience,
            entry_spacing=Sourced.derived(
                entry_spacing_pt, "pt",
                notes=f"P3 Compact: P3 的 14 → {entry_spacing_pt}"),
        )

    return replace(
        base,
        metadata=replace(
            base.metadata,
            spec_id="designspec_p3_compact",
            notes=(base.metadata.notes or "")
                  + " | P3 Compact 变体（line_spacing + spacing 收紧）"
                  f" ls={body_line_spacing}"
                  f" bullet_after={bullet_spacing_after_pt}"
                  f" entry_before={entry_spacing_pt}"
                  f" section_before={section_spacing_before_pt}"
                  f" divider_to_first_line={divider_to_first_line_pt}",
        ),
        typography=new_typo,
        density=new_density,
        section=new_section,
        experience=new_experience,
    )

