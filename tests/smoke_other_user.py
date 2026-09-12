# -*- coding: utf-8 -*-
"""临时测试（用完即删）：验证「换人 / 换位置 / 不改代码」能否跑通。

在系统临时目录下另建一套完全虚构的简历库，目录名故意不叫「简历库」，
内容全是假的，再从该目录运行产品仓库的 gen.py，验证：
    1. 路径自动发现能找到这个陌生位置的简历库
    2. 代码里没有任何针对特定用户/特定路径的假设
    3. 产物正确落回该简历库的岗位定制简历目录
    4. 产物内容是正确的虚构用户数据，且绝不含真实用户信息
    5. 产品仓库内没有被写入任何用户数据
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

PRODUCT = Path(__file__).resolve().parent.parent
GEN = PRODUCT / "gen.py"

FAKE_LIB: dict[str, str] = {
    "00_个人信息/个人信息.md": """# 个人信息

| 字段 | 内容 |
|---|---|
| 姓名 | 李示例 |
| 手机号 | 13900000001 |
| 邮箱 | lishili@example.com |
| 所在城市 | 上海 |
| 求职城市 | 上海 |
| 出生年月 | 2001.05 |
| 民族 | 汉族 |
| 政治面貌 | 共青团员 |
""",
    "01_教育经历/本科_示例大学.md": """# 教育经历

| 字段 | 内容 |
|---|---|
| 学校 | 示例大学 |
| 院系 | 计算机学院 |
| 专业 | 软件工程 |
| 学历 | 本科 |
| 入学时间 | 2022.09 |
| 毕业时间 | 2026.06 |

## 主修课程

数据结构、操作系统、数据库原理、软件工程
""",
    "02_实习经历/示例科技_后端开发实习生.md": """# 实习经历

| 字段 | 内容 |
|---|---|
| 公司 | 示例科技有限公司 |
| 岗位 | 后端开发实习生 |
| 起止时间 | 2025.07 - 2025.09 |
| 行业 | 互联网 |
| 业务方向 | 服务端研发 |

## 原始事实

- 参与订单服务接口开发
- 编写单元测试并修复缺陷
""",
    "05_专业技能/编程.md": """# 编程

## 工具

- Java
- Python
- MySQL
""",
    "07_个人优势/自我评价.md": """# 自我评价

## 原始自我评价

> 示例大学软件工程专业应届生，具备后端开发实习经历，熟悉 Java 与数据库开发。
""",
    "08_证书奖项/证书奖项.md": """# 证书奖项

| 类别 | 名称 | 备注 |
|---|---|---|
| 证书 | 大学英语六级（CET-6） | |
| 证书 | 计算机等级考试二级 | |
| 比赛 | 待补充 | |
""",
    "99_配置/style_preferences.md": "# 设计风格偏好\n\n未设置（待测试）\n",
}

RESUME_MD = """# 李示例 - 后端开发工程师

**示例大学 | 软件工程 | 2026届**

**求职意向**：后端开发工程师

> 具备软件工程专业背景与后端开发实习经历，参与订单服务接口开发与缺陷修复。

---

## 教育经历

**示例大学 | 软件工程（本科） | 2022.09 - 2026.06**

- 主修课程：数据结构、操作系统、数据库原理、软件工程

---

## 实习经历

### 示例科技有限公司 | 后端开发实习生 | 2025.07 - 2025.09

> 互联网行业服务端研发

- 参与订单服务接口开发，完成接口联调与文档编写
- 编写单元测试并修复缺陷，提升模块稳定性

---

## 专业技能

**编程语言**：Java / Python / SQL

---

## 证书奖项

| 类别 | 名称 | 备注 |
|---|---|---|
| 证书 | 大学英语六级（CET-6） | |
| 证书 | 计算机等级考试二级 | |

---

## 自我评价

示例大学软件工程专业应届生，具备后端开发实习经历。熟悉 Java 与数据库开发，注重工程质量。
"""

JD_MD = """# 某科技有限公司 - 后端开发工程师

## 岗位职责
1. 负责核心业务系统的服务端设计与开发；
2. 参与接口性能优化与稳定性建设。

