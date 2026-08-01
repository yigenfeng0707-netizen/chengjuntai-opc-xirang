# -*- coding: utf-8 -*-
"""生成息壤杯预赛提交用专业答辩 PPTX（≤100MB）。"""
from __future__ import annotations

import os
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt, Emu

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "成军台_息壤杯预赛答辩.pptx"

INK = RGBColor(0x0F, 0x1C, 0x2E)
TEAL = RGBColor(0x0D, 0x94, 0x88)
TEAL_DK = RGBColor(0x0F, 0x76, 0x6E)
SAND = RGBColor(0xE8, 0xF0, 0xEE)
MUTED = RGBColor(0x64, 0x74, 0x8B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xCB, 0xD5, 0xE1)


def _blank(prs: Presentation):
    return prs.slide_layouts[6]


def _bg(slide, color: RGBColor):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _rect(slide, l, t, w, h, color: RGBColor):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh


def _text(slide, l, t, w, h, text, size=20, bold=False, color=INK, align=PP_ALIGN.LEFT, font="Microsoft YaHei"):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font
    return box


def _bullets(slide, l, t, w, h, items, size=18, color=INK):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = "•  " + item
        p.level = 0
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.name = "Microsoft YaHei"
        p.space_after = Pt(8)
    return box


def _footer(slide, page: int, total: int = 12):
    _text(
        slide, Inches(0.5), Inches(7.15), Inches(8), Inches(0.3),
        f"成军台 · 息壤杯预赛  |  {page}/{total}",
        size=11, color=MUTED,
    )


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # 1 Cover
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, INK)
    _rect(s, Inches(0), Inches(0), Inches(0.18), Inches(7.5), TEAL)
    _text(s, Inches(0.8), Inches(1.6), Inches(11), Inches(0.4), "2026 息壤杯 · 惠民产品创新 · AI+自选开放场景", 16, False, TEAL)
    _text(s, Inches(0.8), Inches(2.2), Inches(11), Inches(1.0), "成军台", 54, True, WHITE)
    _text(s, Inches(0.8), Inches(3.3), Inches(11), Inches(0.5), "息壤育智 · 一人成军", 26, False, TEAL)
    _text(s, Inches(0.8), Inches(4.1), Inches(11), Inches(0.8), "目标驱动的一人公司 AI 作战系统\n多 Agent 协同 · 人审卡点 · Word 成军周报 · 真政采问数", 16, False, RGBColor(0xCB, 0xD5, 0xE1))
    _text(s, Inches(0.8), Inches(6.4), Inches(11), Inches(0.4), "OPC OS on 息壤 ｜ 仓库见提交材料", 12, False, MUTED)

    # 2 Pain
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "痛点：缺的是操作系统，不是又一个对话框", 28, True, INK)
    _bullets(s, Inches(0.9), Inches(1.5), Inches(11), Inches(4.5), [
        "一人公司 / 超级个体：活是一支团队的量，缺编辑部与作战台",
        "Chat 套壳：不可验收、无协作、无周报，无法交付给客户或上级",
        "政企侧：内容种草、标讯情报、标书材料割裂，缺统一闭环",
        "评委要的是可点通的路径，不是概念 PPT",
    ], 20)
    _footer(s, 2)

    # 3 Solution
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "一句话方案", 28, True, INK)
    _rect(s, Inches(0.7), Inches(1.3), Inches(11.8), Inches(1.4), WHITE)
    _text(s, Inches(0.95), Inches(1.55), Inches(11.3), Inches(1.0),
          "输入目标 → 司令拆任务 → AI 员工矩阵执行 → 人审卡点 → 一键导出 Word 成军周报",
          20, True, TEAL_DK)
    _bullets(s, Inches(0.9), Inches(3.1), Inches(11), Inches(3.2), [
        "增量能力：内容工厂（种草话术）· 标书工作台 · 浙江政采真实标讯 NL2SQL",
        "底座：中国电信息壤 / 星辰 TokenHub · 天翼云可部署",
        "赛道：惠民产品创新 · AI+自选开放场景",
    ], 18)
    _footer(s, 3)

    # 4 Judge 60s
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "评委 60 秒路径（零讲解）", 28, True, INK)
    steps = [
        ("01", "点评委 60 秒体验", "自动登录 judge，打开获客样例战役"),
        ("02", "看产物抽屉", "调研 / 内容 / 问数 / 运营可预览验收"),
        ("03", "① 导出 Word", "成军周报一键下载，交付不是聊天记录"),
        ("04", "② 智能问数一表", "真库出表；离线则明确标注缓存样例"),
    ]
    for i, (n, title, desc) in enumerate(steps):
        x = Inches(0.6 + (i % 2) * 6.2)
        y = Inches(1.35 + (i // 2) * 2.5)
        _rect(s, x, y, Inches(5.9), Inches(2.2), WHITE)
        _text(s, x + Inches(0.25), y + Inches(0.25), Inches(1), Inches(0.4), n, 22, True, TEAL)
        _text(s, x + Inches(0.25), y + Inches(0.75), Inches(5.3), Inches(0.4), title, 18, True, INK)
        _text(s, x + Inches(0.25), y + Inches(1.25), Inches(5.3), Inches(0.7), desc, 14, False, MUTED)
    _footer(s, 4)

    # 5 Agent matrix
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "AI 员工矩阵", 28, True, INK)
    roles = [
        ("调研官", "渠道 / 竞品情报"),
        ("内容官", "种草文案与话术包"),
        ("数据参谋", "NL2SQL 真标讯问数"),
        ("运营官", "跟进表与节奏"),
        ("复盘官", "周报结构与总结"),
    ]
    for i, (name, duty) in enumerate(roles):
        x = Inches(0.5 + i * 2.5)
        _rect(s, x, Inches(1.8), Inches(2.3), Inches(3.2), WHITE)
        _rect(s, x, Inches(1.8), Inches(2.3), Inches(0.12), TEAL)
        _text(s, x + Inches(0.15), Inches(2.2), Inches(2.0), Inches(0.5), name, 18, True, TEAL_DK, PP_ALIGN.CENTER)
        _text(s, x + Inches(0.15), Inches(3.0), Inches(2.0), Inches(1.4), duty, 14, False, MUTED, PP_ALIGN.CENTER)
    _footer(s, 5)

    # 6 Architecture
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "技术架构（可演示）", 28, True, INK)
    _bullets(s, Inches(0.9), Inches(1.4), Inches(11), Inches(5), [
        "Web：FastAPI + 成军看板 / 内容工厂 / 标书工作台（同屏协作）",
        "编排：战役状态机 · 人审门 · 多 Agent 级联（大纲→写作→初审）",
        "数据：bid_telecom.db 真实政采标讯 + NL2SQL MCP（8765）/ znws（8082）",
        "模型：息壤 primary（wishub-x6）级联 TokenPlan / SenseNova；禁止静默 mock",
        "交付：Markdown 源稿 + Word 导出 · MCP 工具封装 · 天翼云部署脚本",
    ], 18)
    _footer(s, 6)

    # 7 Real data
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "真实数据与可验收产物", 28, True, INK)
    _bullets(s, Inches(0.9), Inches(1.5), Inches(11), Inches(5), [
        "浙江政采公开标讯入库（演示库数百条量级，可刷新）",
        "种草内容包写作注入真实统计，初审约束「示例 / 来源」标注",
        "样例战役周包种子化：评委无需等长推理也能走通 60 秒",
        "产物可预览、可导出 Word、可同步内容工厂 / 推入标书知识库",
    ], 18)
    _footer(s, 7)

    # 8 Five dimensions
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "五大评审维度对位", 28, True, INK)
    dims = [
        ("创新性", "一人成军 OS，而非 Chat 套壳"),
        ("商业模式", "席位 + Token + 模板战役包"),
        ("社会价值", "降低一人公司数字化门槛"),
        ("应用成效", "60 秒可走通 + Word 可交"),
        ("孵化潜力", "息壤/天翼云亲和 · 政企可延伸"),
    ]
    for i, (k, v) in enumerate(dims):
        y = Inches(1.25 + i * 1.0)
        _rect(s, Inches(0.7), y, Inches(11.8), Inches(0.85), WHITE)
        _text(s, Inches(0.95), y + Inches(0.22), Inches(2.4), Inches(0.45), k, 16, True, TEAL)
        _text(s, Inches(3.5), y + Inches(0.22), Inches(8.5), Inches(0.45), v, 16, False, INK)
    _footer(s, 8)

    # 9 Business
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "商业与社会价值", 28, True, INK)
    _bullets(s, Inches(0.9), Inches(1.5), Inches(11), Inches(5), [
        "用户：OPC / 超级个体 / 小微经营者 / 政企一线内容与投标协同",
        "收费：订阅席位 + Token 用量 + 行业战役模板包",
        "惠民：一个人也能完成调研→内容→跟进→复盘的可验收闭环",
        "电信亲和：息壤算力与星辰模型主链路，天翼云公网 Demo 可部署",
    ], 18)
    _footer(s, 9)

    # 10 Demo proof
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "演示证明（提交材料对齐）", 28, True, INK)
    _bullets(s, Inches(0.9), Inches(1.5), Inches(11), Inches(5), [
        "演示视频：≤60 秒 · 1080p · 硬烧字幕 · 评委 CTA→Word→问数",
        "本 PPT：预赛提交「演示 PPT / 商业计划书」",
        "代码仓库：github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang",
        "账号：评委只读 judge（口令见现场说明，勿写入公开截图）",
        "截止：2026-08-20 · 智云 Store 惠民赛道上传",
    ], 18)
    _footer(s, 10)

    # 11 Roadmap
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, SAND)
    _text(s, Inches(0.7), Inches(0.45), Inches(11), Inches(0.5), "下一步（复赛 / 决赛）", 28, True, INK)
    _bullets(s, Inches(0.9), Inches(1.5), Inches(11), Inches(5), [
        "公网 Demo HTTPS 加固与评委账号隔离",
        "战役模板库扩展（更多行业 / 政企场景）",
        "内容→公众号草稿→成效回流的运营闭环加深",
        "标书证据矩阵与材料包自动化加强",
    ], 18)
    _footer(s, 11)

    # 12 Thanks
    s = prs.slides.add_slide(_blank(prs))
    _bg(s, INK)
    _rect(s, Inches(0), Inches(0), Inches(0.18), Inches(7.5), TEAL)
    _text(s, Inches(0.8), Inches(2.4), Inches(11), Inches(0.8), "谢谢评委", 44, True, WHITE)
    _text(s, Inches(0.8), Inches(3.4), Inches(11), Inches(0.5), "息壤育智 · 一人成军", 24, False, TEAL)
    _text(s, Inches(0.8), Inches(4.3), Inches(11), Inches(0.8), "成军台 · 欢迎现场体验「评委 60 秒」路径", 16, False, RGBColor(0xCB, 0xD5, 0xE1))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"OK {OUT} ({size_mb:.2f} MB)")
    return OUT


if __name__ == "__main__":
    build()
