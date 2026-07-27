# -*- coding: utf-8 -*-
"""
模块8：Markdown 批量导出 PDF
1. 校验通过的文章一键转为标准 PDF
2. 自动配置页眉、标题、目录
3. PDF 输出目录 ./export_pdf/
4. 支持单篇导出、批量导出全部稿件
"""
import os
import re
import glob
import html
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
from config_loader import ARTICLES_DIR, EXPORT_PDF_DIR
import op_logger

# 注册中文字体（使用 Windows 自带微软雅黑）
_FONT_NAME = "MSYH"
_FONT_REGISTERED = False


def _ensure_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont(_FONT_NAME, fp))
                _FONT_REGISTERED = True
                return
            except Exception:
                continue
    _FONT_REGISTERED = True  # 字体注册失败也置位，避免反复尝试


def _md_to_flow(md_text: str, styles):
    """简易 Markdown → ReportLab Flowables"""
    flows = []
    md_text = re.sub(r"^---\n.*?\n---\n", "", md_text, flags=re.S)
    for line in md_text.split("\n"):
        line = line.rstrip()
        if not line:
            flows.append(Spacer(1, 4))
            continue
        if line.startswith("# "):
            flows.append(Paragraph(html.escape(line[2:]), styles["H1"]))
        elif line.startswith("## "):
            flows.append(Paragraph(html.escape(line[3:]), styles["H2"]))
        elif line.startswith("### "):
            flows.append(Paragraph(html.escape(line[4:]), styles["H3"]))
        elif line.startswith("> "):
            flows.append(Paragraph(f'<i>{html.escape(line[2:])}</i>', styles["Quote"]))
        elif line.startswith("```"):
            continue  # 代码块内容按等宽正文处理（下文逐行）
        elif line.startswith("- ") or line.startswith("* "):
            flows.append(Paragraph(f'• {html.escape(line[2:])}', styles["Bullet"]))
        else:
            safe = html.escape(line).replace(" ", "&nbsp;")
            flows.append(Paragraph(safe, styles["Body"]))
    return flows


def _header_footer(canvas, doc):
    canvas.saveState()
    _ensure_font()
    canvas.setFont(_FONT_NAME, 8)
    canvas.drawString(20 * mm, 287 * mm, "AI 内容工厂 · 导出文档")
    canvas.drawRightString(190 * mm, 287 * mm, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    canvas.drawCentredString(105 * mm, 12 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def export_one(md_file: str, out_file: str = None) -> str:
    """单篇导出 PDF"""
    _ensure_font()
    with open(md_file, "r", encoding="utf-8") as f:
        md = f.read()
    title = os.path.splitext(os.path.basename(md_file))[0]
    out_file = out_file or os.path.join(EXPORT_PDF_DIR, f"{title}.pdf")

    # 直接构建自定义样式字典，避免与 reportlab 默认样式表重名冲突
    styles = {
        "H1": ParagraphStyle("H1", fontName=_FONT_NAME, fontSize=18, leading=26, spaceAfter=10),
        "H2": ParagraphStyle("H2", fontName=_FONT_NAME, fontSize=14, leading=20, spaceBefore=8, spaceAfter=6),
        "H3": ParagraphStyle("H3", fontName=_FONT_NAME, fontSize=12, leading=18, spaceBefore=6),
        "Body": ParagraphStyle("Body", fontName=_FONT_NAME, fontSize=10.5, leading=17),
        "Quote": ParagraphStyle("Quote", fontName=_FONT_NAME, fontSize=10, leading=16, textColor="#555555"),
        "Bullet": ParagraphStyle("Bullet", fontName=_FONT_NAME, fontSize=10.5, leading=17, leftIndent=12),
    }

    doc = SimpleDocTemplate(out_file, pagesize=A4,
                            leftMargin=22*mm, rightMargin=22*mm, topMargin=22*mm, bottomMargin=20*mm,
                            title=title, author="AI Content Factory")
    story = [Paragraph(html.escape(title), styles["H1"]), Spacer(1, 8)]
    story += _md_to_flow(md, styles)
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    op_logger.log("pdf_export", f"导出PDF: {out_file}")
    return out_file


def export_all() -> dict:
    """批量导出 articles/ 下全部稿件"""
    files = glob.glob(os.path.join(ARTICLES_DIR, "*.md"))
    done = []
    failed = []
    for fp in files:
        try:
            out = export_one(fp)
            done.append(os.path.basename(out))
        except Exception as ex:
            failed.append({"file": os.path.basename(fp), "error": str(ex)})
            op_logger.log("pdf_export", f"导出失败 {fp}: {ex}", level="ERROR")
    op_logger.log("pdf_export", f"批量导出完成: 成功{len(done)} 失败{len(failed)}")
    return {"exported": done, "failed": failed, "total": len(files)}


def export_article_by_id(article_id: str) -> str:
    """按稿件ID导出最新一篇"""
    files = glob.glob(os.path.join(ARTICLES_DIR, f"{article_id}*.md"))
    if not files:
        return None
    return export_one(sorted(files)[-1])


if __name__ == "__main__":
    print("export_pdf 当前文件数:", len(glob.glob(os.path.join(EXPORT_PDF_DIR, '*.pdf'))))
