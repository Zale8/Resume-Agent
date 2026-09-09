# -*- coding: utf-8 -*-
"""Regenerate template_config.md / template.json / field_mapping.md for v3 schema,
and copy rendered PNGs as preview.png."""
import os, json, shutil

desktop = r'C:\Users\13032\Desktop'
proj = [d for d in os.listdir(desktop) if 'DJgqY5KXSOKw' in d][0]
TPL = os.path.join(desktop, proj, 'Resume-Agent', 'templates')
PREVIEW = os.path.join(desktop, '_preview')

# ---- field meaning & resume-lib path ----
FM = {
    'NAME': ('姓名', '个人信息.姓名'),
    'OBJ':  ('求职意向', '求职意向.目标岗位'),
    'BIR':  ('出生年月', '个人信息.出生年月'),
    'CITY': ('城市', '个人信息.城市'),
    'TEL':  ('电话', '个人信息.电话'),
    'EML':  ('邮箱', '个人信息.邮箱'),
    'ADDR': ('住址', '个人信息.住址'),
    'ETH':  ('民族', '个人信息.民族'),
    'HT':   ('身高', '个人信息.身高'),
    'POL':  ('政治面貌', '个人信息.政治面貌'),
    'SCH':  ('学校', '教育经历[0].学校'),
    'DG':   ('学历', '教育经历[0].学历'),
    'MAJ':  ('专业', '教育经历[0].专业'),
    'EDD':  ('教育日期', '教育经历[0].日期'),
    'CRS':  ('主修课程', '教育经历[0].主修课程'),
    'SM':   ('自我评价', '个人优势.自我评价'),
    'SM2':  ('自我评价（第二段）', '个人优势.自我评价_第二段'),
    'SK1':  ('技能1', '专业技能.技能[0]'),
    'SK2':  ('技能2', '专业技能.技能[1]'),
    'SK3':  ('技能3', '专业技能.技能[2]'),
    'CER1': ('证书1', '证书奖项.证书[0]'),
    'CER2': ('证书2', '证书奖项.证书[1]'),
    'CER3': ('证书3', '证书奖项.证书[2]'),
    'CERTS':('证书（合并）', '证书奖项.证书'),
    'AW1':  ('奖项1', '证书奖项.奖项[0]'),
    'AW2':  ('奖项2', '证书奖项.奖项[1]'),
    'AW3':  ('奖项3', '证书奖项.奖项[2]'),
    'AW4':  ('奖项4', '证书奖项.奖项[3]'),
    'EX1':  ('优势特长1', '个人优势.特长[0]'),
    'EX2':  ('优势特长2', '个人优势.特长[1]'),
    'EX3':  ('优势特长3', '个人优势.特长[2]'),
    'INT':  ('兴趣爱好', '个人优势.兴趣爱好'),
    'W1D':  ('工作1日期', '实习经历[0].日期'),
    'W1C':  ('工作1公司', '实习经历[0].公司'),
    'W1P':  ('工作1职位', '实习经历[0].职位'),
    'W1R1': ('工作1描述1', '实习经历[0].描述[0]'),
    'W1R2': ('工作1描述2', '实习经历[0].描述[1]'),
    'W1R3': ('工作1描述3', '实习经历[0].描述[2]'),
    'W1A':  ('工作1成果', '实习经历[0].成果'),
    'W2D':  ('工作2日期', '实习经历[1].日期'),
    'W2C':  ('工作2公司', '实习经历[1].公司'),
    'W2P':  ('工作2职位', '实习经历[1].职位'),
    'W2R1': ('工作2描述1', '实习经历[1].描述[0]'),
    'W2R2': ('工作2描述2', '实习经历[1].描述[1]'),
    'W2A':  ('工作2成果', '实习经历[1].成果'),
    'W3D':  ('工作3日期', '实习经历[2].日期'),
    'W3C':  ('工作3公司', '实习经历[2].公司'),
    'W3P':  ('工作3职位', '实习经历[2].职位'),
    'W3R1': ('工作3描述1', '实习经历[2].描述[0]'),
    'C1D':  ('校园1日期', '校园经历[0].日期'),
    'C1N':  ('校园1组织', '校园经历[0].组织'),
    'C1P':  ('校园1职位', '校园经历[0].职位'),
    'C1R1': ('校园1描述1', '校园经历[0].描述[0]'),
    'C1R2': ('校园1描述2', '校园经历[0].描述[1]'),
}

