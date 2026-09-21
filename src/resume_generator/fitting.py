# -*- coding: utf-8 -*-
"""fitting.py — 渲染 → 实测 → 确定性收敛 → QA 报告 的 auto-fit 引擎。

为什么需要它
------------
审计（docs/architecture/audit_2026-09-21_root_cause.md §R4）指出：八个质量
维度里**只有「照片变形」有端到端自动化**，页数/末行/寡行/溢出/边距安全区
全靠人肉发现；而唯一的估算工具 ``scripts/check_pages.py`` 本身有三个硬缺陷
（只认 ``wp:inline`` 漏检浮动照片、单位换算错 14 倍、溢出时仍返回 0）。
于是每份简历都要「生成 → 翻页看 → 手调间距 → 再生成」反复救火。

本模块把这条回路做成产品能力：

    render(blocks, spec) → measure(docx) → 达标？
        ├─ 是 → 出 QA 报告，结束
        └─ 否 → 沿**确定性收敛梯**降一档 spec，重来
                 梯子用尽仍不达标 → 停，给出**溢出归因**（该删内容，
                 不是该继续压字号）

收敛梯顺序（先动最不伤观感的，规范原则见 resume_writer.md Phase 5）
------------------------------------------------------------------
    1. 间距   settings.section / experience 的各段前段后距
    2. 行距   typography.line_spacing.body / density.body_line_spacing
    3. 边距   page.margins（含 safe_area 同步派生）
    4. 字号   **默认禁用**：规范明文「绝不靠缩字号硬塞」（正文不低于 9pt），
              要启用必须显式 ``allow_font_reduction=True``

每档内按固定比例（默认 0.5 → 1.0，即先收到「剩余可压缩量的一半」再收到下限）
探两轮，全程无随机、无启发式搜索 —— 同一份输入必然得到同一份输出。

实测与估算
----------
``measure_pages`` 优先用 Word COM ``ComputeStatistics(2)`` 实测（Windows +
pywin32）；不可用时退化为**修正后**的高度估算，并在报告里明确标注
``pages_source``，绝不把估算伪装成实测。

单位（本模块修正了 check_pages.py 的历史错误）
--------------------------------------------
OOXML 中 ``wp:extent`` 的 ``cx``/``cy`` 单位是 EMU：
    1 cm = 360000 EMU      1 pt = 12700 EMU
历史实现写成 ``int(cx) / 12700 / 2.54 * 72 / 20 * 10``（≈ ×14.17），
把照片高度放大了十几倍。

本模块只读 DOCX / 不写简历库；不含任何个人事实。
"""
from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "FitError",
    "Estimate",
    "PhotoCheck",
    "QaReport",
    "FitStep",
    "FitResult",
    "estimate_height",
    "measure_pages",
    "audit",
    "fit",
    "declared_min_font_pt",
    "STAGE_ORDER",
    "EMU_PER_CM",
    "EMU_PER_PT",
]

EMU_PER_CM = 360000
EMU_PER_PT = 12700

# 收敛梯的下限（规范允许的最小值；到此为止，不再往下压）
SECTION_SPACING_BEFORE_FLOOR_PT = 4.0
SPACING_FLOOR_PT = 0.0
LINE_SPACING_FLOOR = 1.0
MARGIN_FLOOR_CM = 0.4

# OOXML 的 w:sz 以**半磅**为单位，声明值 8.52pt 落盘即 8.5pt（17 半磅）。
# 比较渲染字号与声明字号时必须容忍这半个半磅的量化误差，否则每份简历
# 都会误报一条「字号越界」。
FONT_QUANTIZATION_TOL_PT = 0.26

# 收敛梯档位顺序（字号档默认不在其中）
STAGE_SPACING = "spacing"
STAGE_LINE = "line_spacing"
STAGE_MARGIN = "margin"
STAGE_FONT = "font_size"
STAGE_ORDER = (STAGE_SPACING, STAGE_LINE, STAGE_MARGIN, STAGE_FONT)

_STAGE_TITLE = {
    STAGE_SPACING: "板块 / 条目间距",
    STAGE_LINE: "正文行距",
    STAGE_MARGIN: "页边距",
    STAGE_FONT: "正文字号",
}


