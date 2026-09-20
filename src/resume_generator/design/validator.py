# -*- coding: utf-8 -*-
"""validator.py — DesignSpec 契约校验器（Phase 2B）。

职责边界（只做一件事）：
    判断 DesignSpec 是否违反 Resume Design Knowledge v1 的设计契约。
    不判断“好不好看”，不操作 python-docx，不渲染 DOCX。

输出：
    ValidationResult{ valid, errors[], warnings[], checked_rules[] }

规则分两级：
    ERROR   —— 违反硬约束，Renderer 不允许执行该 Spec。
    WARNING —— 含推导值 / 未确定参数 / P2 fallback，可执行但需知情确认。
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Iterator, List, Optional

from .spec import (
    CONF_LOW,
    DATE_SPACES,
    SOURCE_DERIVED,
    STATUS_UNDETERMINED,
    TITLE_ICON,
    Sourced,
    DesignSpec,
)
from .consumption import evaluate_unconsumed

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"

# ---------------------------------------------------------------------------
# 规则 ID 注册表（checked_rules 始终输出全集，便于定位“查了什么”）
# ---------------------------------------------------------------------------

RULE_INVALID_PAGE_SIZE = "invalid_page_size"
RULE_TARGET_PAGES = "target_pages_must_be_one"
RULE_BODY_FONT_SIZE = "minimum_body_font_size"
RULE_SINGLE_FONT_FAMILY = "single_font_family"
RULE_SINGLE_ACCENT = "single_accent_color"
RULE_ACHIEVEMENT_COUNT = "maximum_achievement_banner"
RULE_DATE_ALIGNMENT = "no_space_based_date_alignment"
RULE_PHOTO_DISTORTION = "photo_distortion_forbidden"
RULE_PHOTO_FLOATING = "invalid_photo_floating"
RULE_PHOTO_BORDER = "invalid_photo_border"
RULE_COLUMN_RATIO = "invalid_column_ratio"
RULE_NEGATIVE_SPACING = "invalid_negative_spacing"
RULE_TABLE_WIDTH = "table_width_within_content_area"
RULE_PHOTO_ASPECT = "photo_dimensions_match_aspect_ratio"

RULE_UNDETERMINED = "parameter_undetermined"
RULE_BLEED_UNDETERMINED = "bleed_undetermined"
RULE_LOW_CONFIDENCE = "low_confidence_parameter"
RULE_DERIVED = "derived_parameter"
RULE_ICON_FALLBACK = "icon_resource_fallback"
RULE_PHOTO_FALLBACK = "photo_fallback_configured"
# Phase 2B-2：Spec 显式承诺（enabled/定值）但 Renderer 无消费点。
# 永远是非阻断 WARNING——只暴露契约缺口，绝不阻止渲染（禁止升级为 ERROR）。
RULE_UNCONSUMED_SPEC_FIELD = "spec_field_without_consumer"

ALL_RULES: List[str] = [
    RULE_INVALID_PAGE_SIZE,
    RULE_TARGET_PAGES,
    RULE_BODY_FONT_SIZE,
    RULE_SINGLE_FONT_FAMILY,
    RULE_SINGLE_ACCENT,
    RULE_ACHIEVEMENT_COUNT,
    RULE_DATE_ALIGNMENT,
    RULE_PHOTO_DISTORTION,
    RULE_PHOTO_FLOATING,
    RULE_PHOTO_BORDER,
    RULE_COLUMN_RATIO,
    RULE_NEGATIVE_SPACING,
    RULE_TABLE_WIDTH,
    RULE_PHOTO_ASPECT,
    RULE_UNDETERMINED,
    RULE_BLEED_UNDETERMINED,
    RULE_LOW_CONFIDENCE,
    RULE_DERIVED,
    RULE_ICON_FALLBACK,
    RULE_PHOTO_FALLBACK,
    RULE_UNCONSUMED_SPEC_FIELD,
]

# 这些路径的负值属于非法间距类参数
_SPACING_PATH_HINTS = ("spacing", "margin", "indent", "gutter", "inset", "bleed")
_RATIO_TOLERANCE = 0.005
_ASPECT_TOLERANCE = 0.03

# Golden Sample CL-01 已验证的浮动锚点 relativeFrom 白名单
_PHOTO_FLOAT_H_REL = frozenset(("column", "page", "margin"))
_PHOTO_FLOAT_V_REL = frozenset(("page", "margin"))
_HEX_COLOR_CHARS = frozenset("0123456789ABCDEFabcdef")


@dataclass
class Issue:
    rule_id: str
    severity: str
    message: str
    path: str = ""
    expected: Any = None
    actual: Any = None

    def render(self) -> str:
        loc = f" [{self.path}]" if self.path else ""
        tail = ""
        if self.expected is not None or self.actual is not None:
            tail = f"（expected={self.expected!r}, actual={self.actual!r}）"
        return f"{self.severity}: {self.message}{loc}{tail}"


@dataclass
class ValidationResult:
    valid: bool = True
    errors: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    checked_rules: List[str] = field(default_factory=lambda: list(ALL_RULES))

    def add_error(self, rule_id: str, message: str, path: str = "",
                  expected: Any = None, actual: Any = None) -> None:
        self.errors.append(Issue(rule_id, SEVERITY_ERROR, message, path,
                                 expected, actual))
        self.valid = False

    def add_warning(self, rule_id: str, message: str, path: str = "",
                    expected: Any = None, actual: Any = None) -> None:
        self.warnings.append(Issue(rule_id, SEVERITY_WARNING, message, path,
                                   expected, actual))

    def has_warning(self, rule_id: str) -> bool:
        return any(w.rule_id == rule_id for w in self.warnings)

    def warning_paths(self, rule_id: str) -> List[str]:
        return [w.path for w in self.warnings if w.rule_id == rule_id]

    def render_text(self) -> str:
        lines = [f"valid: {self.valid}", "",
                 f"errors ({len(self.errors)}):"]
        lines += [f"  - {e.render()}" for e in self.errors] or ["  （无）"]
        lines += ["", f"warnings ({len(self.warnings)}):"]
        lines += [f"  - {w.render()}" for w in self.warnings] or ["  （无）"]
        lines += ["", f"checked_rules ({len(self.checked_rules)}): "
                       + ", ".join(self.checked_rules)]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 遍历工具
# ---------------------------------------------------------------------------

def _walk_sourced(node: Any, path: str = "") -> Iterator[tuple]:
    """递归产出 (path, Sourced)。跳过 None 与裸字符串。"""
    if node is None:
        return
    if isinstance(node, Sourced):
        yield path, node
        return
    if is_dataclass(node) and not isinstance(node, type):
        for f in fields(node):
            yield from _walk_sourced(getattr(node, f.name),
                                     f"{path}.{f.name}" if path else f.name)
        return
    if isinstance(node, (list, tuple)):
        for i, item in enumerate(node):
            yield from _walk_sourced(item, f"{path}[{i}]")


def _walk_bare_strings(node: Any, path: str = "") -> Iterator[tuple]:
    """递归产出值恰好为 "undetermined" 的裸字符串字段（如 weight="undetermined"）。"""
    if node is None or isinstance(node, Sourced):
        return
    if is_dataclass(node) and not isinstance(node, type):
        for f in fields(node):
            yield from _walk_bare_strings(getattr(node, f.name),
                                          f"{path}.{f.name}" if path else f.name)
        return
    if isinstance(node, (list, tuple)):
        for i, item in enumerate(node):
            yield from _walk_bare_strings(item, f"{path}[{i}]")
        return
    if isinstance(node, str) and node == "undetermined":
        yield path, node


def _num(p: Optional[Sourced]) -> Optional[float]:
    """Sourced 数值可用时返回 float，否则 None。"""
    if isinstance(p, Sourced) and not p.is_undetermined \
            and isinstance(p.value, (int, float)):
        return float(p.value)
    return None


# ---------------------------------------------------------------------------
# 校验器
# ---------------------------------------------------------------------------

def validate_spec(spec: DesignSpec) -> ValidationResult:
    """校验一份 DesignSpec，返回结构化结果。纯函数，无副作用。"""
    r = ValidationResult()

    page = spec.page
    ty = spec.typography
    cons = spec.constraints

    # --- ERROR: 纸张尺寸 ---
    if page.size.is_undetermined or page.size.value != "A4":
        r.add_error(RULE_INVALID_PAGE_SIZE,
                    f"page.size 必须为 A4（当前={page.size.value!r}）",
                    "page.size", expected="A4", actual=page.size.value)

    # --- ERROR: 目标页数 ---
    tp = page.target_pages
    if tp.is_undetermined or tp.value != 1:
        r.add_error(RULE_TARGET_PAGES,
                    "target_pages 必须为 1；单页是目标声明，"
                    "最终页数仍以 Word COM 实测为准",
                    "page.target_pages", expected=1, actual=tp.value)

    # --- ERROR: 正文字号下限 ---
    body = _num(ty.body_size)
    floor = max(9.0, float(cons.minimum_body_font_size_pt))
    if body is not None and body < floor:
        r.add_error(RULE_BODY_FONT_SIZE,
                    f"body_size={body}pt 低于硬下限 {floor}pt；"
                    "禁止靠缩小正文解决超页",
                    "typography.body_size",
                    expected=f">= {floor}pt", actual=f"{body}pt")
    sidebar_body = _num(ty.sidebar_body_size)
    if sidebar_body is not None and sidebar_body < floor:
        r.add_error(RULE_BODY_FONT_SIZE,
                    f"sidebar_body_size={sidebar_body}pt 低于硬下限 {floor}pt",
                    "typography.sidebar_body_size",
                    expected=f">= {floor}pt", actual=f"{sidebar_body}pt")

    # --- ERROR: 单一字体族 ---
    ff = ty.font_family
    fams = ff.value if isinstance(ff.value, (list, tuple)) else [ff.value]
    if ff.is_undetermined or len([f for f in fams if f]) != 1:
        r.add_error(RULE_SINGLE_FONT_FAMILY,
                    f"必须恰好 1 个字体族（当前={fams}）",
                    "typography.font_family",
                    expected="single font family", actual=fams)

    # --- ERROR: 强调色只能 1 个 ---
    if spec.colors.additional_accents:
        r.add_error(RULE_SINGLE_ACCENT,
                    f"存在 {len(spec.colors.additional_accents)} 个额外强调色；"
                    "同一语义只能有一个 accent 色值",
                    "colors.additional_accents",
                    expected="empty",
                    actual=[a.value for a in spec.colors.additional_accents])

    # --- ERROR: 成果横幅 ≤ 1 ---
    if spec.achievement.maximum_count > cons.maximum_achievement_banner:
        r.add_error(RULE_ACHIEVEMENT_COUNT,
                    f"maximum_count={spec.achievement.maximum_count} 超过上限 "
                    f"{cons.maximum_achievement_banner}",
                    "achievement.maximum_count",
                    expected=f"<= {cons.maximum_achievement_banner}",
                    actual=spec.achievement.maximum_count)

    # --- ERROR: 日期禁止空格定位 ---
    if spec.experience.date_alignment == DATE_SPACES:
        r.add_error(RULE_DATE_ALIGNMENT,
                    "date_alignment=spaces 是已确认反模式；"
                    "必须使用 tab_stop 或 column 定位",
                    "experience.date_alignment",
                    expected="tab_stop | column", actual=DATE_SPACES)

    # --- ERROR: 照片禁止允许变形 ---
    if spec.photo.enabled and spec.photo.distortion_allowed:
        r.add_error(RULE_PHOTO_DISTORTION,
                    "distortion_allowed 必须为 false；比例不符时只能裁切或走 fallback",
                    "photo.distortion_allowed",
                    expected=False, actual=True)

    # --- ERROR: 栏比例合法 ---
    ratio = spec.grid.column_ratio
    ncol = spec.architecture.column_count
    if ncol == 1:
        if not ratio or abs(ratio[0] - 1.0) > _RATIO_TOLERANCE:
            r.add_error(RULE_COLUMN_RATIO,
                        f"单栏 column_ratio 必须为 [1.0]（当前={ratio}）",
                        "grid.column_ratio", expected="[1.0]", actual=ratio)
    elif ncol == 2:
        if len(ratio) != 2 or abs(sum(ratio) - 1.0) > _RATIO_TOLERANCE:
            r.add_error(RULE_COLUMN_RATIO,
                        f"双栏比例之和必须为 1.0（当前={ratio}，和={sum(ratio) if len(ratio)==2 else 'N/A'}）",
                        "grid.column_ratio", expected="sum=1.0", actual=ratio)
        elif min(ratio) < cons.narrow_column_min_ratio:
            r.add_error(RULE_COLUMN_RATIO,
                        f"窄栏占比 {min(ratio):.2f} 低于下限 "
                        f"{cons.narrow_column_min_ratio}（中文会逐字换行）",
                        "grid.column_ratio",
                        expected=f">= {cons.narrow_column_min_ratio}",
                        actual=min(ratio))
    else:
        r.add_error(RULE_COLUMN_RATIO,
                    f"column_count={ncol} 不在已验证范式内（只允许 1 或 2）",
                    "architecture.column_count", expected="1 | 2", actual=ncol)

    # --- ERROR + WARNING: 全量扫描 Sourced 值 ---
    for path, sv in _walk_sourced(spec):
        # 未确定参数（bleed 单独归类，见下方专项规则）
        if sv.status == STATUS_UNDETERMINED:
            if path != "page.bleed":
                r.add_warning(RULE_UNDETERMINED,
                              f"参数未确定，Renderer 必须走 fallback 或人工确认：{sv.notes}",
                              path)
            continue
        # 低置信度
        if sv.confidence == CONF_LOW:
            r.add_warning(RULE_LOW_CONFIDENCE,
                          f"参数置信度为 low，取值={sv.value!r}",
                          path, actual=sv.value)
        # 推导值
        if sv.source == SOURCE_DERIVED:
            r.add_warning(RULE_DERIVED,
                          f"推导值（非知识库明文），取值={sv.value!r} {sv.unit}",
                          path, actual=sv.value)
        # 负值扫描（只对间距类参数）
        if isinstance(sv.value, (int, float)) and sv.value < 0 \
                and any(h in path for h in _SPACING_PATH_HINTS):
            r.add_error(RULE_NEGATIVE_SPACING,
                        f"间距类参数不允许为负值：{sv.value}{sv.unit}",
                        path, expected=">= 0", actual=sv.value)

    # 裸字符串 "undetermined"（如 weight="undetermined"）
    for path, val in _walk_bare_strings(spec):
        r.add_warning(RULE_UNDETERMINED,
                      "字符串字段未确定（未拿到知识库依据）", path)

    # --- WARNING 专项：P2 bleed 未确定 ---
    if page.bleed.is_undetermined:
        r.add_warning(RULE_BLEED_UNDETERMINED,
                      f"P2 bleed 未确定：{page.bleed.notes}；"
                      "在知识库补齐前 Renderer 必须采用非出血实现",
                      "page.bleed")

    # --- WARNING 专项：P2 图标走 fallback ---
    sec = spec.section
    if sec.title_style == TITLE_ICON and sec.icon.resource.is_undetermined:
        r.add_warning(RULE_ICON_FALLBACK,
                      f"语义图标资源未确定，实际将回退到 "
                      f"{sec.icon.fallback}：{sec.icon.resource.notes}",
                      "section.icon.resource",
                      expected="confirmed icon resource",
                      actual=sec.icon.fallback)

    # --- WARNING 专项：照片配置了 fallback（圆形等未验证形态）---
    if spec.photo.enabled and spec.photo.fallback is not None:
        r.add_warning(RULE_PHOTO_FALLBACK,
                      f"照片主形态为 {spec.photo.display_shape}，"
                      f"若 DOCX/WPS 渲染不稳定将降级为 {spec.photo.fallback.container}",
                      "photo.fallback",
                      expected="primary shape verified",
                      actual=spec.photo.fallback.container)

    # --- ERROR: 表宽必须在有效区域内（数值可用时才检查）---
    pw = _num(page.width_cm)
    ml, mr = _num(page.margins.left), _num(page.margins.right)
    if pw is not None and ml is not None and mr is not None:
        content_w = pw - ml - mr
        if content_w <= 0:
            r.add_error(RULE_TABLE_WIDTH,
                        f"有效内容宽={content_w:.2f}cm，左右边距之和超过页宽",
                        "page.margins", expected="left+right < page width",
                        actual=f"{content_w:.2f}cm")
        else:
            colw = spec.grid.column_widths_cm
            nums = colw.value if isinstance(colw.value, (list, tuple)) else None
            if nums and all(isinstance(x, (int, float)) for x in nums):
                total = sum(float(x) for x in nums)
                if total > content_w + 0.01:
                    r.add_error(RULE_TABLE_WIDTH,
                                f"列宽之和 {total:.2f}cm 超过有效区域 {content_w:.2f}cm；"
                                f"表宽必须始终 = {cons.table_width_rule}",
                                "grid.column_widths_cm",
                                expected=f"<= {content_w:.2f}cm",
                                actual=f"{total:.2f}cm")

    # --- ERROR: 照片声明尺寸必须与声明比例一致（防拉伸）---
    if spec.photo.enabled:
        w, h = _num(spec.photo.width), _num(spec.photo.height)
        ar = _num(spec.photo.aspect_ratio)
        if w is not None and h is not None and ar is not None and h > 0:
            actual_ratio = w / h
            if abs(actual_ratio - ar) > _ASPECT_TOLERANCE:
                r.add_error(RULE_PHOTO_ASPECT,
                            f"照片宽高比 {actual_ratio:.3f} 与声明 aspect_ratio "
                            f"{ar:.3f} 不一致；禁止非等比放置",
                            "photo",
                            expected=f"ratio≈{ar}",
                            actual=f"{actual_ratio:.3f}")

    # --- ERROR: 浮动定位合法性（Golden Sample CL-01）---
    pf = getattr(spec.photo, "floating", None)
    if pf is not None:
        if not isinstance(pf.enabled, bool):
            r.add_error(RULE_PHOTO_FLOATING,
                        "photo.floating.enabled 必须为布尔值",
                        "photo.floating.enabled",
                        expected="bool", actual=type(pf.enabled).__name__)
        elif pf.enabled and not spec.photo.enabled:
            r.add_error(RULE_PHOTO_FLOATING,
                        "photo.floating.enabled=True 要求 photo.enabled=True；"
                        "停用照片时不得单独启用浮动",
                        "photo.floating.enabled",
                        expected="photo.enabled=True", actual=False)
        if pf.enabled:
            if pf.position_h not in _PHOTO_FLOAT_H_REL:
                r.add_error(RULE_PHOTO_FLOATING,
                            f"floating.position_h={pf.position_h!r} 不在已验证锚点 "
                            f"{sorted(_PHOTO_FLOAT_H_REL)} 内",
                            "photo.floating.position_h",
                            expected=sorted(_PHOTO_FLOAT_H_REL),
                            actual=pf.position_h)
            if pf.position_v not in _PHOTO_FLOAT_V_REL:
                r.add_error(RULE_PHOTO_FLOATING,
                            f"floating.position_v={pf.position_v!r} 不在已验证锚点 "
                            f"{sorted(_PHOTO_FLOAT_V_REL)} 内",
                            "photo.floating.position_v",
                            expected=sorted(_PHOTO_FLOAT_V_REL),
                            actual=pf.position_v)
            for axis, sv in (("x", pf.offset_x_cm), ("y", pf.offset_y_cm)):
                if sv is None or sv.is_undetermined:
                    continue
                v = sv.value if isinstance(sv.value, (int, float)) else None
                if v is None or v < 0:
                    r.add_error(RULE_PHOTO_FLOATING,
                                f"floating.offset_{axis}_cm 必须为非负数值"
                                f"（当前={sv.value!r}）",
                                f"photo.floating.offset_{axis}_cm",
                                expected=">= 0 cm", actual=sv.value)

    # --- ERROR: 照片边框合法性（Golden Sample CL-01）---
    pbd = getattr(spec.photo, "border", None)
    if pbd is not None:
        bw = _num(pbd.width_pt)
        color_val = pbd.color.value if isinstance(pbd.color, Sourced) else None
        if bw is None or bw < 0:
            r.add_error(RULE_PHOTO_BORDER,
                        f"photo.border.width_pt 必须为非负数值（当前={pbd.width_pt.value!r}）",
                        "photo.border.width_pt",
                        expected=">= 0 pt", actual=pbd.width_pt.value)
        elif bw > 0:
            color_ok = (isinstance(color_val, str)
                        and len(color_val) == 7
                        and color_val.startswith("#")
                        and all(c in _HEX_COLOR_CHARS for c in color_val[1:]))
            if not color_ok:
                r.add_error(RULE_PHOTO_BORDER,
                            f"photo.border.color 必须为 #RRGGBB（当前={color_val!r}）",
                            "photo.border.color",
                            expected="#RRGGBB", actual=color_val)

    # --- WARNING（非阻断）：字段消费契约（Phase 2B-2）---
    # Spec 显式设置了 enabled / 可执行定值，但消费矩阵登记该字段当前无
    # Renderer 消费点。只暴露「写了但没人读」的契约缺口：
    #   - 不影响 valid，永远不升级为 ERROR；
    #   - 不重复 undetermined / icon_fallback 等既有 WARNING；
    #   - 判定口径见 design/consumption.py 评估器。
    for finding in evaluate_unconsumed(spec):
        r.add_warning(
            RULE_UNCONSUMED_SPEC_FIELD,
            f"字段已显式设置但当前 Renderer 无消费点：{finding.message}",
            finding.path, actual=finding.actual)

    return r
