#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen.py — Resume-Agent 统一命令行入口（运维 / 校验工具）。

设计目标
--------
1. 零依赖：本 CLI 只用 Python 3.8+ 标准库，clone 下来即可运行。
2. 零配置：简历库路径自动发现（见 paths.py），不写死任何绝对路径。
3. 跨平台：Windows / macOS / Linux 行为一致，不依赖 Word、WPS、COM。

两条子命令
----------
    python gen.py doctor           体检：环境 / 路径 / 简历库 / 生成依赖
    python gen.py check-library    校验简历库四阶段产物一致性

DOCX 成品怎么来？
-----------------
本产品**不内置固定模板库**。每份定向简历由 Agent 选定骨架（skeletons）与
行业色板，把内容填入 layout_kit.ResumeBlocks 后动态构建 DOCX
（用后即删任何临时脚本），详见 agent_entry.md 第 5 节「DOCX 动态生成规范」。
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

# Windows 控制台默认 GBK，输出 ✅/⚠️/❌/分隔线会抛 UnicodeEncodeError 而中断体检。
# 尽力把 stdout/stderr 切到 UTF-8；切不动时降级为 errors="replace"，绝不因此崩溃。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        pass

# 让脚本在任意 cwd 下都能 import 到 src/ 里的包
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from resume_generator.paths import (  # noqa: E402
    ResumeLibNotFound,
    describe_paths,
    find_product_root,
    resolve_lib,
)

SEP = "─" * 68


# ============================================================================
# 输出小工具
# ============================================================================

def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def bad(msg: str) -> None:
    print(f"  ❌ {msg}")


