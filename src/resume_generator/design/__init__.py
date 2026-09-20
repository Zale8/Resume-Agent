# -*- coding: utf-8 -*-
"""design 子包 —— 设计决策层（Phase 2B）。

链路位置：
    ResumeBlocks → Design Engine(assembly.assemble_job_spec：范式 preset
                 + 本份 delta) → DesignSpec → Validator
                 → Renderer → layout_kit → DOCX

本包只描述/校验“怎么设计”，不操作 python-docx，也不含任何个人事实。
"""
from .spec import (
    DesignSpec,
    Sourced,
    MetaSpec,
    PageSpec,
    Margins,
    SafeArea,
    ArchitectureSpec,
    GridSpec,
    HeaderSpec,
    AccentLine,
    TypographySpec,
    TypographyWeights,
    LineSpacing,
    ColorSpec,
    PhotoSpec,
    PhotoFallback,
    PhotoFloating,
    PhotoBorder,
    SectionSpec,
    IconSpec,
    Divider,
    ExperienceSpec,
    TextStyle,
    TagLine,
    BulletStyle,
    AchievementSpec,
    DensitySpec,
    ConstraintsSpec,
)
from .validator import (
    validate_spec,
    ValidationResult,
    Issue,
    ALL_RULES,
    RULE_BODY_FONT_SIZE,
    RULE_SINGLE_ACCENT,
    RULE_DATE_ALIGNMENT,
    RULE_PHOTO_DISTORTION,
    RULE_PHOTO_FLOATING,
    RULE_PHOTO_BORDER,
    RULE_BLEED_UNDETERMINED,
    RULE_ICON_FALLBACK,
    RULE_UNCONSUMED_SPEC_FIELD,
)
from .consumption import (
    consumption_matrix,
    get_consumption,
    field_paths,
    evaluate_unconsumed,
    FieldConsumption,
    STATUS_CONSUMED,
    STATUS_PARTIALLY_CONSUMED,
    STATUS_FALLBACK,
    STATUS_UNCONSUMED,
)
from .presets import build_p1_spec, build_p2_spec, build_p3_spec
from .assembly import assemble_job_spec

__all__ = [
    "DesignSpec", "Sourced",
    "MetaSpec", "PageSpec", "Margins", "SafeArea",
    "ArchitectureSpec", "GridSpec", "HeaderSpec", "AccentLine",
    "TypographySpec", "TypographyWeights", "LineSpacing",
    "ColorSpec", "PhotoSpec", "PhotoFallback",
    "PhotoFloating", "PhotoBorder",
    "SectionSpec", "IconSpec", "Divider",
    "ExperienceSpec", "TextStyle", "TagLine", "BulletStyle",
    "AchievementSpec", "DensitySpec", "ConstraintsSpec",
    "validate_spec", "ValidationResult", "Issue", "ALL_RULES",
    "RULE_BODY_FONT_SIZE", "RULE_SINGLE_ACCENT", "RULE_DATE_ALIGNMENT",
    "RULE_PHOTO_DISTORTION", "RULE_PHOTO_FLOATING", "RULE_PHOTO_BORDER",
    "RULE_BLEED_UNDETERMINED", "RULE_ICON_FALLBACK",
    "RULE_UNCONSUMED_SPEC_FIELD",
    "consumption_matrix", "get_consumption", "field_paths",
    "evaluate_unconsumed", "FieldConsumption",
    "STATUS_CONSUMED", "STATUS_PARTIALLY_CONSUMED",
    "STATUS_FALLBACK", "STATUS_UNCONSUMED",
    "build_p1_spec", "build_p2_spec", "build_p3_spec",
    "assemble_job_spec",
]