class FitError(RuntimeError):
    """auto-fit 无法继续（渲染失败 / 校验不通过）时抛出。"""


# ---------------------------------------------------------------------------
# 高度估算（修正版）
# ---------------------------------------------------------------------------

@dataclass
class Estimate:
    """按 DOCX 内容估算的高度分解（cm）。"""

    body_cm: float = 0.0
    table_cm: float = 0.0
    photo_cm: float = 0.0
    usable_cm: float = 0.0

    @property
    def total_cm(self) -> float:
        return self.body_cm + self.table_cm + self.photo_cm

    @property
    def overflow_cm(self) -> float:
        return max(0.0, self.total_cm - self.usable_cm)

    @property
    def virtual_pages(self) -> int:
        if self.usable_cm <= 0:
            return 1
        return max(1, int(math.ceil(self.total_cm / self.usable_cm - 1e-9)))

    def render(self) -> str:
        return (f"估算高度 {self.total_cm:.2f}cm / 可用 {self.usable_cm:.2f}cm"
                f"（正文 {self.body_cm:.2f} + 表格 {self.table_cm:.2f}"
                f" + 照片 {self.photo_cm:.2f}）"
                + (f"，溢出 {self.overflow_cm:.2f}cm"
                   if self.overflow_cm > 0 else "，未溢出"))


def _chars_per_line(font_size_pt: float, in_table: bool,
                    width_cm: float = 18.0) -> int:
    """按字号与可用宽度估算每行字符数（中文按正方形字宽）。"""
    if font_size_pt <= 0:
        font_size_pt = 10.0
    char_cm = font_size_pt / 72.0 * 2.54          # 一个汉字的宽度
    base = max(8, int(width_cm / char_cm))
    return max(6, int(base * 0.6)) if in_table else base


def _photo_cm_from_docx(doc) -> float:
    """文档中所有图片的**最大**高度（cm）。

    同时遍历 ``wp:inline`` 与 ``wp:anchor`` —— 后者是本项目的主用形态
    （浮动照片），历史估算器只认 inline，等于对浮动照片完全失明。
    """
    from docx.oxml.ns import qn

    tallest = 0.0
    body = doc.element.body
    for tag in ("wp:inline", "wp:anchor"):
        for node in body.iter(qn(tag)):
            extent = node.find(qn("wp:extent"))
            if extent is None:
                continue
            cy = extent.get("cy")
            if not cy:
                continue
            tallest = max(tallest, int(cy) / EMU_PER_CM)
    return tallest


