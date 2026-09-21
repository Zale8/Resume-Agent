# -*- coding: utf-8 -*-
"""job_spec.py — ``design.json``（本份 Design Decision 的机器可读载体）→ DesignSpec。

为什么要有这个文件
------------------
审计（docs/architecture/audit_2026-09-21_root_cause.md §R3）指出：规则要求
「每次重新设计」，但**设计决策的落盘载体被堵死**（agent_entry §5.1「对话内
明确即可，不新建任何决策文件」），于是流程上唯一能留存的实物就是**上一份的
临时脚本** —— 「照抄上一份」不是懈怠，而是当前结构下的必然输出。

本模块给出机制上的解法：把本份 Design Decision 写进**该岗位目录下的
``design.json``**，由 ``gen.py build`` 读取。它：

* 让「本份设计」可复现、可 diff、可追溯（不再依赖对话记忆或旧脚本）；
* 因为**必须随每份简历新建**（``gen.py build`` 缺文件直接拒绝，无默认兜底），
  从机制上关掉「默默套用上一份」这条路；
* 取值**全部显式**：只允许出现本文件定义的键，写错键名直接报错，
  不会静默忽略（与 content_parser 的「不静默丢内容」同一条纪律）。

它不是「模板库」：``design.json`` 只描述**这一份**取舍，产品代码里没有
任何默认 design 值，也没有从历史 design.json 继承的通道。

只描述「怎么设计」，不含任何个人事实。
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .assembly import assemble_job_spec, color_delta_from_roles, page_delta_from_margins
from .presets import build_p1_spec, build_p2_spec, build_p3_spec
from .spec import (
    PARADIGM_P1,
    PARADIGM_P2,
    Sourced,
)
from .validator import validate_spec

__all__ = [
    "JobSpecError",
    "PARADIGM_ALIASES",
    "DESIGN_TEMPLATE",
    "load_design",
    "design_to_spec",
    "load_job_spec",
]


class JobSpecError(ValueError):
    """design.json 缺失 / 结构非法 / 取值越界时抛出（消息面向使用者）。"""


# 范式别名 → 内部范式常量
PARADIGM_ALIASES: Dict[str, str] = {
    "p1": PARADIGM_P1,
    "banner": PARADIGM_P1,
    "banner_card": PARADIGM_P1,
    PARADIGM_P1: PARADIGM_P1,
    "p2": PARADIGM_P2,
    "sidebar": PARADIGM_P2,
    "two_column_sidebar": PARADIGM_P2,
    PARADIGM_P2: PARADIGM_P2,
    "p3": "p3_minimal_editorial",
    "minimal": "p3_minimal_editorial",
    "single_column_minimal": "p3_minimal_editorial",
    "p3_minimal_editorial": "p3_minimal_editorial",
}

_BUILDERS = {
    PARADIGM_P1: build_p1_spec,
    PARADIGM_P2: build_p2_spec,
    "p3_minimal_editorial": build_p3_spec,
}

# 每个顶层键的合法子键（None = 该键是标量/列表，无子键）。
# 严格白名单：写错键名必须报错，不能静默忽略 —— 否则「设计改了但没生效」
# 会变成新的静默失败源。
_ALLOWED_KEYS: Dict[str, Optional[Tuple[str, ...]]] = {
    "paradigm": None,
    "design_intent": None,
    "notes": None,
    "target_pages": None,
    "margins_cm": None,
    "colors": ("accent", "hairline", "page_background", "ink", "muted", "paper"),
    "typography": ("body_size", "body_line_spacing"),
    "section": ("spacing_before", "divider_to_first_line", "title_spacing_after",
                "divider_spacing_before", "summary_spacing_after",
                "education_spacing_after", "divider"),
    "experience": ("bullet_spacing_after", "entry_spacing", "entry_spacing_after"),
    "grid": ("identity_band_ratio", "column_ratio"),
    "density": ("level",),
    "photo": ("enabled", "position", "width_cm", "height_cm",
              "offset_x_cm", "offset_y_cm", "position_h", "position_v",
              "border_color", "border_width_pt", "floating"),
}
_ALLOWED_DIVIDER_KEYS = ("line_height", "border_space")

# 逐份必填：这些缺了就不是「一份完整的设计决策」，必须显式写出来。
REQUIRED_KEYS = ("paradigm", "design_intent")

# 设计决策模板：缺 design.json 时打印给用户填（不是产品默认值，只是留白）。
DESIGN_TEMPLATE: Dict[str, Any] = {
    "_说明": [
        "本文件是本份简历的 Design Decision（机器可读），必须**每份新建**。",
        "paradigm 与 design_intent 为必填；其余键不写＝沿用该范式 Preset。",
        "键名只允许出现本模板里列出的；写错键名会直接报错（不静默忽略）。",
        "配色请用 #RRGGBB；页边距顺序 (上, 下, 左, 右) 单位 cm。",
    ],
    "paradigm": "p3",
    "design_intent": "【本份设计的意图，一句话，必填】",
    "target_pages": 1,
    "margins_cm": [1.358, 1.372, 1.499, 1.182],
    "colors": {"accent": "#1F3A5F", "hairline": "#1F3A5F"},
    "typography": {"body_size": 9.0, "body_line_spacing": 1.2},
    "section": {
        "spacing_before": 10,
        "divider_to_first_line": 4,
        "divider": {"line_height": 2, "border_space": 0},
    },
    "experience": {"bullet_spacing_after": 6, "entry_spacing": 14,
                   "entry_spacing_after": 1},
    "photo": {"enabled": False},
}


def _fail(msg: str) -> None:
    raise JobSpecError(msg)


def _num(value, *, key: str, lo: Optional[float] = None,
         hi: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"design.json 的 {key} 必须是数字，收到 {value!r}")
    v = float(value)
    if lo is not None and v < lo:
        _fail(f"design.json 的 {key}={v} 小于下限 {lo}")
    if hi is not None and v > hi:
        _fail(f"design.json 的 {key}={v} 大于上限 {hi}")
    return v


def _hex(value, *, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"design.json 的 {key} 必须是非空 #RRGGBB 字符串，收到 {value!r}")
    v = value.strip()
    if not v.startswith("#") or len(v) != 7:
        _fail(f"design.json 的 {key}={v!r} 不是 #RRGGBB 形式")
    return v


def _check_unknown(node: Dict[str, Any], allowed: Tuple[str, ...], *,
                   where: str) -> None:
    """拒绝未定义的键（写错键名不得被静默忽略）。

    ``_`` 开头的键视为注释（JSON 无注释语法，这是通行约定），一律忽略。
    """
    unknown = [k for k in node if k not in allowed and not str(k).startswith("_")]
    if unknown:
        _fail(f"design.json 的 {where} 出现未定义的键：{unknown}；"
              f"允许的键：{list(allowed)}（写错键名不会被静默忽略）")


# 模板占位符标记：占位符原样提交视为「没写设计意图」，必须拒绝
_PLACEHOLDER_MARKS = ("【", "】", "待填", "TODO", "todo")


def _guard_intent(text: str) -> str:
    note = (text or "").strip()
    if not note:
        _fail("design.json 的 design_intent 不能为空："
              "它是本份设计与上一份区别的唯一书面依据")
    if any(mark in note for mark in _PLACEHOLDER_MARKS):
        _fail(f"design.json 的 design_intent 仍是模板占位符：{note!r}；"
              f"请写成本份的实际设计意图（范式 / 配色 / 照片 / 布局取舍）")
    return note


def load_design(path) -> Dict[str, Any]:
    """读取并校验 design.json 的结构（不做语义到 Spec 的映射）。"""
    p = Path(path)
    if not p.is_file():
        _fail(f"找不到本份设计决策文件：{p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"{p} 不是合法 JSON：{exc}")
    if not isinstance(raw, dict):
        _fail(f"{p} 的顶层必须是对象（{{...}}），收到 {type(raw).__name__}")

    _check_unknown(raw, tuple(_ALLOWED_KEYS), where="顶层")
    for key, sub in _ALLOWED_KEYS.items():
        if sub is None or key not in raw:
            continue
        if not isinstance(raw[key], dict):
            _fail(f"design.json 的 {key} 必须是对象（{{...}}）")
        _check_unknown(raw[key], sub, where=key)
    divider = (raw.get("section") or {}).get("divider")
    if divider is not None:
        if not isinstance(divider, dict):
            _fail("design.json 的 section.divider 必须是对象")
        _check_unknown(divider, _ALLOWED_DIVIDER_KEYS, where="section.divider")

    missing = [k for k in REQUIRED_KEYS if not raw.get(k)]
    if missing:
        _fail(f"design.json 缺必填项：{missing}。"
              f"paradigm 决定范式；design_intent 记录本份设计意图"
              f"（没有它就无法判断这份设计与上一份的区别）。")
    _guard_intent(str(raw["design_intent"]))
    if str(raw["paradigm"]).lower() not in PARADIGM_ALIASES \
            and raw["paradigm"] not in PARADIGM_ALIASES:
        _fail(f"design.json 的 paradigm={raw['paradigm']!r} 不认识；"
              f"可选：p1 / p2 / p3")
    return raw


def design_to_spec(design: Dict[str, Any]):
    """把已校验的 design.json 字典映射为 **已通过 validate_spec 的** DesignSpec。"""
    paradigm = PARADIGM_ALIASES.get(str(design["paradigm"]).lower()) \
        or PARADIGM_ALIASES.get(design["paradigm"])
    if paradigm is None:
        _fail(f"design.json 的 paradigm={design['paradigm']!r} 不认识")
    notes = str(design.get("design_intent", "")).strip()
    base = _BUILDERS[paradigm]()

    kwargs: Dict[str, Any] = {}

    # --- 页面：边距（同步派生 safe_area / content_width）---
    if "margins_cm" in design:
        margins = design["margins_cm"]
        if not isinstance(margins, (list, tuple)) or len(margins) != 4:
            _fail("design.json 的 margins_cm 必须是 (上, 下, 左, 右) 四元组")
        vals = [_num(v, key="margins_cm[]", lo=0.0, hi=10.0) for v in margins]
        kwargs["page_delta"] = page_delta_from_margins(
            base.page, vals,
            notes=notes or "本份 Design Decision",
            target_pages=int(design.get("target_pages", 0)) or None)

    # --- 配色 ---
    if "colors" in design:
        c = design["colors"]
        roles = {
            "accent": c.get("accent"),
            "hairline": c.get("hairline"),
            "page_background": c.get("page_background"),
            "ink": c.get("ink"),
            "muted": c.get("muted"),
            "paper": c.get("paper"),
        }
        checked = {k: _hex(v, key=f"colors.{k}") for k, v in roles.items()
                   if v is not None}
        if checked:
            kwargs["color_delta"] = color_delta_from_roles(base.colors,
                                                           notes=notes, **checked)

    # --- 字体 / 行距 ---
    if "typography" in design:
        t = design["typography"]
        typ = base.typography
        if "body_size" in t:
            size = _num(t["body_size"], key="typography.body_size", lo=9.0, hi=14.0)
            typ = replace(typ, body_size=Sourced.kv1(
                size, "pt", notes=f"{notes}｜本份正文字号"))
        if "body_line_spacing" in t:
            ls = _num(t["body_line_spacing"], key="typography.body_line_spacing",
                      lo=1.0, hi=2.0)
            typ = replace(typ, line_spacing=replace(
                typ.line_spacing,
                body=Sourced.kv1(ls, "ratio", notes=f"{notes}｜本份正文行距")))
        if typ is not base.typography:
            kwargs["typography_delta"] = typ

    # --- 板块间距 / 分割线 ---
    if "section" in design:
        s = design["section"]
        sec = base.section
        field_map = {
            "spacing_before": "spacing_before",
            "divider_to_first_line": "divider_to_first_line",
            "title_spacing_after": "title_spacing_after",
            "divider_spacing_before": "divider_spacing_before",
            "summary_spacing_after": "summary_spacing_after",
            "education_spacing_after": "education_spacing_after",
        }
        for key, attr in field_map.items():
            if key not in s:
                continue
            val = _num(s[key], key=f"section.{key}", lo=0.0, hi=72.0)
            sec = replace(sec, **{attr: Sourced.kv1(
                val, "pt", notes=f"{notes}｜本份 {key}")})
        if "divider" in s:
            d = s["divider"] or {}
            dv = sec.divider
            if "line_height" in d:
                val = _num(d["line_height"], key="section.divider.line_height",
                           lo=0.5, hi=24.0)
                dv = replace(dv, line_height=Sourced.kv1(
                    val, "pt", notes=f"{notes}｜分割线空段行高"))
            if "border_space" in d:
                val = _num(d["border_space"], key="section.divider.border_space",
                           lo=0.0, hi=24.0)
                dv = replace(dv, border_space=Sourced.kv1(
                    val, "pt", notes=f"{notes}｜分割线边框间距"))
            if dv is not sec.divider:
                sec = replace(sec, divider=dv)
        if sec is not base.section:
            kwargs["section_delta"] = sec

    # --- 经历条目节奏 ---
    if "experience" in design:
        e = design["experience"]
        exp = base.experience
        field_map = {
            "bullet_spacing_after": "bullet_spacing_after",
            "entry_spacing": "entry_spacing",
            "entry_spacing_after": "entry_spacing_after",
        }
        for key, attr in field_map.items():
            if key not in e:
                continue
            val = _num(e[key], key=f"experience.{key}", lo=0.0, hi=72.0)
            exp = replace(exp, **{attr: Sourced.kv1(
                val, "pt", notes=f"{notes}｜本份 {key}")})
        if exp is not base.experience:
            kwargs["experience_delta"] = exp

    # --- 栅格（身份区列比）---
    if "grid" in design:
        g = design["grid"]
        grid = base.grid
        if "identity_band_ratio" in g:
            ratio = g["identity_band_ratio"]
            if not isinstance(ratio, (list, tuple)) or len(ratio) < 2:
                _fail("design.json 的 grid.identity_band_ratio 至少要有 2 个正数")
            vals = [_num(v, key="grid.identity_band_ratio[]", lo=0.01) for v in ratio]
            total = sum(vals)
            grid = replace(grid, identity_band_ratio=[v / total for v in vals])
        if "column_ratio" in g:
            ratio = g["column_ratio"]
            if not isinstance(ratio, (list, tuple)) or len(ratio) < 2:
                _fail("design.json 的 grid.column_ratio 至少要有 2 个正数")
            vals = [_num(v, key="grid.column_ratio[]", lo=0.01) for v in ratio]
            total = sum(vals)
            grid = replace(grid, column_ratio=[v / total for v in vals])
        if grid is not base.grid:
            kwargs["grid_delta"] = grid

    # --- 密度档 ---
    if "density" in design:
        d = design["density"]
        if "level" in d:
            level = str(d["level"]).strip().lower()
            if level not in ("compact", "medium", "spacious"):
                _fail("design.json 的 density.level 只能是 compact / medium / spacious")
            kwargs["density_delta"] = replace(
                base.density, level=level,
                body_line_spacing=(kwargs.get("typography_delta")
                                   or base.typography).line_spacing.body)

    # --- 照片 ---
    if "photo" in design:
        p = design["photo"]
        enabled = bool(p.get("enabled", False))
        photo = replace(base.photo, enabled=enabled)
        if enabled:
            if "width_cm" not in p or "height_cm" not in p:
                _fail("design.json 的 photo 启用时必须给 width_cm 与 height_cm"
                      "（照片不得拉伸变形，宽高必须显式）")
            w = _num(p["width_cm"], key="photo.width_cm", lo=1.0, hi=10.0)
            h = _num(p["height_cm"], key="photo.height_cm", lo=1.0, hi=12.0)
            photo = replace(
                photo,
                position=str(p.get("position", "floating_top_right")),
                width=Sourced.kv1(w, "cm", notes=f"{notes}｜照片宽"),
                height=Sourced.kv1(h, "cm", notes=f"{notes}｜照片高"),
                aspect_ratio=Sourced.kv1(round(w / h, 4), "ratio",
                                         notes="由本份宽高派生（禁变形）"),
            )
            if p.get("floating", True):
                from .spec import PhotoFloating
                photo = replace(photo, floating=PhotoFloating(
                    enabled=True,
                    position_h=str(p.get("position_h", "column")),
                    position_v=str(p.get("position_v", "page")),
                    offset_x_cm=Sourced.kv1(
                        _num(p.get("offset_x_cm", 0.0), key="photo.offset_x_cm",
                             lo=0.0, hi=21.0), "cm"),
                    offset_y_cm=Sourced.kv1(
                        _num(p.get("offset_y_cm", 0.0), key="photo.offset_y_cm",
                             lo=0.0, hi=29.7), "cm"),
                ))
            border_color = p.get("border_color")
            border_w = p.get("border_width_pt")
            if border_color is not None or border_w is not None:
                if border_color is None or border_w is None:
                    _fail("design.json 的 photo 边框要同时给 border_color 与 "
                          "border_width_pt")
                from .spec import PhotoBorder
                photo = replace(photo, border=PhotoBorder(
                    color=Sourced.kv1(_hex(border_color, key="photo.border_color"),
                                      "hex"),
                    width_pt=Sourced.kv1(
                        _num(border_w, key="photo.border_width_pt",
                             lo=0.0, hi=12.0), "pt")))
        kwargs["photo_delta"] = photo

    spec = assemble_job_spec(base, **kwargs) if kwargs else base

    # 把本份意图写进 Spec（可追溯；Spec 本来就带 design_intent 槽位）
    if notes or design.get("notes"):
        spec = replace(spec, design_intent=notes or str(design.get("notes", "")))

    result = validate_spec(spec)
    if result.errors:
        detail = "\n".join("  ✗ " + e.render() for e in result.errors)
        _fail("本份设计未通过 validate_spec：\n" + detail)
    return spec


def load_job_spec(design_path):
    """``design.json`` 路径 → (DesignSpec, 原始字典)。"""
    raw = load_design(design_path)
    return design_to_spec(raw), raw