def head(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


# ============================================================================
# doctor
# ============================================================================

def cmd_doctor(args: argparse.Namespace) -> int:
    head("Resume-Agent 环境体检")
    print(describe_paths())

    problems = 0

    head("1. Python 版本")
    version = sys.version_info
    if version >= (3, 8):
        ok(f"Python {version.major}.{version.minor}.{version.micro}（需 3.8+）")
    else:
        bad(f"Python {version.major}.{version.minor} 过低，需 3.8+")
        problems += 1

    head("2. 产品仓库")
    root = find_product_root()
    print(f"  仓库根目录：{root}")
    for name in ("src", "prompts"):
        path = root / name
        (ok if path.is_dir() else bad)(f"{name}/ {'存在' if path.is_dir() else '缺失'}")
        if not path.is_dir():
            problems += 1

    head("3. 简历库")
    try:
        lib = resolve_lib(args.lib)
        print(f"  简历库路径：{lib}")
        expected = [
            "00_个人信息", "01_教育经历", "02_实习经历", "03_项目经历",
            "04_校园经历", "05_专业技能", "06_求职意向", "07_个人优势",
            "08_证书奖项", "09_岗位定制简历", "10_简历母版", "11_岗位JD",
            "12_投递记录", "13_JD分析", "14_JD结构化分析", "99_配置",
        ]
        for name in expected:
            path = lib / name
            if path.is_dir():
                count = len(list(path.glob("*.md")))
                ok(f"{name}/ （{count} 个 md）")
            else:
                warn(f"{name}/ 不存在")
    except ResumeLibNotFound as exc:
        bad("未能定位简历库")
        print(f"\n{exc}")
        problems += 1

    head("4. DOCX 生成依赖（动态生成简历时使用，体检本身不需要）")
    ok("本 CLI 零第三方依赖（仅标准库）")
    if importlib.util.find_spec("docx") is not None:
        ok("python-docx 已安装 —— 可调用 layout_kit / skeletons 生成 DOCX")
    else:
        warn("未检测到 python-docx —— 生成简历前需安装：pip install python-docx")
    kit = root / "src" / "resume_generator" / "layout_kit.py"
    skel = root / "src" / "resume_generator" / "skeletons.py"
    if kit.is_file() and skel.is_file():
        ok("排版积木 layout_kit.py + 三种骨架 skeletons.py 已就位")
    else:
        bad("缺少 src/resume_generator/layout_kit.py 或 skeletons.py")
        problems += 1
    if importlib.util.find_spec("win32com") is not None:
        ok("pywin32 已安装 —— 可用 Word COM 实测真实页数（可选，仅 Windows）")
    else:
        print("  ℹ️  pywin32 未安装（可选）：无它时用 scripts/check_pages.py 估算页数")

    head("体检结论")
    if problems == 0:
        print("  🎉 全部通过。生成简历请按 agent_entry.md 第 5 节："
              "选定骨架 + layout_kit 动态构建 DOCX。")
        return 0
    print(f"  发现 {problems} 处问题，请按上面的提示修复。")
    return 1


# ============================================================================
# check-library — 简历库一致性校验
# ============================================================================

def cmd_check_library(args: argparse.Namespace) -> int:
    """校验四处产物的一致性：JD 原文 / JD 结构化分析 / 匹配分析 / 成品。

    为什么需要：文件名相近（`公司_岗位.md` 与 `公司_岗位_匹配分析.md`）容易被
    误认为重复生成，也确实存在「只留了一份」的历史遗留。本命令把不一致显式
    列出，避免靠人肉比对。
    """
    try:
        lib = resolve_lib(args.lib)
    except ResumeLibNotFound as exc:
        bad("未找到简历库")
        print(str(exc))
        return 1

    stages = [
        ("JD原文", lib / "11_岗位JD", ""),
        ("结构化", lib / "14_JD结构化分析", ""),
        ("匹配分析", lib / "13_JD分析", "_匹配分析"),
    ]
    resume_dir = lib / "09_岗位定制简历"

    head("简历库一致性校验")
    print(f"  简历库：{lib}")

    def stems(folder: Path, suffix: str = "") -> dict[str, Path]:
        out: dict[str, Path] = {}
        if not folder.is_dir():
            return out
        for f in folder.glob("*.md"):
            name = f.stem
            if suffix:
                if not name.endswith(suffix):
                    continue
                name = name[: -len(suffix)]
            out[name] = f
        return out

    per_stage: dict[str, dict[str, Path]] = {
        label: stems(folder, suffix) for label, folder, suffix in stages
    }

    all_keys: set[str] = set()
    for files in per_stage.values():
        all_keys.update(files)

    orphan_resumes = _resume_dir_keys(resume_dir)
    unmatched = {k for k in orphan_resumes if not _key_matches_company(k, all_keys)}

    print(f"\n  发现 {len(all_keys)} 个岗位记录（按 JD/分析文件名）")
    if unmatched:
        print(f"  另有 {len(unmatched)} 个 09 成品目录未对应到 11/13/14 文件名：")
        for k in sorted(unmatched):
            print(f"      · {k}")

    print()

    header = f"  {'岗位':<40}" + "".join(f"{label:<10}" for label, _, _ in stages) + "成品"
    print(header)
    print("  " + "-" * (len(header) + 2))

    problems: list[str] = []
    if unmatched:
        for k in sorted(unmatched):
            problems.append(f"{k}：09 有目录但缺对应 JD/分析文件（请补 11 或核对公司名）")
    for key in sorted(all_keys):
        cells = []
        for label, _, _ in stages:
            cells.append("✓" if key in per_stage[label] else "✗")

        # 成品：按公司目录找任意 docx。
        # 放宽匹配的原因：JD 文件名里的「岗位」可能与实际投递岗位不同
        # （JD 叫「招聘简章」，实际投的是「库管员」），因此不要求岗位名精确相等。
        has_docx = _has_deliverable(resume_dir, key)
        cells.append("✓" if has_docx else "✗")

        print(f"  {key:<40}" + "".join(f"{c:<10}" for c in cells))

        for (label, folder, _), has in zip(stages, cells):
            if has == "✗":
                problems.append(f"{key}：缺{label}（{folder.name}/）")
        if cells[-1] == "✗":
            problems.append(f"{key}：缺成品 DOCX（09_岗位定制简历/）")

    head("结论")
    if not problems:
        ok("四处产物齐全且命名规范")
        return 0

    warn(f"发现 {len(problems)} 处不完整：")
    for p in problems:
        print(f"      · {p}")
    print()
    print("  说明：这些是**不同阶段**的产物，不是重复生成：")
    print("      11_岗位JD/YYYY-MM-DD_公司_岗位.md"
          "              → JD 原文")
    print("      14_JD结构化分析/YYYY-MM-DD_公司_岗位.md"
          "       → ① 岗位要什么（与候选人无关，可复用）")
    print("      13_JD分析/YYYY-MM-DD_公司_岗位_匹配分析.md"
          "    → ② 这个人与岗位的关系")
    print("      09_岗位定制简历/公司/岗位/日期/"
          "                → 成品 DOCX")
    print()
    print("  修复建议：")
    print("      · 缺「结构化」：按 prompts/jd_analyst.md 补 14_JD结构化分析")
    print("      · 缺「匹配分析」：执行「这个岗位我匹配吗？」流程")
    print("      · 缺「成品」：由 Agent 按 agent_entry.md 第 5 节选用骨架生成")
    print("      · 09 有目录但无 JD：把当日 JD 原文补进 11_岗位JD/")
    return 1


def _resume_dir_keys(resume_dir: Path) -> list[str]:
    """09_岗位定制简历/公司/岗位/ → 公司_岗位（不含日期）。"""
    keys: list[str] = []
    if not resume_dir.is_dir():
        return keys
    for company in resume_dir.iterdir():
        if not company.is_dir():
            continue
        for role in company.iterdir():
            if role.is_dir():
                keys.append(f"{company.name}_{role.name}")
    return keys


def _key_matches_company(resume_key: str, jd_keys: set[str]) -> bool:
    """JD stem 为 YYYY-MM-DD_公司_岗位，09 为 公司_岗位。"""
    company = resume_key.split("_", 1)[0]
    for jk in jd_keys:
        parts = jk.split("_")
        if len(parts) >= 2 and (parts[1] == company or company in parts[1] or parts[1] in company):
            return True
    return False


def _has_deliverable(resume_dir: Path, key: str) -> bool:
    """判断某个岗位是否已有成品 docx。

    按公司目录放宽匹配：JD 文件名里的岗位名常与实际投递岗位不同。
    """
    if not resume_dir.is_dir():
        return False
    parts = key.split("_")
    if len(parts) < 2:
        return False
    company = parts[1]

    direct = resume_dir / company
    if direct.is_dir() and any(direct.rglob("*.docx")):
        return True

    # 公司名可能带后缀（JD 写「某公司华北某市分公司」，目录名是「某公司」）
    for cand in resume_dir.iterdir():
        if not cand.is_dir():
            continue
        if cand.name in company or company in cand.name:
            if any(cand.rglob("*.docx")):
                return True
    return False


# ============================================================================
# 参数
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen.py",
        description="Resume-Agent 运维 / 校验 CLI（零依赖 / 零配置 / 跨平台）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--lib", help="简历库绝对路径（默认自动发现）")

    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="环境与路径体检")
    p_doc.set_defaults(func=cmd_doctor)

    p_ck = sub.add_parser("check-library",
                          help="校验简历库一致性（JD原文/JD分析/匹配分析/成品）")
    p_ck.set_defaults(func=cmd_check_library)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\n已中断")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