TEMPLATES = {
    'template_01': dict(
        name_cn='职业风（稳重正式）', style='稳重正式',
        source='jianli-00100职业风简历模板word免费版.docx',
        desc='左右分栏，左侧联系方式+技能，右侧教育+工作+证书+奖项，适合国企/传统行业',
        applicable='国企、传统行业、制造、硬件工程师类岗位',
        style_desc='稳重、正式、专业',
        layout='左右分栏；左侧窄栏：联系方式+技能水平；右侧宽栏：教育背景+工作经验+证书+奖项',
        photo_desc='方形 1:1，位于左上角', font='微软雅黑，标题加粗配分割线',
        color='深色标题 + 灰色正文，点缀色 #3C444F',
        photo_shape='square', photo_ratio='1:1',
        work_entries='3 段（固定）', edu_entries='1 段（固定）',
        campus_entries=None, skill_entries='3 个技能名称（固定）',
        fields=['NAME','OBJ','CITY','TEL','EML','SM','SM2','SK1','SK2','SK3',
                'EDD','SCH','MAJ','DG','CRS','CER1','CER2','CER3',
                'AW1','AW2','AW3','AW4',
                'W1D','W1C','W1P','W1R1','W2D','W2C','W2P','W2R1','W3D','W3C','W3P','W3R1',
                'EX1','EX2','EX3','INT'],
        br_marker=True,
    ),
    'template_02': dict(
        name_cn='蓝色简约（简约科技）', style='简约科技',
        source='jianli-0046蓝色好看的简历模板.docx',
        desc='单栏表格布局，顶部个人信息+照片 → 教育 → 自我评价 → 技能证书 → 校园经历 → 实习经历，适合互联网/产品类',
        applicable='AI产品运营、AI应用、互联网、产品类岗位',
        style_desc='简约、现代、蓝色主题',
        layout='单栏表格布局；顶部个人信息表 → 教育背景 → 自我评价 → 技能证书 → 校园经历 → 实习经历',
        photo_desc='竖版 3:4，位于个人信息表左侧', font='微软雅黑，蓝色标题 #254665',
        color='蓝色主色调 + 白色背景',
        photo_shape='portrait', photo_ratio='3:4',
        work_entries='2 段（固定）', edu_entries='1 段（固定）',
        campus_entries='1 段（固定）', skill_entries=None,
        fields=['NAME','ETH','TEL','EML','ADDR','BIR','HT','POL',
                'SCH','DG','EDD','MAJ','CRS','SM','CER1','CER2','CER3',
                'C1D','C1N','C1P','C1R1','C1R2',
                'W1D','W1C','W1P','W1R1','W1R2','W2D','W2C','W2P','W2R1','W2R2'],
        br_marker=False,
    ),
    'template_03': dict(
        name_cn='双色个性（个性双色）', style='个性双色',
        source='jianli-0085双色个性简历模板免费.docx',
        desc='单栏布局，顶部个人信息 → 教育 → 自我评价 → 实习经历 → 校园经历 → 技能证书，适合创意/市场类',
        applicable='创意、设计、传媒、市场类岗位',
        style_desc='个性、双色装饰、活泼',
        layout='单栏布局；顶部个人信息 → 教育背景 → 自我评价 → 实习经历 → 校园经历 → 技能证书',
        photo_desc='竖版 3:4，位于个人信息区域', font='微软雅黑，双色标题点缀',
        color='双色对比 + 白色背景',
        photo_shape='portrait', photo_ratio='3:4',
        work_entries='2 段（固定）', edu_entries='1 段（固定）',
        campus_entries='1 段（固定）', skill_entries=None,
        fields=['NAME','ETH','TEL','EML','ADDR','BIR','HT','POL',
                'SCH','DG','EDD','MAJ','CRS','SM','CER1','CER2','CER3',
                'W1D','W1C','W1P','W1R1','W1R2','W2D','W2C','W2P','W2R1','W2R2',
                'C1D','C1N','C1P','C1R1','C1R2'],
        br_marker=False,
    ),
    'template_04': dict(
        name_cn='黑色风（极简科技）', style='极简科技',
        source='jianli-0026黑色风简历模板免费使用.docx',
        desc='单栏布局，顶部姓名+意向 → 联系方式 → 教育 → 自我评价 → 奖项证书 → 工作经验，适合技术/工程类',
        applicable='技术、研发、工程、开发类岗位',
        style_desc='极简、黑色主色调、专业',
        layout='单栏布局；顶部姓名+求职意向 → 联系方式 → 教育背景 → 自我评价 → 奖项证书 → 工作经验',
        photo_desc='方形 1:1，位于右上角', font='微软雅黑，黑色加粗标题',
        color='黑白为主，点缀色深灰',
        photo_shape='square', photo_ratio='1:1',
        work_entries='2 段（固定，含成果字段）', edu_entries='1 段（固定）',
        campus_entries=None, skill_entries=None,
        fields=['NAME','OBJ','BIR','CITY','TEL','EML',
                'EDD','SCH','MAJ','DG','CRS','SM','SM2','AW1','AW2','CERTS',
                'W1D','W1C','W1P','W1R1','W1R2','W1R3','W1A',
                'W2D','W2C','W2P','W2R1','W2R2','W2A'],
        br_marker=False,
    ),
}

