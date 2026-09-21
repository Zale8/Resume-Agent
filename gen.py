#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen.py — Resume-Agent 统一命令行入口。

设计目标
--------
1. 零依赖：doctor / check-library 只用 Python 3.8+ 标准库，clone 下来即可运行。
2. 零配置：简历库路径自动发现（见 paths.py），不写死任何绝对路径。
3. 跨平台：Windows / macOS / Linux 行为一致；`build` 在有 Word 的机器上
   用 COM 实测页数，没有则退化为明确标注的估算。

三条子命令
----------
    python gen.py doctor                         体检：环境 / 路径 / 简历库 / 生成依赖
    python gen.py check-library                  校验简历库四阶段产物一致性
    python gen.py build <resume.md> [--design …] 一条命令从内容层 + 本份设计出达标 DOCX

`build` 为什么要求 design.json 必须每份新建
-------------------------------------------
审计（docs/architecture/audit_2026-09-21_root_cause.md §R3）指出：旧规则把
设计决策的落盘载体堵死（「对话内明确即可，不新建任何决策文件」），流程上唯一
留存的实物反而是**上一份的临时脚本**，于是「照抄上一份」成了必然。
`build` 改为读取**该岗位目录下的 design.json**，并且：

* 缺文件 → 直接拒绝并打印模板（**没有默认设计，不存在兜底**）；
* 写出成品的同时把本份设计意图回显，便于事后核对；
* 生成后自动走 auto-fit 收敛 + 八维 QA 报告，不达标就明确归因。

DOCX 成品怎么来？
-----------------
推荐路径就是 `build`：内容层 resume.md →（本份 design.json）→ DesignSpec
→ validate_spec → 渲染 → auto-fit → QA 报告。
需要完全自定义版式时，才写一次性脚本（临时脚本是**执行器，不是设计系统**），
不入 Git；用户定稿确认后删除（AGENT.md §十三）。
兼容旧路径 `build_document(blocks, skeleton_id, palette_id)`（无本份级定制时使用）。
详见 agent_entry.md 第 5 节「DOCX 动态生成规范」。
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
            "08_证书奖项", "09_岗位定制简历", "11_岗位JD",
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
              "确定本份 Design Decision → assemble_job_spec → validate_spec "
              "→ build_document(design_spec=) 动态构建 DOCX。")
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

    # 公司名可能带后缀（JD 写「某公司某地分公司」，目录名是「某公司」）
    for cand in resume_dir.iterdir():
        if not cand.is_dir():
            continue
        if cand.name in company or company in cand.name:
            if any(cand.rglob("*.docx")):
                return True
    return False


# ============================================================================
# build — 一条命令：内容层 + 本份设计 → 达标 DOCX
# ============================================================================

def _design_template_text() -> str:
    import json as _json

    from resume_generator.design import DESIGN_TEMPLATE

    return _json.dumps(DESIGN_TEMPLATE, ensure_ascii=False, indent=2)


def _build_help_on_missing_design(design_path: Path, resume_md: Path) -> None:
    bad(f"缺少本份设计决策文件：{design_path}")
    print()
    print("  `build` 不会替你挑一套设计，也不会沿用上一份 —— 这是刻意的：")
    print("  审计已证明「照抄上一份」的根源就是设计决策没有落盘载体。")
    print()
    print(f"  请先在本命令旁生成模板，再按本份取舍填写：")
    print(f"      python gen.py build \"{resume_md}\" --write-design-template")
    print(f"      （会写出 {design_path}）")
    print()
    print("  模板内容：")
    for line in _design_template_text().splitlines():
        print("      " + line)


