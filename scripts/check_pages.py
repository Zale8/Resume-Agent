# -*- coding: utf-8 -*-
"""估算 docx 内容总高度，判断是否单页 A4。

这是**估算工具**，不能替代 Word COM 实测。
页数以 Word ``ComputeStatistics(2)`` 为准（``gen.py build`` 会自动走 COM 实测并收敛）。

v0.9.0 起本脚本**不再自带估算逻辑**，改为委托 ``fitting.estimate_height``：
早先那份实现有三个已实测的硬缺陷
（见 docs/architecture/audit_2026-09-21_root_cause.md §R4）：
    1. 只遍历 ``wp:inline``，**浮动照片 ``wp:anchor`` 完全漏检**
       —— 而本项目主用的正是浮动照片；
    2. 单位换算写错（``int(cx)/12700`` 已是 pt，又乘 ``72/(2.54*20)*10`` ≈ ×14.17）；
    3. 溢出时仍 ``return 0``，无法当门禁信号。
现在估算逻辑只有一份（fitting.py），缺陷一次性修掉。

用法：
    python scripts/check_pages.py <docx文件路径>
    python scripts/check_pages.py <docx文件路径> --strict   # 溢出时返回 1

本脚本不含任何用户个人信息。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让脚本在任意 cwd 下都能 import src/
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except (AttributeError, ValueError, OSError):
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_pages.py",
        description="估算 DOCX 内容高度，判断是否单页 A4（估算，非实测）")
    parser.add_argument("docx", help="DOCX 文件路径")
    parser.add_argument("--strict", action="store_true",
                        help="溢出时返回退出码 1（可作门禁用）")
    args = parser.parse_args(argv)

    path = Path(args.docx)
    if not path.is_file():
        print(f"文件不存在: {path}")
        return 1

    from resume_generator.fitting import estimate_height, measure_pages

    est = estimate_height(path)
    print(est.render())
    print(f"估算页数: {est.virtual_pages}（虚拟页，按可用高度折算）")

    pages, source = measure_pages(path)
    tag = {"word_com": "实测", "estimate": "估算", "unavailable": "不可用"}
    print(f"页数: {pages}（来源：{tag.get(source, source)}）")

    if source == "word_com":
        print("✅ 有 Word COM 实测，以该页数为准。")
        if pages and pages > 1:
            return 1 if args.strict else 0
        return 0

    if est.overflow_cm > 0:
        print(f"✗ 预计溢出 ({est.overflow_cm:.2f} cm)")
        return 1 if args.strict else 0
    print(f"✓ 预计单页内 (余量 {est.usable_cm - est.total_cm:.2f} cm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
