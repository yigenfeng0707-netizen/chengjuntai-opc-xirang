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
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.enums import TA_LEFT
from config_loader import ARTICLES_DIR, EXPORT_PDF_DIR
import op_logger

# 中文字体名（运行时可能被 _ensure_font() 改写为 CID 回退名）
_FONT_NAME = "MSYH"
_FONT_REGISTERED = False

# Windows 候选 (regular, bold)
_WIN_CANDIDATES = [
    (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"),
    (r"C:\Windows\Fonts\msyh.ttf", r"C:\Windows\Fonts\msyhbd.ttf"),
    (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simhei.ttf"),
    (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simsun.ttc"),
]

# Linux 候选 (regular, bold) —— 覆盖 Noto CJK / WenQuanYi / 用户上传字体
_LINUX_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
     "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
     "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ("/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
     "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc"),
    (os.path.expanduser("~/.fonts/msyh.ttc"),
     os.path.expanduser("~/.fonts/msyhbd.ttc")),
    (os.path.expanduser("~/.fonts/msyh.ttf"),
     os.path.expanduser("~/.fonts/msyhbd.ttf")),
]


def _register_family(regular_path: str, bold_path: str, family_name: str) -> str:
    """注册单个字体族（regular + bold），并建立 family/bold/italic 映射。
    成功返回字体族名，供 _ensure_font 设置 _FONT_NAME。
    修复关键：必须 registerFontFamily，否则 <b>/<i> 标签会触发
    'Can't map determine family/bold/italic' 异常。"""
    reg_kwargs = {"subfontIndex": 0} if regular_path.lower().endswith(".ttc") else {}
    pdfmetrics.registerFont(TTFont(family_name, regular_path, **reg_kwargs))

    bold_name = family_name + "-Bold"
    if os.path.exists(bold_path) and os.path.abspath(bold_path) != os.path.abspath(regular_path):
        bold_kwargs = {"subfontIndex": 0} if bold_path.lower().endswith(".ttc") else {}
        pdfmetrics.registerFont(TTFont(bold_name, bold_path, **bold_kwargs))
    else:
        # 没有独立粗体文件，用 regular 顶替，避免 <b> 标签时找不到字体
        bold_name = family_name

    # 注册字体族：italic/boldItalic 无真正斜体文件，统一映射到 regular/bold
    # registerFontFamily 内部已建立 bold/italic 映射，无需额外 addMapping
    pdfmetrics.registerFontFamily(
        family_name,
        normal=family_name,
        bold=bold_name,
        italic=family_name,
        boldItalic=bold_name,
    )
    return family_name


def _ensure_font() -> str:
    """注册中文字体并返回当前生效的字体名。
    依次尝试 Windows 雅黑/黑体 → Linux Noto/WQY → reportlab 内置 CID 字体 STSong-Light。
    修复关键：必须 registerFontFamily + addMapping，否则 <b>/<i> 标签会触发
    'Can't map determine family/bold/italic' 异常。"""
    global _FONT_REGISTERED, _FONT_NAME
    if _FONT_REGISTERED:
        return _FONT_NAME

    candidates = _WIN_CANDIDATES + _LINUX_CANDIDATES
    for regular_path, bold_path in candidates:
        if not os.path.exists(regular_path):
            continue
        try:
            _FONT_NAME = _register_family(regular_path, bold_path, "MSYH")
            _FONT_REGISTERED = True
            op_logger.log("pdf_export", f"字体注册成功: {regular_path}")
            return _FONT_NAME
        except Exception as ex:
            op_logger.log("pdf_export", f"字体注册失败 {regular_path}: {ex}", level="WARN")
            continue

    # 最终回退：reportlab 内置 CID 中文字体（无需外部字体文件）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _FONT_NAME = "STSong-Light"
        _FONT_REGISTERED = True
        op_logger.log("pdf_export", "回退使用内置 CID 字体 STSong-Light（中文可正常显示，但无粗体变体）", level="WARN")
        return _FONT_NAME
    except Exception as ex:
        op_logger.log("pdf_export", f"CID 字体回退也失败: {ex}", level="ERROR")

    _FONT_REGISTERED = True  # 避免反复尝试，但此时 PDF 导出大概率会失败
    return _FONT_NAME


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
