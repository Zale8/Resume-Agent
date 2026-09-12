# -*- coding: utf-8 -*-
"""template_kit.py — 把「用户上传的任意 docx」标准化为 Resume-Agent 可用模板。

解决的问题
----------
用户从网上（Canva / 五百丁 / WPS 模板站 / 学校发的模板 / HR 给的模板）下载一份
docx，希望直接用起来。此前没有工具能把它变成可用模板，只能靠手工改造。

本模块做的事
------------
1. 读取 docx，探测它用的是哪种占位符语法（{{}} / [[ ]] / [[]] / 【】 / %% 等）
2. 若不是标准 {{FIELD}} 语法，自动改写成 {{FIELD}}（只改文本，不动版式）
3. 若模板里根本没有占位符，则根据常见中文标签自动植入占位符
   （如把「姓名」单元格变成 {{NAME}}）—— 这一步默认关闭，需显式开启
4. 识别照片占位图
5. 生成 template.json / field_mapping.md / template_config.md

仅依赖标准库。本文件不含任何用户个人信息，不含任何绝对路径。
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import docx_engine as de

# 没有占位符时，用于自动植入的中文标签 -> 规范字段名
CN_LABEL_SEEDS: Sequence[Tuple[str, str]] = (
    ("姓名", "NAME"), ("名字", "NAME"),
    ("出生年月", "BIR"), ("出生日期", "BIR"), ("生日", "BIR"),
    ("民族", "ETH"), ("政治面貌", "POL"), ("身高", "HT"),
    ("籍贯", "ADDR"), ("住址", "ADDR"), ("现居地", "ADDR"), ("地址", "ADDR"),
    ("电话", "TEL"), ("手机", "TEL"), ("联系电话", "TEL"), ("联系方式", "TEL"),
    ("邮箱", "EML"), ("电子邮箱", "EML"),
    ("求职意向", "OBJ"), ("应聘岗位", "OBJ"), ("期望职位", "OBJ"), ("目标岗位", "OBJ"),
    ("学校", "SCH"), ("毕业院校", "SCH"), ("院校", "SCH"),
    ("专业", "MAJ"), ("学历", "DG"), ("学位", "DG"),
    ("主修课程", "CRS"), ("相关课程", "CRS"),
    ("自我评价", "SM"), ("个人简介", "SM"), ("自我介绍", "SM"),
    ("技能", "SK1"), ("专业技能", "SK1"),
    ("证书", "CERTS"), ("资格证书", "CERTS"),
    ("兴趣爱好", "INT"), ("爱好", "INT"),
)

# 非标准占位符语法 -> 内部字段名（用于自动改写）
FOREIGN_PATTERNS: Dict[str, str] = {
    "double_bracket": r"\[\[\s*([A-Za-z0-9_]+)\s*\]\]",       # [[NAME]]
    "double_percent": r"%%\s*([A-Za-z0-9_]+)\s*%%",           # %%NAME%%
    "hash": r"##\s*([A-Za-z0-9_]+)\s*##",                     # ##NAME##
    "at": r"@@\s*([A-Za-z0-9_]+)\s*@@",                       # @@NAME@@
    "underscore": r"__([A-Za-z0-9_]+)__",                     # __NAME__
    "html": r"<!--\s*([A-Za-z0-9_]+)\s*-->",                  # <!--NAME-->
}


class NoMarkerFound(de.TemplateError):
    """模板中既没有占位符，也无法自动植入。"""


# ============================================================================
# 元数据
# ============================================================================

def load_template_meta(tpl_dir: Path) -> Dict[str, object]:
    """读取模板目录下的 template.json，缺失则返回空字典。"""
    path = tpl_dir / "template.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ============================================================================
# 占位符改写
# ============================================================================

def rewrite_foreign_markers(xml: str) -> Tuple[str, int, Optional[str]]:
    """把非标准占位符统一改写成 {{FIELD}}。

    返回 (新 xml, 改写数量, 命中的语法名)
    """
    for name, pattern in FOREIGN_PATTERNS.items():
        compiled = re.compile(pattern)
        if not compiled.search(xml):
            continue

        count = [0]

        def repl(m: re.Match) -> str:
            count[0] += 1
            return "{{" + m.group(1).upper() + "}}"

        # 只在文本节点内改写，避免碰到 XML 属性
        def run_repl(rm: re.Match) -> str:
            run = rm.group(0)
            if not compiled.search(run):
                return run

            def node_repl(nm: re.Match) -> str:
                tag, attrs = nm.group(1), nm.group(2) or ""
                if nm.group(3) == "/>":
                    return nm.group(0)
                body = nm.group(4) or ""
                return f"<{tag}{attrs}>{compiled.sub(repl, body)}</{tag}>"

            return de._TEXT_NODE.sub(node_repl, run)

        return de._RUN.sub(run_repl, xml), count[0], name
    return xml, 0, None


def seed_markers_from_labels(xml: str) -> Tuple[str, int]:
    """把「标签：值」形态的模板转成占位符形态。

    只处理文本节点中「标签」后面紧跟空白或标点的场景，把紧邻的占位值替换为
    {{FIELD}}。保守策略：只在标签**独占**一个文本节点时植入占位符
    （例如单元格里写的就是「姓名」），避免破坏正文。

    返回 (新 xml, 植入数量)。
    """
    seeded = 0

    def node_repl(nm: re.Match) -> str:
        nonlocal seeded
        tag, attrs = nm.group(1), nm.group(2) or ""
        if nm.group(3) == "/>":
            return nm.group(0)
        body = nm.group(4) or ""
        stripped = body.strip()
        if not stripped or "{{" in stripped:
            return nm.group(0)
        for label, field in CN_LABEL_SEEDS:
            if stripped == label:
                seeded += 1
                return f"<{tag}{attrs}>{{{{{field}}}}}</{tag}>"
        return nm.group(0)

    return de._TEXT_NODE.sub(node_repl, xml), seeded


# ============================================================================
# 标准化主流程
# ============================================================================

def standardize_template(
    src_docx: Path,
    out_dir: Path,
    name_cn: str = "",
    style: str = "",
    description: str = "",
    pattern: Optional[str] = None,
    seed_from_labels: bool = True,
) -> Dict[str, object]:
    """把任意 docx 标准化为 Resume-Agent 模板目录。

    产出：
        <out_dir>/template.docx
        <out_dir>/template.json
        <out_dir>/field_mapping.md
        <out_dir>/template_config.md
    """
    src_docx = Path(src_docx)
    entries, order = de.read_zip(src_docx)
    xml = entries[de.DOCUMENT_XML].decode("utf-8", "surrogateescape")
    original_xml = xml

    # 1) 探测已有的标准占位符
    existing = de.list_fields(xml)
    converted = 0
    used_foreign: Optional[str] = None

    if not existing:
        # 2) 尝试改写非标准占位符
        xml, converted, used_foreign = rewrite_foreign_markers(xml)

    seeded = 0
    if not de.list_fields(xml) and seed_from_labels:
        # 3) 兜底：按中文标签植入
        xml, seeded = seed_markers_from_labels(xml)

    fields = de.list_fields(xml, pattern)
    if not fields:
        raise NoMarkerFound(
            f"模板中找不到任何占位符，也无法自动植入：{src_docx.name}\n\n"
            "这个模板需要先做人工标记。三种做法（任选其一）：\n"
            "  1) 用 Word 打开模板，把需要填的位置改成 {{NAME}}、{{SCH}} 这类标记；\n"
            "     （花括号要打两遍，即 {{ 和 }}，Word 不会吞掉）\n"
            "  2) 若模板已有自己的标记语法，用 --pattern 指定：\n"
            "     python gen.py standardize 模板.docx --pattern '\\[\\[(\\w+)\\]\\]'\n"
            f"     可用预设：{', '.join(de.MARKER_PRESETS)}\n"
            "  3) 换一份带 {{字段}} 标记的模板，或用 templates/ 下现有模板。"
        )

    resolved_pattern = de.resolve_pattern(xml, pattern)
    names = [f for f, _ in fields]

    # ---- 写盘 ----
    out_dir.mkdir(parents=True, exist_ok=True)
    entries[de.DOCUMENT_XML] = xml.encode("utf-8", "surrogateescape")
    de.write_zip(entries, order, out_dir / "template.docx")

    photo_hint = de.image_placeholder_hint(entries)
    images = de.find_image_parts(entries)

    align = _infer_photo_shape(entries, photo_hint)

    meta = {
        "template_name": out_dir.name,
        "name_cn": name_cn or out_dir.name,
        "version": "1.0",
        "style": style or "待确认",
        "description": description or "",
        # 只记文件名，不记绝对路径（跨机器可移植）
        "source_file": src_docx.name,
        "standardized_at": _dt.date.today().isoformat(),        "pattern": resolved_pattern,
        "fields": {f: "{{" + f + "}}" for f in names},
        "field_count": len(names),
        "photo": {
            "field": "{{PHOTO}}",
            "part": photo_hint,
            "shape": align[0],
            "ratio": align[1],
        },
        "notes": [
            "本文件由 gen.py standardize 自动生成",
            "fields 的取值说明请人工补全（见 field_mapping.md）",
        ],
    }
    (out_dir / "template.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    (out_dir / "field_mapping.md").write_text(
        _build_field_mapping_md(out_dir.name, meta, fields, images, photo_hint),
        encoding="utf-8",
    )
    (out_dir / "template_config.md").write_text(
        _build_template_config_md(out_dir.name, meta, src_docx, used_foreign,
                                  converted, seeded),
        encoding="utf-8",
    )

    return {
        "out_dir": str(out_dir),
        "pattern": resolved_pattern,
        "fields": fields,
        "field_count": len(fields),
        "images": images,
        "photo_hint": photo_hint,
        "converted_markers": converted,
        "seed_markers": seeded,
        "foreign_syntax": used_foreign,
        "xml_changed": xml != original_xml,
    }


def _infer_photo_shape(
    entries: Dict[str, bytes], photo_hint: Optional[str]
) -> Tuple[str, str]:
    """从占位图的实际像素比例推断照片形状。"""
    if not photo_hint or photo_hint not in entries:
        return ("unknown", "unknown")
    size = de.image_size(entries[photo_hint])
    if not size or not size[0] or not size[1]:
        return ("unknown", "unknown")
    w, h = size
    ratio = w / h
    if abs(ratio - 1.0) < 0.06:
        return ("square", "1:1")
    if abs(ratio - 3 / 4) < 0.08:
        return ("portrait", "3:4")
    if abs(ratio - 4 / 3) < 0.08:
        return ("landscape", "4:3")
    from math import gcd
    g = gcd(w, h) or 1
    return ("custom", f"{w // g}:{h // g}")


def _build_field_mapping_md(
    name: str,
    meta: Dict[str, object],
    fields: List[Tuple[str, int]],
    images: List[str],
    photo_hint: Optional[str],
) -> str:
    photo = meta.get("photo", {})                    # type: ignore[assignment]
    lines = [
        f"# {name} 字段映射表",
        "",
        f"**模板名称**：{meta.get('name_cn')}",
        f"**风格**：{meta.get('style')}",
        f"**来源文件**：{meta.get('source_file')}",
        f"**照片**：{photo.get('shape')}（比例 {photo.get('ratio')}）",  # type: ignore[union-attr]
        "",
        "## 字段清单（请人工补全「含义」与「简历库路径」）",
        "",
        "| 模板字段 | 出现次数 | 含义（待补） | 简历库路径（待补） |",
        "|---|---|---|---|",
    ]
    for field, count in fields:
        lines.append(f"| `{{{{{field}}}}}` | {count} | 待补充 | 待补充 |")

    lines += [
        "",
        "## 标准字段名参考（建议对齐 AGENT.md 的字段词典）",
        "",
        "| 类别 | 字段名 |",
        "|---|---|",
        "| 个人信息 | NAME / OBJ / CITY / TEL / EML / ADDR / BIR / ETH / POL / HT |",
        "| 教育 | SCH / MAJ / DG / EDD / CRS |",
        "| 自我评价 | SM / SM2 |",
        "| 实习 | W{n}D / W{n}C / W{n}P / W{n}R{m} / W{n}A |",
        "| 项目 | P{n}D / P{n}N / P{n}P / P{n}R{m} |",
        "| 校园 | C{n}D / C{n}N / C{n}P / C{n}R{m} |",
        "| 技能 | SK{n} |",
        "| 证书奖项 | CER{n} / CERTS / AW{n} |",
        "| 优势兴趣 | EX{n} / INT |",
        "",
        "> n 为条目序号（1 起），m 为描述行序号（1 起）。",
        "",
        "## 照片处理",
        "",
        f"- 图片部件：{', '.join(images) if images else '无'}",
        f"- 照片占位图：{photo_hint or '未识别到'}",
        "- 渲染时默认只替换体积最小的位图（防误伤图标 / logo）",
        "- 如需指定部件：`--photo-part word/media/image1.png`",
        "- 如需替换全部位图：`--photo-all`",
        "",
        "## 备注",
        "",
        "- 所有 `{{FIELD}}` 标记均位于单个 `<w:t>` run 内，可精确替换",
        "- 字段在模板中出现多次时（如页眉 + 正文），渲染会全部填入同一个值",
        "- 不支持动态增减条目（固定条目数），缺失条目留空",
    ]
    return "\n".join(lines) + "\n"


def _build_template_config_md(
    name: str,
    meta: Dict[str, object],
    src: Path,
    foreign_syntax: Optional[str],
    converted: int,
    seeded: int,
) -> str:
    lines = [
        f"# {name} 配置说明",
        "",
        # 只记文件名，不记绝对路径：避免把某台机器的路径固化进产品仓库
        f"- 来源文件：`{src.name}`",
        f"- 标准化日期：{meta.get('standardized_at')}",
        f"- 占位符语法：`{meta.get('pattern')}`",
        f"- 字段数量：{meta.get('field_count')}",
        f"- 照片占位：{meta.get('photo', {}).get('part') if isinstance(meta.get('photo'), dict) else None}",  # type: ignore[union-attr]
        "",
        "## 标准化过程中做了什么",
        "",
    ]
    if foreign_syntax:
        lines.append(f"- 识别到非标准占位符语法 `{foreign_syntax}`，已自动改写 "
                     f"{converted} 处为 `{{{{FIELD}}}}`")
    elif converted:
        lines.append(f"- 改写非标准占位符 {converted} 处")
    else:
        lines.append("- 模板原本已使用标准 `{{FIELD}}` 语法，未改写")
    if seeded:
        lines.append(f"- 按中文标签自动植入占位符 {seeded} 处（请人工核对是否正确）")
    lines += [
        "",
        "## 使用方式",
        "",
        "```bash",
        f"python gen.py render --template {name} \\",
        "    --company 目标公司 --role 目标岗位 \\",
        "    --resume /路径/to/resume.md",
        "```",
        "",
        "## 待人工确认项",
        "",
        "- [ ] `template.json` 中 `fields` 的字段含义是否与模板位置一致",
        "- [ ] 照片占位图是否识别正确（若不是，用 --photo-part 指定）",
        "- [ ] 渲染一次后目视检查版式是否被破坏",
        "- [ ] 字段数量是否足够表达一份完整简历（不足则考虑增补占位符）",
    ]
    return "\n".join(lines) + "\n"


def copy_template_dir(src_dir: Path, dst_dir: Path) -> None:
    """整目录复制模板（保留 preview 等附属文件）。"""
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
