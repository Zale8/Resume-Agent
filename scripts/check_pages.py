# -*- coding: utf-8 -*-
"""估算docx内容总高度，判断是否单页A4

用法：
    python check_pages.py <docx文件路径>

本脚本不含任何用户个人信息。
DOC 路径通过命令行参数传入。
"""
import sys
from docx import Document
from docx.shared import Cm, Pt, Emu

if len(sys.argv) < 2:
    print("用法: python check_pages.py <docx文件路径>")
    sys.exit(1)

DOC = sys.argv[1]

doc = Document(DOC)

# A4 可用高度
for sec in doc.sections:
    usable_h = sec.page_height - sec.top_margin - sec.bottom_margin
    print(f"页面可用高度: {usable_h/914400*2.54:.1f} cm")
    print(f"页面可用宽度: {(sec.page_width-sec.left_margin-sec.right_margin)/914400*2.54:.1f} cm")

# 估算内容高度
total_pt = 0
para_count = 0

for p in doc.paragraphs:
    pf = p.paragraph_format
    size = 10
    for run in p.runs:
        if run.font.size:
            size = run.font.size.pt
            break
    line = pf.line_spacing or 1.0
    if isinstance(line, float):
        line_h = size * line
    else:
        line_h = size
    before = pf.space_before.pt if pf.space_before else 0
    after = pf.space_after.pt if pf.space_after else 0
    text_len = len(p.text)
    chars_per_line = 45
    lines = max(1, (text_len + chars_per_line - 1) // chars_per_line)
    h = line_h * lines + before + after
    total_pt += h
    para_count += 1
    if p.text.strip():
        print(f"  [{para_count}] size={size} line={line} lines={lines} h={h:.1f}pt | {p.text[:50]}")

# 表格高度
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                pf = p.paragraph_format
                size = 10
                for run in p.runs:
                    if run.font.size:
                        size = run.font.size.pt
                        break
                line = pf.line_spacing or 1.0
                if isinstance(line, float):
                    line_h = size * line
                else:
                    line_h = size
                before = pf.space_before.pt if pf.space_before else 0
                after = pf.space_after.pt if pf.space_after else 0
                text_len = len(p.text)
                chars_per_line = 30
                lines = max(1, (text_len + chars_per_line - 1) // chars_per_line)
                h = line_h * lines + before + after
                total_pt += h
                if p.text.strip():
                    print(f"  [TABLE] size={size} lines={lines} h={h:.1f}pt | {p.text[:50]}")

# 照片高度
total_pt += 74  # 2.6cm ≈ 74pt

total_cm = total_pt / 28.35
print(f"\n总段落数: {para_count}")
print(f"估算总高度: {total_pt:.1f} pt = {total_cm:.1f} cm")
usable_cm = (doc.sections[0].page_height - doc.sections[0].top_margin - doc.sections[0].bottom_margin) / 914400 * 2.54
print(f"可用高度: {usable_cm:.1f} cm")
if total_cm <= usable_cm:
    print(f"✓ 预计单页内 (余量 {usable_cm - total_cm:.1f} cm)")
else:
    print(f"✗ 预计溢出 (超出 {total_cm - usable_cm:.1f} cm)")
