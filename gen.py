#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen.py — Resume-Agent 统一命令行入口。

设计目标
--------
1. 零依赖：只用 Python 标准库。clone 下来即可运行，不需 pip install。
2. 零配置：简历库路径自动发现（见 paths.py），不写死任何绝对路径。
3. 跨平台：Windows / macOS / Linux 行为一致，不依赖 Word、WPS、COM。

四条子命令
----------
    python gen.py doctor                     体检：环境 / 路径 / 模板 / 简历库
    python gen.py list-templates             列出可用模板及其字段
    python gen.py standardize <docx> ...     把用户上传的 docx 模板标准化入库
    python gen.py render   --company X --role Y --jd file.md --template template_02
                                             一条命令出 DOCX 成品 （主命令）

典型用法
--------
    # 1. 体检
    python gen.py doctor

    # 2. 看看有哪些模板
    python gen.py list-templates

    # 3. 标准化一个自己下载的模板
    python gen.py standardize ~/Downloads/my_template.docx --name template_07

    # 4. 出简历（自动找简历库、自动找照片、自动命名、自动归档）
    python gen.py render --company 某科技公司 --role 产品经理 \
        --jd ../简历库/11_岗位JD/2026-01-01_某科技公司_产品经理.md \
        --template template_02 --resume ../简历库/09_岗位定制简历/某科技公司/产品经理/2026-01-01/resume.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