## 任职要求
1. 本科及以上学历，计算机相关专业；
2. 熟悉 Java、MySQL，了解常用数据结构与算法；
3. 具备良好的工程习惯，有单元测试意识。
"""


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GEN), *argv], cwd=cwd,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def load_real_terms(repo: Path) -> list[str]:
    """从仓库外的简历库读取真实用户敏感词（用于「产物不含真实信息」比对）。

    刻意不硬编码真实姓名/学校/公司名 —— 那会把它们写进产品仓库，本身即泄漏。
    """
    try:
        sys.path.insert(0, str(repo / "src"))
        from resume_generator.paths import find_resume_lib
        terms_file = find_resume_lib() / "99_配置" / "privacy_terms.txt"
    except Exception:      # noqa: BLE001 - 定位失败则跳过比对
        return []
    if not terms_file.is_file():
        return []
    terms = []
    for raw in terms_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^[>#*\-+\s]+", "", line).strip("`*_ \t")
        if line and 2 <= len(line) <= 30 and not re.search(r"[，。；：、,.;:!?！？]", line):
            terms.append(line)
    return terms


def safe_rmtree(path: Path) -> None:
    """Windows 上 docx 可能仍被句柄占用，重试几次再放弃。"""
    for _ in range(6):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.3)
    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="otheruser_"))
    try:
        return _checks(work)
    finally:
        safe_rmtree(work)


def _checks(work: Path) -> int:
    failures = 0

    # 故意放在与产品仓库毫无关系的深层层级，且目录名不叫「简历库」
    lib = work / "深层" / "目录" / "层级" / "resume_lib_data"
    for rel, text in FAKE_LIB.items():
        path = lib / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    print(f"虚构简历库位置：{lib}")
    print(f"产品仓库位置  ：{PRODUCT}\n")

    base = lib / "09_岗位定制简历" / "某科技公司" / "后端开发工程师" / "2026-01-01"
    base.mkdir(parents=True, exist_ok=True)
    (base / "resume.md").write_text(RESUME_MD, encoding="utf-8")
    jd = lib / "11_岗位JD" / "2026-01-01_某科技公司_后端开发工程师.md"
    jd.parent.mkdir(parents=True, exist_ok=True)
    jd.write_text(JD_MD, encoding="utf-8")

    # ---- 1. doctor 自动发现陌生位置的简历库 ----
    print("### 1. 从无关目录运行 doctor（路径自动发现）")
    proc = run(["doctor"], cwd=lib)
    ok = "resume_lib" in proc.stdout and str(lib) in proc.stdout
    print(f"  {'✅' if ok else '❌'} 自动定位到虚构简历库")
    if not ok:
        failures += 1
        print(proc.stdout[-600:])

    # ---- 2. render 不传 --lib / --out ----
    print("\n### 2. 渲染（不传 --lib，不传 --out，靠自动发现 + 自动归档）")
    proc = run([
        "render", "--template", "template_02",
        "--company", "某科技公司", "--role", "后端开发工程师",
        "--jd", str(jd), "--resume", str(base / "resume.md"),
        "--supplement",
    ], cwd=lib)
    out_docx = base / "李示例_某科技公司_后端开发工程师.docx"

    for label, ok in [
        ("渲染成功", proc.returncode == 0),
        ("姓名自动识别为李示例", "李示例" in proc.stdout),
        ("产物落在 resume.md 旁边", out_docx.exists()),
        ("生成说明已产出", (base / "generation_notes.md").exists()),
        ("字段快照已产出",
         (base / "李示例_某科技公司_后端开发工程师.fields.json").exists()),
    ]:
        print(f"  {'✅' if ok else '❌'} {label}")
        if not ok:
            failures += 1

    if proc.returncode != 0:
        print("\n--- stdout ---\n" + proc.stdout[-2000:])
        print("--- stderr ---\n" + proc.stderr[-1500:])

    # ---- 3. 产物内容核对 ----
    if out_docx.exists():
        print("\n### 3. 产物内容核对")
        with zipfile.ZipFile(out_docx) as z:
            doc = z.read("word/document.xml").decode("utf-8")

        for label, expect in [
            ("含虚构姓名", "李示例"),
            ("含虚构公司", "示例科技"),
            ("含虚构学校", "示例大学"),
            ("含虚构邮箱", "lishili@example.com"),
            ("含证书 CET-6", "CET-6"),
            ("含第二证书", "计算机等级考试二级"),
        ]:
            ok = expect in doc
            print(f"  {'✅' if ok else '❌'} {label}（{expect}）")
            if not ok:
                failures += 1

        print("  --- 绝不能含真实用户信息 ---")
        # 真实用户的姓名/学校/公司名**不能硬编码在本文件里**（那本身就是一次泄漏）。
        # 从仓库外的词表读取：简历库/99_配置/privacy_terms.txt
        real_terms = load_real_terms(PRODUCT)
        if real_terms:
            for term in real_terms:
                ok = term not in doc
                print(f"  {'✅' if ok else '❌'} 不含真实信息「{term}」")
                if not ok:
                    failures += 1
        else:
            print("  ⏭️  未找到仓库外敏感词表，跳过真实信息比对")
            print("      （在 简历库/99_配置/privacy_terms.txt 写入真实姓名/学校/公司名即可启用）")

        leftover = sorted(set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", doc)))
        # 该虚构用户确实没有：校园经历、第二段实习、身高，
        # 证书也只有 2 个真实项（第 3 行是「待补充」已被过滤）—— 留空均正确。
        expected_empty = {
            "HT", "CER3",
            "C1D", "C1N", "C1P", "C1R1", "C1R2",
            "W2D", "W2C", "W2P", "W2R1", "W2R2",
        }
        unexpected = [f for f in leftover if f not in expected_empty]
        ok = not unexpected
        print(f"  {'✅' if ok else '❌'} 残留占位符仅限该用户确实没有的数据"
              f"（残留 {leftover}；意外 {unexpected}）")
        if not ok:
            failures += 1

    # ---- 4. 产品仓库未被写入用户数据 ----
    print("\n### 4. 产品仓库未被写入任何用户数据")
    stray = []
    me = Path(__file__).name
    for path in PRODUCT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".md", ".json", ".txt"}:
            continue
        if path.name == me:      # 本测试脚本自身必须含虚构数据
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "李示例" in text or "示例科技" in text:
            stray.append(path.relative_to(PRODUCT).as_posix())
    ok = not stray
    print(f"  {'✅' if ok else '❌'} 无泄漏（命中：{stray}）")
    if not ok:
        failures += 1

    print("\n" + "=" * 64)
    if failures:
        print(f"❌ {failures} 项未通过")
        return 1
    print("✅ 换人 / 换位置 / 不改代码 —— 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
