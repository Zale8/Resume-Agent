# -*- coding: utf-8 -*-
"""冒烟测试：对模板库中每套模板验证「字段发现 → 填充 → 照片替换 → 溢出估算」。

不依赖 pytest，直接 python 运行。
本文件不含任何用户个人信息。
"""
from __future__ import annotations

import posixpath
import re
import sys
import tempfile
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))

from resume_generator import docx_engine as de  # noqa: E402
from resume_generator.paths import find_product_root  # noqa: E402

FAKE = {
    "NAME": "张三", "OBJ": "产品经理", "CITY": "北京", "TEL": "13800000000",
    "EML": "zhangsan@example.com", "SM": "某虚构大学应届生，具备项目落地经验。",
    "SM2": "补充第二段自我评价用于测试溢出。", "ETH": "汉族", "BIR": "2000.01",
    "POL": "群众", "HT": "175cm", "ADDR": "北京市海淀区",
    "SCH": "某虚构大学", "MAJ": "电气工程及其自动化", "DG": "本科",
    "EDD": "2023.09 - 2027.06", "CRS": "自动控制原理、电力电子技术",
    "CER1": "CET-4", "CER2": "计算机二级", "CER3": "普通话二甲",
    "CERTS": "CET-4；计算机二级",
    "SK1": "Python", "SK2": "Axure", "SK3": "Excel",
    "W1D": "2023.12 - 2024.03", "W1C": "某科技公司", "W1P": "测试实习生",
    "W1R1": "参与自动化测试流程，完成数据记录与异常排查。",
    "W1R2": "协助工程师定位问题并完成复测验证。",
    "W1R3": "跟进现场设备维护与故障处理闭环。",
    "W1A": "异常处理时效提升 20%",
    "W2D": "2026.07 - 2026.09", "W2C": "某汽车公司", "W2P": "制造工程实习生",
    "W2R1": "参与自动化产线设备巡检与点检。",
    "W2R2": "配合工程师完成设备调试与异常处理。",
    "W2A": "完成 30+ 次设备点检记录",
    "W3D": "2024.10 - 2026.06", "W3C": "某服务项目", "W3P": "项目负责人",
    "W3R1": "主导项目从需求调研到落地运营的全流程。",
    "C1D": "2024.09 - 2025.06", "C1N": "校学生会", "C1P": "部长",
    "C1R1": "统筹部门日常管理与任务分配。",
    "C1R2": "策划并组织校园主题活动。",
    "EX1": "流程设计", "EX2": "跨部门协作", "EX3": "数据化表达",
    "INT": "长跑、摄影",
}


