# -*- coding: utf-8 -*-
"""smoke_layout_kit.py — 用虚构人物验证三种骨架能产出 DOCX。

不含任何真实个人信息。需要 python-docx。
用法（在 Resume-Agent 根目录）：
    python tests/smoke_layout_kit.py
退出码：0 通过 / 1 失败 / 2 缺少 python-docx
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Windows 控制台默认 GBK，输出 ✅/❌ 会抛 UnicodeEncodeError。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def fictional_blocks():
    from resume_generator.layout_kit import BulletBlock, ResumeBlocks

    return ResumeBlocks(
        name="张三",
        intent="产品经理（实习）",
        contact_lines=["13800000000  ·  zhangsan@example.com", "北京 / 上海"],
        summary="某虚构大学在读，具备从需求调研到落地的校园项目经验，善于用数据验证方案。",
        education_lines=["某虚构大学｜本科｜计算机｜2023.09-2027.06  GPA 3.6/4.0"],
        internships=[
            BulletBlock(
                title="某科技公司",
                role="产品实习生",
                meta="2025.07-2025.09",
                bullets=["协助完成需求文档与验收；跟踪核心指标并输出周报"],
            )
        ],
        projects=[
            BulletBlock(
                title="校园信息服务",
                role="负责人",
                meta="2024.10-2026.06",
                bullets=["从调研到运营落地，日均订单示例数据仅用于版式测试"],
            )
        ],
        campus=["学生会干事，组织过主题活动"],
        skills=["Office / 飞书", "Python 基础"],
        certs=["大学英语四级"],
        photo_path=None,
    )


def _assert_cell_margins_sane(doc, sid: str) -> None:
    """校验所有表格单元格内边距的 twips 值在合理范围内。

    回归点：w:tcMar 的单位是 twips（dxa），最大合理值约几厘米（1cm=567twips）。
    若出现 > 50000（~88cm）说明又把 EMU 当 twips 写了。
    """
    from docx.oxml.ns import qn

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                tcPr = cell._tc.find(qn("w:tcPr"))
                if tcPr is None:
                    continue
                tcMar = tcPr.find(qn("w:tcMar"))
                if tcMar is None:
                    continue
                for node in tcMar:
                    val = node.get(qn("w:w"))
                    if val and int(val) > 50000:
                        raise AssertionError(
                            f"{sid}: 单元格内边距异常（w={val} twips，疑似 EMU 误作 twips）"
                        )


def main() -> int:
    try:
        from resume_generator.layout_kit import (
            SKELETON_BANNER,
            SKELETON_MINIMAL,
            SKELETON_SIDEBAR,
            describe_kit,
        )
        from resume_generator.skeletons import build_document
    except ImportError as exc:
        print(f"import 失败：{exc}")
        return 1

    print(describe_kit())
    try:
        import docx  # noqa: F401
    except ImportError:
        print("未安装 python-docx，跳过写出文件（pip install python-docx）")
        return 2

    blocks = fictional_blocks()
    out_dir = Path(tempfile.mkdtemp(prefix="resume_kit_"))
    ids = [SKELETON_BANNER, SKELETON_MINIMAL, SKELETON_SIDEBAR]
    palettes = ["tech_navy", "minimal_ink", "manufacturing_steel"]
    for sid, pal in zip(ids, palettes):
        doc = build_document(blocks, sid, pal)
        # 回归守卫：单元格内边距的 twips 值必须在合理范围内。
        # 历史 bug：Cm() 返回 EMU，却当作 dxa 写进 w:tcMar，
        # 0.25cm 变成 ~142cm，导致分页探成几十页。
        _assert_cell_margins_sane(doc, sid)
        path = out_dir / f"zhangsan_{sid}.docx"
        doc.save(path)
        if path.stat().st_size < 2000:
            print(f"❌ {sid} 文件过小：{path}")
            return 1
        print(f"✅ {sid}  {pal}  → {path.name}  ({path.stat().st_size} bytes)")
    print(f"临时目录：{out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