def gen_config_md(tid, d):
    lines = [f'# 模板配置 - {tid}', '', '| 配置项 | 内容 |', '|---|---|']
    lines.append(f"| 模板名称 | {d['name_cn']} |")
    lines.append(f"| 源文件 | {d['source']} |")
    lines.append(f"| 适用岗位 | {d['applicable']} |")
    lines.append(f"| 风格 | {d['style_desc']} |")
    lines.append(f"| 页面布局 | {d['layout']} |")
    lines.append(f"| 照片 | {d['photo_desc']} |")
    lines.append(f"| 字体 | {d['font']} |")
    lines.append(f"| 颜色 | {d['color']} |")
    lines.append(f"| 字段数 | {len(d['fields'])} |")
    lines.append(f"| 工作经历条目 | {d['work_entries']} |")
    lines.append(f"| 教育经历条目 | {d['edu_entries']} |")
    if d['campus_entries']:
        lines.append(f"| 校园经历条目 | {d['campus_entries']} |")
    if d['skill_entries']:
        lines.append(f"| 技能展示 | {d['skill_entries']} |")
    if d['br_marker']:
        lines.append('| 纵向补齐 | t01 含品红(FF00FF) br 标记 run，填充引擎替换字段前需删除 |')
    return '\n'.join(lines) + '\n'

def gen_json(tid, d):
    fields = {k: '{{' + k + '}}' for k in d['fields']}
    return json.dumps({
        'template_name': tid,
        'name_cn': d['name_cn'],
        'version': '3.0',
        'style': d['style'],
        'description': d['desc'],
        'photo': {'field': '{{PHOTO}}', 'shape': d['photo_shape'], 'ratio': d['photo_ratio']},
        'fields': fields,
        'field_count': len(d['fields']),
        'br_marker': d['br_marker'],
    }, ensure_ascii=False, indent=2) + '\n'

def gen_mapping_md(tid, d):
    lines = [f'# {tid} 字段映射表', '',
             f"**模板名称**：{d['name_cn']}",
             f"**风格**：{d['style']}",
             f"**照片**：{d['photo_shape']}（比例 {d['photo_ratio']}）", '',
             '## 字段映射', '',
             '| 模板字段 | 简历库路径 | 说明 |',
             '|----------|------------|------|']
    for k in d['fields']:
        desc, path = FM[k]
        lines.append(f"| `{{{{{k}}}}}` | `{path}` | {desc} |")
    lines += ['', '## 照片处理', '',
              '- 照片位置已替换为灰色占位图',
              f"- 生成简历时：用真实证件照覆盖 `word/media/image1.*`",
              f"- 照片形状：{d['photo_shape']}", '']
    lines.append('## 备注')
    lines.append('')
    lines.append('- 所有 `{{FIELD}}` 标记均位于单个 `<w:t>` run 内，可直接精确替换')
    lines.append('- 不支持动态增减条目（固定条目数），缺失条目留空字符串')
    if d['br_marker']:
        lines.append('- **t01 特有**：含品红(FF00FF) `<w:br/>` 标记 run，用于纵向高度补齐；填充引擎在替换字段前必须先删除这些标记 run')
    return '\n'.join(lines) + '\n'

for tid, d in TEMPLATES.items():
    tdir = os.path.join(TPL, tid)
    # preview.png
    idx = tid.split('_')[1]
    src_png = os.path.join(PREVIEW, f't{idx}_new_p1.png')
    dst_png = os.path.join(tdir, 'preview.png')
    shutil.copy2(src_png, dst_png)
    print(f'{tid}: preview.png updated')
    # config files
    with open(os.path.join(tdir, 'template_config.md'), 'w', encoding='utf-8') as f:
        f.write(gen_config_md(tid, d))
    with open(os.path.join(tdir, 'template.json'), 'w', encoding='utf-8') as f:
        f.write(gen_json(tid, d))
    with open(os.path.join(tdir, 'field_mapping.md'), 'w', encoding='utf-8') as f:
        f.write(gen_mapping_md(tid, d))
    n = len(d['fields'])
    print(f'{tid}: {n} fields, config/json/mapping regenerated')

print('DONE')
