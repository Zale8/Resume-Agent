# -*- coding: utf-8 -*-
"""Render original + processed docx to PNG via Word COM (PDF) + pymupdf."""
import os, sys, glob
import win32com.client as win32
import fitz  # pymupdf

desktop = r'C:\Users\13032\Desktop'
proj = [d for d in os.listdir(desktop) if 'DJgqY5KXSOKw' in d][0]
TPL_DIR = os.path.join(desktop, proj, 'Resume-Agent', 'templates')
OUT = os.path.join(desktop, '_preview')
os.makedirs(OUT, exist_ok=True)

jobs = [
    ('t01_orig', os.path.join(desktop, 'jianli-00100职业风简历模板word免费版.docx')),
    ('t01_new',  os.path.join(TPL_DIR, 'template_01', 'template.docx')),
    ('t02_orig', os.path.join(desktop, 'jianli-0046蓝色好看的简历模板.docx')),
    ('t02_new',  os.path.join(TPL_DIR, 'template_02', 'template.docx')),
    ('t03_orig', os.path.join(desktop, 'jianli-0085双色个性简历模板免费.docx')),
    ('t03_new',  os.path.join(TPL_DIR, 'template_03', 'template.docx')),
    ('t04_orig', os.path.join(desktop, 'jianli-0026黑色风简历模板免费使用.docx')),
    ('t04_new',  os.path.join(TPL_DIR, 'template_04', 'template.docx')),
]

word = win32.DispatchEx('Word.Application')
word.Visible = False
word.DisplayAlerts = 0
try:
    for tag, path in jobs:
        pdf_path = os.path.join(OUT, tag + '.pdf')
        doc = word.Documents.Open(path, ReadOnly=True)
        doc.ExportAsFixedFormat(pdf_path, 17)  # wdExportFormatPDF
        doc.Close(False)
        print('PDF:', tag)
        d = fitz.open(pdf_path)
        for i, page in enumerate(d):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
            png = os.path.join(OUT, f'{tag}_p{i+1}.png')
            pix.save(png)
            print('  PNG:', png, pix.width, 'x', pix.height)
        d.close()
finally:
    word.Quit()
print('DONE')