def make_png(w: int = 120, h: int = 160) -> bytes:
    """生成一张最小合法 PNG（纯色），用于测试照片替换。"""
    import struct
    import zlib

    raw = b""
    for _ in range(h):
        raw += b"\x00" + bytes([200, 210, 220]) * w

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    root = find_product_root()
    tpl_root = root / "templates"
    templates = sorted(p for p in tpl_root.glob("template_*/template.docx"))
    if not templates:
        print(f"❌ 未找到任何模板：{tpl_root}")
        return 1

    photo = make_png()
    print(f"产品仓库根目录: {root}")
    print(f"发现模板 {len(templates)} 套\n")

    failures = 0
    for tpl in templates:
        name = tpl.parent.name
        print("=" * 68)
        print(f"### {name}")
        entries, order = de.read_zip(tpl)
        xml = entries[de.DOCUMENT_XML].decode("utf-8", "surrogateescape")

        pattern = de.detect_pattern(xml)
        fields = de.list_fields(xml, pattern)
        names = [f for f, _ in fields]
        repeat = [(f, c) for f, c in fields if c > 1]
        print(f"  占位符语法 : {pattern}")
        print(f"  发现字段   : {len(names)} 个")
        if repeat:
            print(f"  重复占位   : {repeat}")

        hint = de.image_placeholder_hint(entries)
        print(f"  图片部件   : {de.find_image_parts(entries)}")
        print(f"  照片占位   : {hint}")

        # 只填模板真正有的字段
        values = {k: v for k, v in FAKE.items() if k in names}
        missing_vals = [n for n in names if n not in values]
        print(f"  未提供值   : {missing_vals}")

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.docx"
            report = de.render(tpl, values, out, photo_path=None, pattern=pattern)

            assert out.exists(), "输出文件未生成"
            # 重新读回验证：不再有已填字段的残留标记
            e2, _ = de.read_zip(out)
            x2 = e2[de.DOCUMENT_XML].decode("utf-8", "surrogateescape")
            leftover = [
                n for n in report["filled"]  # type: ignore[union-attr]
                if f"{{{{{n}}}}}" in x2
            ]
            print(f"  已填充     : {len(report['filled'])} 个字段 / "
                  f"{sum(report['filled'].values())} 处替换")  # type: ignore[union-attr]
            print(f"  标记清理   : {report['marker_runs_removed']} 个补高 run")
            in_ov = report.get("inline_overflow") or []      # type: ignore[assignment]
            fl_ov = report.get("flow_overflow") or []        # type: ignore[assignment]
            print(f"  窄槽位超出 : {[n for n, _ in in_ov] or '无'}")
            print(f"  流式文本   : {len(fl_ov)} 个（自然换行，不缩字号）")
            print(f"  自动缩字号 : {report.get('shrunk_fields') or '无'}")
            ov = report["overflow"]  # type: ignore[assignment]
            print(f"  溢出估算   : {ov['visual_chars']} 视觉字符 ≈ "
                  f"{ov['approx_lines']} 行 / 容量 {ov['capacity_lines']} 行 "
                  f"-> {ov['verdict']}")
            print(f"  输出体积   : {report['size_bytes']} bytes")

            # 关键回归：mc:Choice / mc:Fallback 两个分支都必须被替换干净。
            # 只填一个分支会导致 Word 与其他阅读器显示不一致。
            # 注意：未提供值的字段在所有分支里都会保留占位符，这是设计如此，
            #       因此这里只统计「已提供值」的字段是否还有残留。
            fb_leftover: list[str] = []
            for block in de._FALLBACK_BLOCK.findall(x2):
                for m in de._TEXT_NODE.finditer(block):
                    body = m.group(4) or ""
                    for name in re.findall(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", body):
                        if name in values:
                            fb_leftover.append(name)
            print(f"  Fallback分支: {'已赋值字段全部替换' if not fb_leftover else '残留 ' + str(fb_leftover)}")

            if leftover:
                print(f"  ❌ 残留未替换标记: {leftover}")
                failures += 1
            elif fb_leftover:
                print(f"  ❌ mc:Fallback 分支未同步替换: {fb_leftover}")
                failures += 1
            elif missing_vals:
                print(f"  ⚠️  模板存在未赋值字段（设计如此，保持空白）：{missing_vals}")
            else:
                print("  ✅ 全部字段替换成功（含 Fallback 分支）")

            # 照片替换：必须走完整 render 链路验证，而不是只测 replace_photo。
            # 曾经的真实缺陷：replace_photo 改了图片扩展名却没同步更新 zip 写入
            # 顺序，导致照片部件根本没进产物，而关系文件仍指向它
            # —— 照片直接消失。只单测 replace_photo 发现不了这个问题。
            out2 = Path(td) / "out_photo.docx"
            photo_file = Path(td) / "photo.png"
            photo_file.write_bytes(photo)
            rep2 = de.render(tpl, values, out2, photo_path=photo_file, pattern=pattern)
            replaced = rep2.get("photo_replaced") or []
            print(f"  照片替换   : {replaced or '该模板无位图部件'}")

            if replaced:
                photo_problems = _check_package_integrity(out2)
                if photo_problems:
                    print(f"  ❌ 带照片产物包完整性: {photo_problems}")
                    failures += 1
                else:
                    print("  ✅ 带照片产物包完整"
                          "（关系目标均存在 / 照片字节已写入）")
                    # 确认写入的是我们的照片，而不是模板占位图
                    with zipfile.ZipFile(out2) as zf:
                        written = zf.read(replaced[0])
                    if written == photo:
                        print("  ✅ 照片字节与输入一致")
                    else:
                        print("  ❌ 照片字节与输入不一致")
                        failures += 1
            else:
                print("  ⚠️  该模板无位图部件，照片需手工放置")

    print("=" * 68)
    print("✅ 冒烟测试通过" if failures == 0 else f"❌ {failures} 套模板存在问题")
    return 0 if failures == 0 else 1


def _check_package_integrity(docx_path: Path) -> list[str]:
    """校验 docx 包的自洽性：每个关系目标都必须真实存在于 zip 中。

    这是「产物是否可被 Word/WPS 正常打开」的核心判据。
    关系指向不存在的部件会导致图片丢失，严重时 Word 报文件损坏。
    """
    problems: list[str] = []
    with zipfile.ZipFile(docx_path) as zf:
        names = set(zf.namelist())
        for rels_name in [n for n in names if n.endswith(".rels")]:
            # 关系文件所在目录 = 去掉 "_rels/xxx.rels" 后的前缀
            # 例：word/_rels/document.xml.rels -> base = "word"
            #     _rels/.rels                  -> base = ""
            base_dir = rels_name.rsplit("_rels/", 1)[0].rstrip("/")
            rels_xml = zf.read(rels_name).decode("utf-8", "surrogateescape")
            for m in re.finditer(r'Target="([^"]+)"', rels_xml):
                target = m.group(1)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("/"):
                    resolved = target.lstrip("/")
                else:
                    # 必须规范化 ../ 与 ./，否则会把存在的部件误判为缺失
                    joined = f"{base_dir}/{target}" if base_dir else target
                    resolved = posixpath.normpath(joined)
                if resolved not in names:
                    problems.append(f"{rels_name} -> {target}（解析为 {resolved}，zip 内不存在）")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