def cmd_build(args: argparse.Namespace) -> int:
    head("Resume-Agent 一键生成（content → design → fit → QA）")

    resume_md = Path(args.resume_md)
    if resume_md.is_dir():
        resume_md = resume_md / "resume.md"
    if not resume_md.is_file():
        bad(f"找不到内容层 resume.md：{resume_md}")
        print("  内容层必须先生成（agent_entry.md §2 / §6）：")
        print("      11_岗位JD → 14_JD结构化分析 → 13_JD分析 → "
              "09_岗位定制简历/公司/岗位/日期/resume.md")
        print("  四阶段产物状态可用 `python gen.py check-library` 查看。")
        return 2

    design_path = (Path(args.design) if args.design
                   else resume_md.parent / "design.json")

    if args.write_design_template:
        if design_path.exists() and not args.force:
            warn(f"{design_path} 已存在；要覆盖请加 --force")
            return 1
        design_path.parent.mkdir(parents=True, exist_ok=True)
        design_path.write_text(_design_template_text() + "\n", encoding="utf-8")
        ok(f"已写出设计决策模板：{design_path}")
        print("  请按本份取舍填写（paradigm 与 design_intent 必填），"
              "再运行 build。")
        return 0

    # --- 1. 内容层 ---
    from resume_generator.content_parser import parse_resume_md

    try:
        lib = resolve_lib(args.lib)
        photo_root = lib
    except ResumeLibNotFound as exc:
        warn(f"未能定位简历库，照片相对路径将原样保留\n{exc}")
        photo_root = None

    try:
        parsed = parse_resume_md(resume_md, photo_root=photo_root, strict=False)
    except Exception as exc:                      # noqa: BLE001 - CLI 边界
        bad(f"内容层解析失败：{exc}")
        return 1

    head("1. 内容层诊断")
    print(f"  {parsed.summary_line()}")
    for line in parsed.diagnostics.render().splitlines():
        print("  " + line)
    if parsed.fatal:
        bad("内容层存在致命问题，拒绝生成（先修内容层，再 build）")
        return 2
    if parsed.diagnostics.warnings:
        warn(f"内容层有 {len(parsed.diagnostics.warnings)} 条警告"
             f"（不阻断生成，但请核对上面逐条列出的原始行）")

    # --- 2. 本份设计决策 ---
    head("2. 本份设计决策（design.json）")
    if not design_path.is_file():
        _build_help_on_missing_design(design_path, resume_md)
        return 2

    from resume_generator.design import JobSpecError, load_job_spec

    try:
        spec, design = load_job_spec(design_path)
    except JobSpecError as exc:
        bad(f"design.json 不可用：{exc}")
        print()
        print("  模板（可复制到文件后按本份取舍修改）：")
        for line in _design_template_text().splitlines():
            print("      " + line)
        return 2
    print(f"  文件：{design_path}")
    print(f"  范式：{design['paradigm']}")
    print(f"  意图：{design['design_intent']}")
    ok("已通过 validate_spec（ERROR 0）")

    # --- 3. 渲染 + auto-fit + QA ---
    head("3. 渲染 → auto-fit → QA")
    try:
        from resume_generator.fitting import FitError, fit
    except ImportError:
        bad("未安装 python-docx，无法渲染 DOCX：pip install python-docx")
        return 2

    out_path = (Path(args.out) if args.out
                else resume_md.parent / f"{parsed.blocks.name or 'resume'}"
                                        f"_简历.docx")
    try:
        result = fit(parsed.blocks, spec, out_path,
                     allow_font_reduction=args.allow_font_reduction,
                     on_step=lambda s: print("  · " + s.render()))
    except FitError as exc:
        bad(f"auto-fit 中止：{exc}")
        return 1
    except Exception as exc:                      # noqa: BLE001 - CLI 边界
        bad(f"渲染失败：{exc}")
        return 1

    print()
    print(result.render())
    print()
    if result.converged:
        ok(f"成品已生成且达标：{out_path}")
        return 0
    if args.allow_overflow:
        warn("成品已生成但**未达标**（--allow-overflow 已指定，不判失败）")
        return 0
    bad("成品已生成但**未达标**：请按上面的归因处理（通常是精简内容）"
        "，或用 --allow-overflow 明确接受")
    return 1


# ============================================================================
# 参数
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen.py",
        description="Resume-Agent 运维 / 校验 / 生成 CLI",
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

    p_b = sub.add_parser(
        "build",
        help="一条命令：resume.md + design.json → 达标 DOCX（含 auto-fit 与 QA）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "从内容层 resume.md 与本份 design.json 生成达标 DOCX。\n"
            "design.json 必须每份新建：缺文件直接拒绝（不套用上一份）。\n"
            "需要 python-docx；有 Word/pywin32 时用 COM 实测页数。"))
    p_b.add_argument("resume_md", help="resume.md 路径（或其所在目录）")
    p_b.add_argument("--design", help="本份 design.json（默认取 resume.md 同目录）")
    p_b.add_argument("--out", help="成品 DOCX 路径（默认 <姓名>_简历.docx）")
    p_b.add_argument("--allow-font-reduction", action="store_true",
                     help="允许 auto-fit 走「缩字号」档（默认禁止：正文不低于 9pt）")
    p_b.add_argument("--allow-overflow", action="store_true",
                     help="未达标时仍返回 0（默认返回 1，便于当门禁）")
    p_b.add_argument("--write-design-template", action="store_true",
                     help="只写出 design.json 模板后退出")
    p_b.add_argument("--force", action="store_true",
                     help="配合 --write-design-template：覆盖已存在的文件")
    p_b.set_defaults(func=cmd_build)

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