def estimate_height(docx_path) -> Estimate:
    """估算 DOCX 内容高度与可用高度（cm）。

    这是**估算**，不能替代 Word COM 实测；但它是修正版：
    浮动照片计入、单位换算正确、结果可用于判定溢出。
    """
    from docx import Document

    doc = Document(str(docx_path))
    sec = doc.sections[0]
    usable_h_emu = sec.page_height - sec.top_margin - sec.bottom_margin
    usable_cm = usable_h_emu / EMU_PER_CM
    usable_w_cm = (sec.page_width - sec.left_margin - sec.right_margin) / EMU_PER_CM

    est = Estimate(usable_cm=usable_cm)

    def _para_cm(p, in_table: bool) -> float:
        size = 10.0
        for run in p.runs:
            if run.font.size is not None:
                size = run.font.size.pt
                break
        pf = p.paragraph_format
        line = pf.line_spacing
        if isinstance(line, float):
            line_h = size * line
        elif line is not None:
            line_h = float(line.pt)
        else:
            line_h = size * 1.15
        before = pf.space_before.pt if pf.space_before is not None else 0.0
        after = pf.space_after.pt if pf.space_after is not None else 0.0
        text_len = len(p.text)
        cpl = _chars_per_line(size, in_table, usable_w_cm)
        n_lines = max(1, (text_len + cpl - 1) // cpl) if text_len else 1
        return (line_h * n_lines + before + after) / 72.0 * 2.54

    for p in doc.paragraphs:
        est.body_cm += _para_cm(p, in_table=False)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    est.table_cm += _para_cm(p, in_table=True)
    est.photo_cm = _photo_cm_from_docx(doc)
    return est


# ---------------------------------------------------------------------------
# 实测（Word COM）
# ---------------------------------------------------------------------------

def measure_pages(docx_path, *, fallback: bool = True):
    """实测页数。返回 ``(pages, source)``。

    source 取值：
        ``"word_com"``  —— Word/WPS COM 实测（可信）
        ``"estimate"``  —— 无 COM，按高度估算的「虚拟页数」（明确标注）
        ``"unavailable"`` —— 估不出来（docx 打不开）
    """
    from .layout_kit import count_pages_com

    pages = count_pages_com(docx_path)
    if pages is not None:
        return pages, "word_com"
    if not fallback:
        return None, "unavailable"
    try:
        return estimate_height(docx_path).virtual_pages, "estimate"
    except Exception:
        return None, "unavailable"


# ---------------------------------------------------------------------------
# QA 报告
# ---------------------------------------------------------------------------

@dataclass
class PhotoCheck:
    count: int = 0
    floating: int = 0
    inline: int = 0
    declared_ratio: Optional[float] = None
    rendered_ratio: Optional[float] = None
    distorted: bool = False
    exact_line_with_image: int = 0

    @property
    def ok(self) -> bool:
        return (not self.distorted) and self.exact_line_with_image == 0

    def render(self) -> str:
        if self.count == 0:
            return "无照片"
        ratio = ("—" if self.rendered_ratio is None
                 else f"{self.rendered_ratio:.4f}")
        decl = ("—" if self.declared_ratio is None
                else f"{self.declared_ratio:.4f}")
        bits = [f"{self.count} 张（浮动 {self.floating} / 内联 {self.inline}）",
                f"比例 声明 {decl} vs 实际 {ratio}"]
        if self.distorted:
            bits.append("⚠️ 变形")
        if self.exact_line_with_image:
            bits.append(f"⚠️ {self.exact_line_with_image} 个图片段落用了 exact 行高")
        return "；".join(bits)


@dataclass
class QaReport:
    """八维质量报告（对应审计 §R4 的八个维度）。"""

    pages: Optional[int] = None
    pages_source: str = "unavailable"
    target_pages: int = 1
    estimate: Optional[Estimate] = None
    last_line_chars: Optional[int] = None
    last_line_fill: Optional[float] = None
    widow: bool = False
    hairlines: int = 0
    photo: PhotoCheck = field(default_factory=PhotoCheck)
    min_font_pt: Optional[float] = None
    declared_min_pt: Optional[float] = None
    font_floor_pt: float = 9.0
    margins_cm: Optional[Tuple[float, float, float, float]] = None
    safe_area_ok: bool = True
    bullet_count: int = 0
    entry_count: int = 0
    exact_line_paragraphs: int = 0

    # -- 判定 ---------------------------------------------------------------

    @property
    def pages_ok(self) -> bool:
        return self.pages is not None and self.pages <= self.target_pages

    @property
    def font_ok(self) -> bool:
        """渲染出来的最小字号不得低于 **Spec 声明的最小字号**。

        为什么不用 9pt 直接比：正文的 9pt 下限只管**正文**，而
        header / contact / 侧栏等元信息 run 按规范本就允许更小
        （audit §R4 记的正是这个盲区：那些 run 此前完全不在校验范围内）。
        这里改成「渲染值 vs Spec 声明值」——能抓出渲染器超出声明偷偷缩小，
        又不会把规范内的小字号误判成缺陷。
        """
        if self.min_font_pt is None:
            return True
        ref = self.declared_min_pt if self.declared_min_pt else self.font_floor_pt
        return self.min_font_pt + FONT_QUANTIZATION_TOL_PT >= ref

    @property
    def overflow_cm(self) -> float:
        return self.estimate.overflow_cm if self.estimate else 0.0

    @property
    def problems(self) -> List[str]:
        out: List[str] = []
        if self.pages is None:
            out.append("页数无法测量（无 Word COM 且无法估算）")
        elif self.pages > self.target_pages:
            out.append(
                f"页数 {self.pages} 超过目标 {self.target_pages}"
                + (f"（估算溢出 {self.overflow_cm:.2f}cm）"
                   if self.overflow_cm > 0
                   else "（高度估算未捕到溢出——估算偏乐观，**以实测页数为准**）"))
        if not self.font_ok:
            out.append(
                f"字号 {self.min_font_pt:.2f}pt 低于 Spec 声明的最小字号 "
                f"{self.declared_min_pt:.2f}pt"
                + (f"（正文下限 {self.font_floor_pt}pt）"
                   if self.declared_min_pt else ""))
        if self.widow:
            out.append(
                f"末行仅 {self.last_line_chars} 字（寡行，建议回填或精简上一行）")
        if self.photo.distorted:
            out.append("照片比例与声明不符（变形）")
        if self.photo.exact_line_with_image:
            out.append(
                f"{self.photo.exact_line_with_image} 个含图片的段落使用了 exact 行高"
                "（会裁切图片，验收规则 4）")
        if not self.safe_area_ok:
            out.append("边距小于安全下限（safe_area 与 margins 不一致或过窄）")
        return out

    @property
    def ok(self) -> bool:
        return not self.problems

    def dimension_table(self) -> List[Tuple[str, str, str]]:
        """(维度, 判定, 明细) —— 八维逐项，供人类对照。"""
        rows = [
            ("页数", "✅" if self.pages_ok else "❌",
             "—" if self.pages is None
             else f"{self.pages}（来源 {self.pages_source}，目标 {self.target_pages}）"),
            ("溢出", "✅" if self.overflow_cm <= 0 else "❌",
             "—" if self.estimate is None
             else f"{self.overflow_cm:.2f}cm"
             + ("（估算未捕到，以页数为准）"
                if self.overflow_cm <= 0 and self.pages is not None
                and self.pages > self.target_pages else "")),
            ("末行位置", "✅" if not self.widow else "❌",
             "—" if self.last_line_fill is None
             else f"填充 {self.last_line_fill * 100:.0f}%"
                  f"（{self.last_line_chars} 字）"),
            ("寡行", "✅" if not self.widow else "❌",
             "末行 ≥3 字" if not self.widow else f"末行 {self.last_line_chars} 字"),
            ("内容密度", "ℹ️",
             f"{self.entry_count} 个经历条目 / {self.bullet_count} 条 bullet"),
            ("边距安全区", "✅" if self.safe_area_ok else "❌",
             "—" if self.margins_cm is None else
             "上下左右 " + "/".join(f"{v:.2f}" for v in self.margins_cm) + "cm"),
            ("字号下限", "✅" if self.font_ok else "❌",
             "—" if self.min_font_pt is None else
             f"最小 {self.min_font_pt:.2f}pt"
             + (f" / 声明下限 {self.declared_min_pt:.2f}pt"
                if self.declared_min_pt else "")
             + f"（正文下限 {self.font_floor_pt}pt）"),
            ("照片", "✅" if self.photo.ok else "❌", self.photo.render()),
        ]
        return rows

    def render(self, *, title: str = "排版 QA 报告") -> str:
        width = 74
        lines = [title, "═" * width]
        for name, mark, detail in self.dimension_table():
            lines.append(f"  {mark} {name:<10} {detail}")
        lines.append("─" * width)
        if self.ok:
            lines.append("  结论：达标 ✅")
        else:
            lines.append(f"  结论：不达标 ❌（{len(self.problems)} 项）")
            for p in self.problems:
                lines.append(f"      · {p}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------

def _last_paragraph_stats(doc) -> Tuple[Optional[int], Optional[float]]:
    """末段落的「末行」字数与填充率。"""
    last = None
    for p in doc.paragraphs:
        if p.text.strip():
            last = p
    for table in doc.tables:                      # 表格在内时取最后一行单元格
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if p.text.strip():
                        last = p
    if last is None:
        return None, None
    text = last.text.strip()
    size = 10.0
    for run in last.runs:
        if run.font.size is not None:
            size = run.font.size.pt
            break
    sec = doc.sections[0]
    usable_w_cm = (sec.page_width - sec.left_margin - sec.right_margin) / EMU_PER_CM
    cpl = _chars_per_line(size, in_table=False, width_cm=usable_w_cm)
    n = len(text)
    on_last = n if n <= cpl else (n % cpl or cpl)
    return on_last, min(1.0, on_last / cpl)


def _photo_check(doc, docx_path: Path, declared_ratio: Optional[float]) -> PhotoCheck:
    from docx.oxml.ns import qn

    body = doc.element.body
    check = PhotoCheck(declared_ratio=declared_ratio)
    extents: List[Tuple[int, int]] = []
    for tag, is_float in (("wp:inline", False), ("wp:anchor", True)):
        for node in body.iter(qn(tag)):
            ext = node.find(qn("wp:extent"))
            if ext is None or not ext.get("cx") or not ext.get("cy"):
                continue
            extents.append((int(ext.get("cx")), int(ext.get("cy"))))
            if is_float:
                check.floating += 1
            else:
                check.inline += 1
    check.count = len(extents)
    if extents:
        cx, cy = extents[0]
        if cy:
            check.rendered_ratio = cx / cy
    if (declared_ratio and check.rendered_ratio
            and abs(check.rendered_ratio - declared_ratio)
            > max(0.01, declared_ratio * 0.02)):
        check.distorted = True

    # 含图片的段落不得使用 exact 行高（会按该行高裁切图片）
    for p in doc.paragraphs:
        _scan_exact_with_drawing(p._p)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _scan_exact_with_drawing(p._p)
    check.exact_line_with_image = _PHOTO_EXACT_HITS[0]
    _PHOTO_EXACT_HITS[0] = 0
    return check


_PHOTO_EXACT_HITS = [0]


def _scan_exact_with_drawing(p_el) -> None:
    from docx.oxml.ns import qn

    pPr = p_el.find(qn("w:pPr"))
    if pPr is None:
        return
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None or spacing.get(qn("w:lineRule")) != "exact":
        return
    if p_el.find(qn("w:r")) is not None and any(
            r.find(qn("w:drawing")) is not None for r in p_el.iter(qn("w:r"))):
        _PHOTO_EXACT_HITS[0] += 1


def _min_font_pt(doc) -> Optional[float]:
    sizes: List[float] = []
    for p in doc.paragraphs:
        for run in p.runs:
            if run.font.size is not None and run.text.strip():
                sizes.append(run.font.size.pt)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        if run.font.size is not None and run.text.strip():
                            sizes.append(run.font.size.pt)
    return min(sizes) if sizes else None


def _count_hairlines(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return xml.count("<w:pBdr>") if "w:pBdr" in xml else 0


def declared_min_font_pt(spec) -> Optional[float]:
    """Spec 声明的**全域最小字号**（含 header/contact/侧栏等元信息档）。

    它不是「正文下限」（那个是 ``constraints.minimum_body_font_size_pt``），
    而是「这份设计自称会用到的最小字号」。渲染结果比它还小，说明渲染器
    越过了 Spec，才是真问题。
    """
    if spec is None:
        return None
    typ = getattr(spec, "typography", None)
    if typ is None:
        return None
    vals: List[float] = []
    for attr in ("name_size", "title_size", "organization_size", "role_size",
                 "body_size", "metadata_size", "sidebar_body_size",
                 "sidebar_group_label_size"):
        v = _num(getattr(typ, attr, None))
        if v:
            vals.append(v)
    for extra in (getattr(typ, "header_meta_sizes", None) or []):
        v = _num(extra)
        if v:
            vals.append(v)
    return min(vals) if vals else None


def audit(docx_path, *, spec=None, blocks=None,
          target_pages: Optional[int] = None,
          measurer: Optional[Callable[[Path], Tuple[Optional[int], str]]] = None
          ) -> QaReport:
    """对一份已生成的 DOCX 出八维 QA 报告。

    :param docx_path: 成品 DOCX
    :param spec: 可选 DesignSpec；提供时用它读目标页数 / 字号下限 / 照片声明比例
    :param blocks: 可选 ResumeBlocks；提供时统计条目与 bullet 数量
    :param target_pages: 覆盖目标页数（默认取 spec，其次 1）
    :param measurer: 测页函数（默认 Word COM + 估算）。
        ``fit()`` 会把它自己用的测页器传进来，保证收敛循环与终报口径一致。
    """
    from docx import Document

    path = Path(docx_path)
    report = QaReport()
    if target_pages is not None:
        report.target_pages = int(target_pages)
    elif spec is not None:
        tp = getattr(spec.page.target_pages, "value", None)
        report.target_pages = int(tp) if tp else 1
    else:
        report.target_pages = 1

    if spec is not None:
        report.font_floor_pt = float(
            spec.constraints.minimum_body_font_size_pt or 9.0)
        report.declared_min_pt = declared_min_font_pt(spec)
        try:
            report.margins_cm = (
                float(spec.page.margins.top.value),
                float(spec.page.margins.bottom.value),
                float(spec.page.margins.left.value),
                float(spec.page.margins.right.value),
            )
            report.safe_area_ok = min(report.margins_cm) >= MARGIN_FLOOR_CM
        except (TypeError, ValueError):
            report.margins_cm = None
            report.safe_area_ok = True

    if blocks is not None:
        report.entry_count = len(blocks.internships) + len(blocks.projects)
        report.bullet_count = (
            sum(len(x.bullets) for x in blocks.internships)
            + sum(len(x.bullets) for x in blocks.projects)
            + len(blocks.campus) + len(blocks.skills)
        )

    report.pages, report.pages_source = (measurer or measure_pages)(path)
    try:
        report.estimate = estimate_height(path)
    except Exception:
        report.estimate = None
    if report.pages is None and report.estimate is not None:
        report.pages = report.estimate.virtual_pages
        report.pages_source = "estimate"

    doc = Document(str(path))
    report.last_line_chars, report.last_line_fill = _last_paragraph_stats(doc)
    report.widow = (report.last_line_chars is not None
                    and report.last_line_chars <= 2)
    report.min_font_pt = _min_font_pt(doc)
    report.hairlines = _count_hairlines(path)
    declared = None
    if spec is not None and getattr(spec.photo, "aspect_ratio", None):
        declared = spec.photo.aspect_ratio.value
    report.photo = _photo_check(doc, path, declared)
    report.exact_line_paragraphs = report.photo.exact_line_with_image
    return report


# ---------------------------------------------------------------------------
# 收敛梯
# ---------------------------------------------------------------------------

def _shrink(value: float, floor: float, intensity: float) -> float:
    """把 value 朝 floor 压缩 intensity 比例（0=不动，1=到 floor）。

    结果按 6 位小数量化：否则 ``1.499 - 1.099`` 会得到 ``0.4`` 附近一个
    带极长尾数的浮点值，再压一次尾数又漂向另一侧，使「是否已到下限」的判定
    （``_tunables`` 相等比较）失效。
    """
    if value is None:
        return value
    span = float(value) - float(floor)
    if span <= 0:
        return float(floor)
    return round(float(value) - span * intensity, 6)


def _make_pt(sourced, floor: float, intensity: float):
    """对 pt 数值字段做压缩；None（未声明）保持原样。"""
    from .design import Sourced

    if sourced is None or sourced.value is None:
        return sourced
    shrunk = _shrink(sourced.value, floor, intensity)
    return Sourced.kv1(shrunk, sourced.unit or "pt",
                       notes=f"auto-fit 收敛：{sourced.value}→{shrunk}")


def _num(sourced) -> Optional[float]:
    if sourced is None or getattr(sourced, "value", None) is None:
        return None
    try:
        return float(sourced.value)
    except (TypeError, ValueError):
        return None


def _tunables(spec) -> tuple:
    """收敛梯可动字段的**数值签名**。

    用它判断「这一档是否还能再压」——不能直接比较 DesignSpec 数据类：
    压缩函数即使数值不变（已到下限）也会生成新的 Sourced（notes 不同），
    数据类 ``__eq__`` 会判为不同，循环将永远「有进展」而空转到 max_steps。
    """
    return (
        _num(spec.section.spacing_before),
        _num(spec.section.title_spacing_after),
        _num(spec.section.divider_to_first_line),
        _num(spec.section.divider_spacing_before),
        _num(spec.section.summary_spacing_after),
        _num(spec.section.education_spacing_after),
        _num(spec.experience.bullet_spacing_after),
        _num(spec.experience.entry_spacing),
        _num(spec.experience.entry_spacing_after),
        _num(spec.typography.line_spacing.body),
        _num(spec.density.body_line_spacing),
        _num(spec.page.margins.top),
        _num(spec.page.margins.bottom),
        _num(spec.page.margins.left),
        _num(spec.page.margins.right),
        _num(spec.typography.body_size),
    )


def _spacing_stage(spec, intensity: float):
    sec = spec.section
    new_sec = replace(
        sec,
        spacing_before=_make_pt(sec.spacing_before,
                                SECTION_SPACING_BEFORE_FLOOR_PT, intensity),
        title_spacing_after=_make_pt(sec.title_spacing_after,
                                     SPACING_FLOOR_PT, intensity),
        divider_to_first_line=_make_pt(sec.divider_to_first_line,
                                       SPACING_FLOOR_PT, intensity),
        divider_spacing_before=_make_pt(sec.divider_spacing_before,
                                        SPACING_FLOOR_PT, intensity),
        summary_spacing_after=_make_pt(sec.summary_spacing_after,
                                       SPACING_FLOOR_PT, intensity),
        education_spacing_after=_make_pt(sec.education_spacing_after,
                                         SPACING_FLOOR_PT, intensity),
    )
    exp = spec.experience
    new_exp = replace(
        exp,
        bullet_spacing_after=_make_pt(exp.bullet_spacing_after,
                                      SPACING_FLOOR_PT, intensity),
        entry_spacing=_make_pt(exp.entry_spacing, SPACING_FLOOR_PT, intensity),
        entry_spacing_after=_make_pt(exp.entry_spacing_after,
                                     SPACING_FLOOR_PT, intensity),
    )
    from .design import assemble_job_spec
    return assemble_job_spec(spec, section_delta=new_sec, experience_delta=new_exp)


def _line_stage(spec, intensity: float):
    from .design import assemble_job_spec

    typ = replace(
        spec.typography,
        line_spacing=replace(
            spec.typography.line_spacing,
            body=_make_pt(spec.typography.line_spacing.body,
                          LINE_SPACING_FLOOR, intensity)),
    )
    den = replace(
        spec.density,
        body_line_spacing=_make_pt(spec.density.body_line_spacing,
                                   LINE_SPACING_FLOOR, intensity),
    )
    return assemble_job_spec(spec, typography_delta=typ, density_delta=den)


def _margin_stage(spec, intensity: float):
    from .design import assemble_job_spec, page_delta_from_margins

    m = spec.page.margins
    vals = [float(m.top.value), float(m.bottom.value),
            float(m.left.value), float(m.right.value)]
    shrunk = [_shrink(v, MARGIN_FLOOR_CM, intensity) for v in vals]
    page = page_delta_from_margins(
        spec.page, shrunk,
        notes="auto-fit 收敛梯：本份页边距压缩（fitting.py）")
    return assemble_job_spec(spec, page_delta=page)


def _font_stage(spec, intensity: float):
    from .design import assemble_job_spec

    floor = float(spec.constraints.minimum_body_font_size_pt or 9.0)
    typ = replace(spec.typography,
                  body_size=_make_pt(spec.typography.body_size, floor, intensity))
    return assemble_job_spec(spec, typography_delta=typ)


_STAGE_FUNCS: Dict[str, Callable[[object, float], object]] = {
    STAGE_SPACING: _spacing_stage,
    STAGE_LINE: _line_stage,
    STAGE_MARGIN: _margin_stage,
    STAGE_FONT: _font_stage,
}


@dataclass
class FitStep:
    stage: str
    intensity: float
    pages: Optional[int]
    pages_source: str

    def render(self) -> str:
        title = _STAGE_TITLE.get(self.stage, self.stage)
        return (f"{title} 收到 {self.intensity * 100:.0f}%"
                f" → 页数 {self.pages}（{self.pages_source}）")


@dataclass
class FitResult:
    spec: object
    docx_path: Path
    report: QaReport
    steps: List[FitStep] = field(default_factory=list)
    converged: bool = False
    attribution: str = ""

    def render(self) -> str:
        lines = [self.report.render(title="排版 QA 报告（auto-fit）"),
                 "─" * 74]
        if self.steps:
            lines.append("  收敛过程：")
            for i, s in enumerate(self.steps, 1):
                lines.append(f"      {i}. {s.render()}")
        else:
            lines.append("  收敛过程：（首轮即达标，无需收敛）")
        if self.attribution:
            lines.append("  归因：" + self.attribution)
        lines.append(f"  成品：{self.docx_path}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# auto-fit 主循环
# ---------------------------------------------------------------------------

def _render(blocks, spec, out_path: Path):
    from .skeletons import build_document

    doc = build_document(blocks, design_spec=spec)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return doc


def fit(blocks, spec, out_path, *,
        target_pages: Optional[int] = None,
        allow_font_reduction: bool = False,
        levels: Sequence[float] = (0.5, 1.0),
        max_steps: int = 12,
        measurer: Optional[Callable[[Path], Tuple[Optional[int], str]]] = None,
        on_step: Optional[Callable[[FitStep], None]] = None) -> FitResult:
    """渲染并自动收敛到目标页数，产出成品 + QA 报告。

    :param blocks: ResumeBlocks（内容）
    :param spec: 装配好并校验通过的 DesignSpec
    :param out_path: 成品 DOCX 路径
    :param target_pages: 目标页数（默认取 ``spec.page.target_pages``）
    :param allow_font_reduction: 是否允许走第 4 档（缩字号）。
        默认 False —— 规范明文「绝不靠缩字号硬塞」；关闭时若前三档用尽仍
        溢出，会**停下并归因**（告诉你要删内容），而不是悄悄把正文压到 9pt 以下。
    :param levels: 每档内的压缩强度序列（默认先 50% 再 100%）
    :param max_steps: 重渲染次数上限（防止意外死循环）
    :param measurer: 注入的页数测量函数（测试用；默认 Word COM + 估算）
    :param on_step: 每次收敛后的回调（CLI 用来实时打印）
    :return: FitResult
    """
    if measurer is None:
        measurer = measure_pages

    if target_pages is None:
        tp = getattr(spec.page.target_pages, "value", None)
        target_pages = int(tp) if tp else 1

    path = Path(out_path)
    stages = [s for s in STAGE_ORDER
              if s != STAGE_FONT or allow_font_reduction]

    steps: List[FitStep] = []
    current = spec

    def _measure() -> Tuple[Optional[int], str]:
        _render(blocks, current, path)
        return measurer(path)

    pages, source = _measure()
    if pages is None:
        report = audit(path, spec=current, blocks=blocks,
                       target_pages=target_pages, measurer=measurer)
        raise FitError(
            "无法测量页数（无 Word COM 且估算失败），auto-fit 中止。\n"
            + report.render())

    while pages > target_pages and len(steps) < max_steps:
        progressed = False
        for stage in stages:
            if pages <= target_pages or len(steps) >= max_steps:
                break
            for level in levels:
                if pages <= target_pages or len(steps) >= max_steps:
                    break
                candidate = _STAGE_FUNCS[stage](current, level)
                if _tunables(candidate) == _tunables(current):
                    continue            # 本档已到下限，换下一档
                current = candidate
                pages, source = _measure()
                step = FitStep(stage, level, pages, source)
                steps.append(step)
                if on_step:
                    on_step(step)
                progressed = True
        if pages <= target_pages or not progressed:
            break

    report = audit(path, spec=current, blocks=blocks,
                   target_pages=target_pages, measurer=measurer)
    converged = report.pages_ok

    attribution = ""
    if not converged:
        used = {s.stage for s in steps}
        missing = [s for s in stages if s not in used]
        parts = [
            f"已收敛 {(report.pages if report.pages else '?')} 页，"
            f"目标 {target_pages} 页，仍超出"
        ]
        if report.estimate is not None and report.overflow_cm > 0:
            parts.append(f"估算溢出 {report.overflow_cm:.2f}cm")
        if not allow_font_reduction:
            parts.append(
                "间距/行距/边距三档已用尽；按规范**不自动缩字号**"
                "（正文下限 9pt，禁止靠缩字号硬塞）")
        if missing:
            parts.append(
                "未使用档位：" + "、".join(_STAGE_TITLE.get(m, m) for m in missing))
        parts.append(
            f"当前内容量：{len(getattr(blocks, 'internships', []))} 实习 / "
            f"{len(getattr(blocks, 'projects', []))} 项目 / "
            f"{len(getattr(blocks, 'campus', []))} 校园 / "
            f"{len(getattr(blocks, 'skills', []))} 技能点 —— "
            "请按 resume_writer.md Phase 5 顺序**删减内容**"
            "（先砍弱相关经历与 bullet，再压缩优势/合并证书）")
        attribution = "；".join(parts)

    return FitResult(spec=current, docx_path=path, report=report,
                     steps=steps, converged=converged, attribution=attribution)