# 让脚本在任意 cwd 下都能 import 到 src/ 里的包
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from resume_generator import docx_engine as de            # noqa: E402
from resume_generator import resume_map as rm             # noqa: E402
from resume_generator import template_kit as tk           # noqa: E402
from resume_generator.paths import (                      # noqa: E402
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
    for name in ("src", "templates", "prompts"):
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
            "08_证书奖项", "09_岗位定制简历", "11_岗位JD", "13_JD分析", "99_配置",
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

    head("4. 模板")
    tpl_root = root / "templates"
    templates = sorted(tpl_root.glob("template_*/template.docx"))
    if not templates:
        bad(f"未找到任何模板：{tpl_root}")
        problems += 1
    for tpl in templates:
        xml = de.read_zip(tpl)[0][de.DOCUMENT_XML].decode("utf-8", "surrogateescape")
        fields = de.list_fields(xml)
        ok(f"{tpl.parent.name:<14} {len(fields):>3} 个字段  "
           f"照片={'有' if de.find_image_parts(de.read_zip(tpl)[0]) else '无'}  "
           f"占位符语法={'{{{{}}}}' if fields else '未识别'}")

    head("5. 依赖检查")
    ok("零第三方依赖（仅 Python 标准库）—— 无需 pip install")
    print("  说明：不需要 Word / WPS / LibreOffice，也不需要 pywin32 / python-docx。")

    head("体检结论")
    if problems == 0:
        print("  🎉 全部通过，可以直接运行： python gen.py render --help")
        return 0
    print(f"  发现 {problems} 处问题，请按上面的提示修复。")
    return 1


# ============================================================================
# list-templates
# ============================================================================

def cmd_list_templates(args: argparse.Namespace) -> int:
    root = find_product_root()
    tpl_root = root / "templates"
    templates = sorted(tpl_root.glob("template_*/template.docx"))
    if not templates:
        bad(f"未找到任何模板：{tpl_root}")
        return 1

    head(f"可用模板（{len(templates)} 套）")
    for tpl in templates:
        meta = tk.load_template_meta(tpl.parent)
        xml = de.read_zip(tpl)[0][de.DOCUMENT_XML].decode("utf-8", "surrogateescape")
        fields = [f for f, _ in de.list_fields(xml)]
        print(f"\n■ {tpl.parent.name}   {meta.get('name_cn', '(未命名)')}")
        print(f"  风格   : {meta.get('style', '未标注')}")
        print(f"  适用   : {meta.get('description', '未标注')}")
        print(f"  字段数 : {len(fields)}")
        print(f"  字段   : {', '.join(fields)}")
    print()
    print("  模板选择建议见 agent_entry.md「模板与风格路由表」")
    return 0


# ============================================================================
# standardize
# ============================================================================

def cmd_standardize(args: argparse.Namespace) -> int:
    root = find_product_root()
    src = Path(args.docx).expanduser()
    if not src.exists():
        bad(f"文件不存在：{src}")
        return 1

    name = args.name or f"template_{_next_template_index(root / 'templates'):02d}"
    head(f"标准化模板：{src.name}  ->  {name}")

    report = tk.standardize_template(
        src_docx=src,
        out_dir=root / "templates" / name,
        name_cn=args.name_cn or name,
        style=args.style or "待确认",
        description=args.description or "",
        pattern=args.pattern,
    )

    ok(f"已写入 {report['out_dir']}")
    print(f"  占位符语法 : {report['pattern']}")
    print(f"  发现字段   : {report['field_count']} 个")
    for field, count in report["fields"]:      # type: ignore[union-attr]
        flag = f"  ×{count}" if count > 1 else ""
        print(f"      {field}{flag}")
    print(f"  图片部件   : {report['images'] or '无'}")
    print(f"  照片占位   : {report['photo_hint'] or '未识别到'}")
    if report.get("converted_markers"):
        warn(f"已把 {report['converted_markers']} 处非标准占位符统一改写为 {{{{FIELD}}}} 形式")

    print("\n  产出：template.docx / template.json / field_mapping.md / template_config.md")
    warn("模板里若有图标类位图，渲染时默认只替换最小的一张（照片占位图）。")
    warn("请人工确认 field_mapping.md 的字段含义，并在 template.json 里补全 fields 说明。")
    return 0


def _next_template_index(tpl_root: Path) -> int:
    existing = []
    for p in tpl_root.glob("template_*"):
        try:
            existing.append(int(p.name.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return max(existing, default=0) + 1


# ============================================================================
# render — 主命令
# ============================================================================

def cmd_render(args: argparse.Namespace) -> int:
    root = find_product_root()

    # ---- 1. 模板 ----
    tpl_dir = root / "templates" / args.template
    tpl_docx = tpl_dir / "template.docx"
    if not tpl_docx.exists():
        # 允许直接传一个 docx 路径
        direct = Path(args.template).expanduser()
        if direct.suffix.lower() == ".docx" and direct.exists():
            tpl_docx = direct
            tpl_dir = direct.parent
        else:
            bad(f"找不到模板：{tpl_dir}")
            print("  用 `python gen.py list-templates` 查看可用模板。")
            return 1

    # ---- 2. 简历库 ----
    lib: Path | None = None
    try:
        lib = resolve_lib(args.lib)
    except ResumeLibNotFound as exc:
        if args.out:
            warn("未找到简历库，但指定了 --out，将直接输出到指定路径")
            print(f"  （{exc.__class__.__name__}: 已忽略简历库自动发现）")
        else:
            bad("未找到简历库")
            print(str(exc))
            return 1

    # ---- 3. 定位 resume.md ----
    resume_md: Path | None = None
    fields_json: Path | None = None
    base_dir: Path | None = None

    if args.resume:
        resume_md = Path(args.resume).expanduser()
    elif lib is not None and args.company and args.role:
        stem = lib / "09_岗位定制简历" / args.company / args.role
        if stem.is_dir():
            dates = sorted([d for d in stem.iterdir() if d.is_dir()], reverse=True)
            base = dates[0] if dates else stem
            candidate = base / "resume.md"
            if candidate.exists():
                resume_md = candidate
                print(f"  自动定位 resume.md：{candidate}")
            if (base / "resume.fields.json").exists():
                fields_json = base / "resume.fields.json"

    if args.fields:
        fields_json = Path(args.fields).expanduser()

    if resume_md is None and fields_json is None:
        bad("没有可用的简历内容来源")
        print("  请用 --resume 指定 resume.md，或用 --fields 指定 resume.fields.json。")
        return 1

    # resume.md 存在性早检查：避免走到一半才报错
    if resume_md is not None and not resume_md.exists():
        bad(f"resume.md 不存在：{resume_md}")
        return 1

    # resume.md 所在目录就是本次归档目录。
    # 产物应与它消费的内容层放在一起（resume.md + docx + notes + fields.json），
    # 而不是另建一个日期目录 —— 否则同一岗位会散落成多个目录。
    if resume_md is not None:
        base_dir = resume_md.resolve().parent
    elif lib is not None and args.company and args.role:
        base_dir = rm.find_resume_base(lib, args.company, args.role)

    # ---- 3b. JD 校验 ----
    # JD 是整条链路的输入起点（内容由 AI 依 JD 定制的依据），但它不参与字段填充。
    # 因此这里只做「存在性 + 是否像 JD」的检查与记录，不让渲染依赖它。
    jd_path: Path | None = None
    if args.jd:
        jd_path = Path(args.jd).expanduser()
        if not jd_path.exists():
            warn(f"--jd 指定的 JD 原文不存在，渲染继续，但生成说明中将标记为缺失：{jd_path}")
            jd_path = None
        else:
            jd_text = jd_path.read_text(encoding="utf-8", errors="ignore")
            if len(jd_text.strip()) < 40:
                warn(f"JD 文件内容过短（{len(jd_text.strip())} 字），"
                     "请确认不是只贴了岗位名称")
            print(f"  JD 原文     : {jd_path.name}（{len(jd_text)} 字）")

    # ---- 4. 读模板字段 ----
    entries, order = de.read_zip(tpl_docx)
    xml = entries[de.DOCUMENT_XML].decode("utf-8", "surrogateescape")
    pattern = de.resolve_pattern(xml, args.pattern)
    template_fields = [f for f, _ in de.list_fields(xml, pattern)]

    head(f"渲染简历：{args.company or '未指定公司'} / {args.role or '未指定岗位'}")
    print(f"  模板        : {tpl_docx}")
    print(f"  模板字段数  : {len(template_fields)}")
    print(f"  占位符语法  : {pattern}")
    if resume_md:
        print(f"  内容来源    : {resume_md}")
    if fields_json:
        print(f"  字段覆盖    : {fields_json}")

    # ---- 5. 构建字段值 ----
    library_data = None
    if args.supplement:
        if lib is None:
            warn("--supplement 需要简历库，但未能定位简历库，已跳过补齐")
        else:
            try:
                from resume_generator.data_loader import load_personal_data
                library_data = load_personal_data(lib)
                print(f"  库补齐数据源: {lib}（显式开启）")
            except Exception as exc:          # noqa: BLE001 - 补齐是增强，不应中断渲染
                warn(f"读取简历库失败，跳过补齐：{exc}")

    try:
        map_report = rm.MapReport()
        values, unmapped, source_note, parsed = rm.build_fields(
            resume_md=resume_md,
            template_fields=template_fields,
            fields_json=fields_json,
            library_data=library_data,
            report=map_report,
        )
    except (FileNotFoundError, ValueError) as exc:
        bad(str(exc))
        return 1

    print(f"  映射策略    : {source_note}")
    print(f"  已映射字段  : {len(values)} / {len(template_fields)}")

    # 姓名：优先命令行，其次 resume.md 解析，最后从简历库个人信息兜底
    if not args.name and parsed and parsed.name:
        args.name = parsed.name
        print(f"  姓名（自动）: {args.name}")
    if not args.name and library_data:
        personal = library_data.get("personal") or {}
        if isinstance(personal, dict) and personal.get("name"):
            args.name = str(personal["name"]).strip()
            print(f"  姓名（库兜底）: {args.name}")
    if not args.name:
        print("  姓名        : 未识别（将用「简历」作为文件名，可用 --name 指定）")

    if map_report.supplemented:
        print(f"  库补齐明细  : {len(map_report.supplemented)} 项"
              "（来自简历库事实层，未覆盖 resume.md）")
        for k, v in map_report.supplemented.items():
            shown = v if len(v) <= 34 else v[:34] + "…"
            print(f"      {k} = {shown}")

    # 槽位不足导致内容被丢弃 —— 这是最容易被忽略的问题，必须显式警告
    if map_report.truncated:
        warn(f"{len(map_report.truncated)} 项内容因模板槽位不足未进入简历：")
        for item in map_report.truncated[:8]:
            print(f"      · {item}")
        print("      处理建议：让 AI 重新排序 resume.md（最相关的放最前），")
        print("                或改用槽位更多的模板（见 gen.py list-templates）。")
    if map_report.slot_summary:
        print("  槽位占用    :")
        for key, summary in map_report.slot_summary.items():
            print(f"      {key}：{summary}")

    if unmapped:
        warn(f"以下 {len(unmapped)} 个模板字段没有对应内容，将保持空白：")
        print(f"      {', '.join(unmapped)}")
        print("      修复方式（按推荐顺序）：")
        print("        a) 让 AI 在 resume.md 中补上对应章节（最佳，内容可针对 JD 定制）；")
        print("        b) 加 --supplement 用简历库事实层补齐客观信息（TEL/EML/证书等）；")
        print("        c) 在 resume.fields.json 中直接给这些键赋值后加 --fields 重跑。")

    # 内容层写了字段、但当前模板没有对应位置 -> 会被丢弃，必须报警
    if map_report.unknown_fields:
        warn(f"{len(map_report.unknown_fields)} 个字段在当前模板中没有对应位置，"
             "已丢弃：")
        for key in map_report.unknown_fields[:10]:
            raw = str(map_report.unknown_values.get(key, "") or "")
            shown = raw if len(raw) <= 40 else raw[:40] + "…"
            print(f"      {key} = {shown!r}")
        if len(map_report.unknown_fields) > 10:
            print(f"      …另有 {len(map_report.unknown_fields) - 10} 个")
        print(f"      当前模板 {tpl_docx.parent.name} 的字段："
              f"{', '.join(template_fields)}")
        print("      处理方式：")
        print("        a) 换用包含这些字段的模板（见 python gen.py list-templates）；")
        print("        b) 或把这些内容并入模板已有的字段（如把技能写进自我评价）")

    # ---- 6. 证件照 ----
    photo: Path | None = None
    if args.photo:
        photo = Path(args.photo).expanduser()
    elif lib is not None and not args.no_photo:
        photos_dir = lib / "00_个人信息" / "photos"
        if photos_dir.is_dir():
            found = sorted(
                p for p in photos_dir.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp")
            )
            if found:
                photo = found[0]
    if photo and not photo.exists():
        warn(f"证件照不存在，跳过：{photo}")
        photo = None
    if photo:
        print(f"  证件照      : {photo}")
    elif not args.no_photo:
        warn("未找到证件照，将保留模板自带占位图")

    # ---- 7. 输出路径 ----
    out = _resolve_out_path(args, lib, root, tpl_docx, base_dir)
    print(f"  输出路径    : {out}")

    # 同名成品已存在时提醒（避免覆盖上一版或重复投递同一个岗位）
    if out.exists() and not args.force:
        warn(f"输出文件已存在，将被覆盖：{out.name}")
        print("      如需保留上一版，请先改名或加 --date 指定其他归档日期")
        print("      （确认覆盖可加 --force 消除本提示）")

    # ---- 8. 渲染 ----
    try:
        report = de.render(
            template_path=tpl_docx,
            values=values,
            out_path=out,
            photo_path=photo,
            pattern=pattern,
            strip_colors=tuple(args.strip_color),
            shrink=not args.no_shrink,
            photo_target=args.photo_part,
            photo_all=args.photo_all,
            preserve_slots=not args.no_slot_align,
        )
    except de.TemplateError as exc:
        bad(str(exc))
        return 1

    # ---- 9. 报告 ----
    head("渲染结果")
    ok(f"已生成 {out.name}（{report['size_bytes']} bytes）")
    filled = report["filled"]
    print(f"  替换字段    : {len(filled)} 个 / 共 {sum(filled.values())} 处")  # type: ignore[union-attr]
    if report["marker_runs_removed"]:
        print(f"  清理补高标记: {report['marker_runs_removed']} 个")
    if report["photo_replaced"]:
        print(f"  照片已替换  : {', '.join(report['photo_replaced'])}")  # type: ignore[arg-type]
    elif photo:
        warn("模板中没有可替换的图片部件，照片未写入")

    leftover = report["missing"]
    if leftover:
        warn(f"模板中仍留有空白字段：{', '.join(leftover)}")  # type: ignore[arg-type]

    # 空格对齐槽位：这是模板版式错位最常见的根因，必须显式汇报
    inline_ov = report.get("inline_overflow") or []
    flow_ov = report.get("flow_overflow") or []
    shrunk = report.get("shrunk_fields") or {}

    # 整行溢出：用真实页面几何判断，分「流式换行（正常）」与「行内槽位换行（破坏版式）」
    line_ov = report.get("line_overflow") or []
    risky = [i for i in line_ov if i.get("layout_risk")]      # type: ignore[union-attr]
    benign = [i for i in line_ov if not i.get("layout_risk")]  # type: ignore[union-attr]

    if risky:
        warn(f"{len(risky)} 行因值过长会换行，可能挤乱版式：")
        for item in risky[:6]:                      # type: ignore[union-attr]
            fields = ", ".join(item["fields"])      # type: ignore[index]
            print(f"      [{fields}] 行宽 {item['line_width']} > "     # type: ignore[index]
                  f"每行容量 {item['chars_per_line']} 字符"
                  f"（{item.get('half_pt', 18) / 2:.1f}pt）")           # type: ignore[union-attr]
            print(f"          {item['preview']!r}")    # type: ignore[index]
        print("      处理建议：精简这些字段的值，或改用字段更宽的模板")
    else:
        print("  行内槽位    : 无因值过长而换行的固定行（版式安全）")

    if benign:
        fields_joined = ", ".join(
            sorted({f for i in benign for f in i["fields"]})   # type: ignore[union-attr,index]
        )
        print(f"  流式换行    : {len(benign)} 行为长文本自然换行（设计如此，不影响版式）："
              f"{fields_joined}")

    # 槽位层面的提示（次要，用于说明「值比模板预留位置长」）
    if inline_ov:
        print(f"  槽位长度提示: {len(inline_ov)} 个窄槽位的值长于模板占位符"
              "（若上面无整行溢出则不影响版式）")
        for name, ratio in inline_ov[:8]:          # type: ignore[misc]
            print(f"      {name}  超出 {ratio}×")
        if shrunk:
            print(f"      已自动缩字号（下限 8pt）：{shrunk}")

    if flow_ov:
        # 这里包含「流式文本」与「轻微超出（只右移几个像素，视觉不可见）」两类
        mild = [n for n, _ in flow_ov]
        print(f"  文本长度提示: {len(flow_ov)} 个字段较长（栏内自然换行或轻微右移，"
              "不影响版式，按规范不缩字号）：")
        print(f"      {', '.join(mild[:10])}")

    ov = report["overflow"]
    print(f"  溢出估算    : 约 {ov['approx_lines']} 行 / 单页容量约 "
          f"{ov['capacity_lines']} 行 -> {ov['verdict']}")  # type: ignore[index]
    if ov["verdict"] != "ok":                              # type: ignore[index]
        warn("内容可能超过一页。")
        print("      这不是精确排版结果（本工具不启动 Word）。")
        print("      请打开 docx 目视确认；如需压缩，优先精简 Weakly Relevant 内容。")
    else:
        print("      注意：这是文字量估算，非精确分页。最终请目视确认。")

    # ---- 10. 生成说明（AGENT.md 要求产物目录必须有）----
    if not args.no_notes:
        notes_path = out.with_name("generation_notes.md")
        meta = tk.load_template_meta(tpl_docx.parent)
        rm.generate_notes_md(
            company=args.company,
            role=args.role,
            jd_path=jd_path,
            template_name=tpl_docx.parent.name,
            template_style=str(meta.get("style", "") or ""),
            resume_md=resume_md,
            fields_json=fields_json,
            photo=photo,
            source_note=source_note,
            values=values,
            template_fields=template_fields,
            report=map_report,
            render_report=report,
            notes_path=notes_path,
            resume_sha256=rm.sha256_of_file(resume_md),
        )
        print(f"\n  生成说明已写：{notes_path.name}")
        print("  （记录模板槽位、被丢弃内容、留空字段、版式检查；"
              "「AI 优化说明」两节需 AI 补充）")

    # ---- 11. 字段快照，便于复查与二次渲染 ----
    if not args.no_emit_fields:
        sidecar = out.with_suffix(".fields.json")
        rm.save_fields_json(
            values,
            sidecar,
            extra={
                "template": tpl_docx.parent.name,
                "company": args.company,
                "role": args.role,
                "jd": jd_path.name if jd_path else None,
                "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "unmapped_template_fields": unmapped,
                "dropped_by_slot_limit": map_report.truncated,
                "source": source_note,
            },
        )
        print(f"  字段快照已存：{sidecar.name}")
        print("  （可用于排查、复现，以及下次只改字段不重跑解析）")

    head("下一步")
    step = 1
    print(f"  {step}. 打开 docx 目视确认排版、照片与页码"); step += 1
    print(f"  {step}. 补齐 generation_notes.md 的「AI 优化说明」与「真实性自检」两节"); step += 1
    if map_report.truncated:
        print(f"  {step}. ⚠️ 处理上面列出的「未进入简历」内容"
              "（重排 resume.md 或换模板）"); step += 1
    print(f"  {step}. 如有字段偏差：改 resume.fields.json 后加 --fields 重跑，无需重写内容")
    return 0


def _resolve_out_path(
    args: argparse.Namespace,
    lib: Path | None,
    root: Path,
    tpl_docx: Path,
    base_dir: Path | None = None,
) -> Path:
    """决定输出路径。

    优先级：--out > resume.md 所在目录（或简历库规范目录） > 产品仓库同级 _output/
    文件命名：{姓名}_{公司}_{岗位}.docx

    姓名优先来自 resume.md 解析结果（已在 cmd_render 中回填到 args.name），
    这样用户不必每次重复输入姓名。

    为什么优先放在 resume.md 旁边：
        resume.md 是这次生成的内容层，归档目录应同时容纳
        resume.md / docx / generation_notes.md / *.fields.json，
        便于「改字段→重渲→对比」的迭代闭环。
    """
    if args.out:
        return Path(args.out).expanduser().resolve()

    name_part = args.name or "简历"
    company = args.company or "未知公司"
    role = args.role or "未知岗位"
    filename = args.filename or f"{name_part}_{company}_{role}.docx"

    if base_dir is not None:
        return (base_dir / filename).resolve()

    if lib is not None:
        date = args.date or _dt.date.today().isoformat()
        return (lib / "09_岗位定制简历" / company / role / date / filename).resolve()

    fallback = root.parent / "_output"
    return (fallback / filename).resolve()


# ============================================================================
# 参数
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen.py",
        description="Resume-Agent 统一 CLI（零依赖 / 零配置 / 跨平台）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--lib", help="简历库绝对路径（默认自动发现）")

    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="环境与路径体检")
    p_doc.set_defaults(func=cmd_doctor)

    p_ls = sub.add_parser("list-templates", help="列出可用模板与字段")
    p_ls.set_defaults(func=cmd_list_templates)

    p_std = sub.add_parser("standardize", help="把上传的 docx 标准化为可用模板")
    p_std.add_argument("docx", help="待标准化的 .docx 文件")
    p_std.add_argument("--name", help="模板目录名（默认自动编号 template_07）")
    p_std.add_argument("--name-cn", help="模板中文名")
    p_std.add_argument("--style", help="风格标签，如「稳重正式」")
    p_std.add_argument("--description", help="适用场景说明")
    p_std.add_argument("--pattern",
                       help=f"占位符语法：预设名或正则。预设：{', '.join(de.MARKER_PRESETS)}")
    p_std.set_defaults(func=cmd_standardize)

    p_r = sub.add_parser("render", help="渲染 DOCX 成品（主命令）")
    p_r.add_argument("--template", required=True,
                     help="模板目录名（如 template_02）或 docx 路径")
    p_r.add_argument("--company", help="目标公司（用于命名与归档）")
    p_r.add_argument("--role", help="目标岗位")
    p_r.add_argument("--name", help="姓名（用于文件命名，留空则用「简历」）")
    p_r.add_argument("--jd", help="JD 原文路径（仅记录到报告，不参与字段填充）")
    p_r.add_argument("--resume", help="resume.md 路径")
    p_r.add_argument("--fields", help="resume.fields.json 路径（优先级最高）")
    p_r.add_argument("--photo", help="证件照路径（默认自动取 简历库/00_个人信息/photos/）")
    p_r.add_argument("--no-photo", action="store_true", help="不替换照片")
    p_r.add_argument("--out", help="直接指定输出文件路径（优先级最高）")
    p_r.add_argument("--filename", help="输出文件名（不含目录）")
    p_r.add_argument("--date", help="归档日期，默认今天 YYYY-MM-DD")
    p_r.add_argument("--pattern", help="占位符语法覆盖")
    p_r.add_argument("--strip-color", action="append", default=["FF00FF"],
                     help="需要删除的补高标记颜色（可重复，默认 FF00FF）")
    p_r.add_argument("--no-shrink", action="store_true",
                     help="关闭超长字段自动缩字号")
    p_r.add_argument("--no-slot-align", action="store_true",
                     help="关闭空格对齐槽位保持（默认保持，防止职位/日期错位）")
    p_r.add_argument("--photo-part", help="指定要替换的图片部件（如 word/media/image1.png）")
    p_r.add_argument("--photo-all", action="store_true",
                     help="替换模板中所有位图（默认只替换最小的一张）")
    p_r.add_argument("--no-emit-fields", action="store_true",
                     help="不输出 *.fields.json 字段快照")
    p_r.add_argument("--no-notes", action="store_true",
                     help="不生成 generation_notes.md（默认生成，AGENT.md 要求产物目录必须有）")
    p_r.add_argument("--force", action="store_true",
                     help="输出文件已存在时不再提示（默认会提示将覆盖上一版）")
    p_r.add_argument("--supplement", action="store_true",
                     help="用简历库事实层补齐 resume.md 未写到的客观字段"
                          "（联系方式/证书等；绝不补经历描述，且已存在的值不覆盖）")
    p_r.set_defaults(func=cmd_render)

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
