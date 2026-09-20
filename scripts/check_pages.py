# -*- coding: utf-8 -*-
"""估算 docx 内容总高度，判断是否单页 A4。

这是**估算工具**，不能替代 Word COM 实测。
页数以 Word ComputeStatistics(2) = 1 为准（见 layout_kit.count_pages_com）。

用法：
    python scripts/check_pages.py <docx文件路径>

本脚本不含任何用户个人信息。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让脚本在任意 cwd 下都能 import src/
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _estimate_chars_per_line(font_size_pt: float, in_table: bool) -> int:
    """根据字号估算每行字符数。中英文混排取折中值。"""
    # A4 可用宽约 18cm，10pt 中文约 2.8mm/字 → ~64字/行
    # 表格列宽更窄，约 60%
    base = max(20, int(64 * 10 / font_size_pt))
    return int(base * 0.6) if in_table else base


def estimate_height(docx_path: str) -> tuple[float, float]:
    """估算 DOCX 内容高度。返回 (估算高度cm, 可用高度cm)。"""
    from docx import Document

    doc = Document(docx_path)
    sec = doc.sections[0]
    usable_h_emu = sec.page_height - sec.top_margin - sec.bottom_margin
    usable_cm = usable_h_emu / 914400 * 2.54

    total_pt = 0.0
    photo_pt = 0.0

    def _para_height(p, in_table: bool = False) -> float:
        pf = p.paragraph_format
        size = 10.0
        for run in p.runs:
            if run.font.size:
                size = run.font.size.pt
                break
        line = pf.line_spacing or 1.0
        line_h = size * line if isinstance(line, float) else size
        before = pf.space_before.pt if pf.space_before else 0
        after = pf.space_after.pt if pf.space_after else 0
        cpl = _estimate_chars_per_line(size, in_table)
        text_len = len(p.text)
        n_lines = max(1, (text_len + cpl - 1) // cpl) if text_len > 0 else 1
        return line_h * n_lines + before + after

    # 文档级段落
    for p in doc.paragraphs:
        total_pt += _para_height(p)

    # 表格内段落
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    total_pt += _para_height(p, in_table=True)

    # 照片：从 inline shapes 检测实际高度，而非硬编码
    try:
        from docx.oxml.ns import qn
        for inline in doc.element.body.iter(qn("wp:inline")):
            extent = inline.find(qn("wp:extent"))
            if extent is not None:
                cx = extent.get("cy")
                if cx:
                    photo_pt = max(photo_pt, int(cx) / 12700 / 2.54 * 72 / 20 * 10)
    except Exception:
        pass

    # 兜底：如果检测不到照片但文档有图片关系，估算 2.5cm
    if photo_pt == 0:
        for rel in doc.part.rels.values():
            if "image" in rel.reltype:
                photo_pt = 71  # ~2.5cm
                break

    total_pt += photo_pt
    total_cm = total_pt / 28.35
    return total_cm, usable_cm


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/check_pages.py <docx文件路径>")
        return 1

    docx_path = sys.argv[1]
    if not Path(docx_path).exists():
        print(f"文件不存在: {docx_path}")
        return 1

    total_cm, usable_cm = estimate_height(docx_path)

    print(f"估算总高度: {total_cm:.1f} cm")
    print(f"可用高度: {usable_cm:.1f} cm")
    if total_cm <= usable_cm:
        print(f"✓ 预计单页内 (余量 {usable_cm - total_cm:.1f} cm)")
    else:
        print(f"✗ 预计溢出 (超出 {total_cm - usable_cm:.1f} cm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())