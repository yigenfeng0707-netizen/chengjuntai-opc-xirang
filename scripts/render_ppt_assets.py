# -*- coding: utf-8 -*-
"""Render high-DPI Pillow stills for contest PPT (16:9 / 1920×1080)."""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "ppt"

W, H = 1920, 1080
INK = (15, 28, 46)
INK_MID = (22, 40, 64)
TEAL = (13, 148, 136)
TEAL_LT = (45, 212, 191)
TEAL_DK = (15, 118, 110)
SAND = (232, 240, 238)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)
SLATE = (100, 116, 139)
GLASS = (255, 255, 255, 28)
GLASS_DK = (8, 18, 32, 180)
ROW_ALT = (248, 250, 252)
CHIP_HI = (254, 243, 199)
CHIP_OK = (204, 251, 241)

FONT_REG = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BD if bold and FONT_BD.exists() else FONT_REG
    try:
        return ImageFont.truetype(str(path), size, index=0)
    except OSError:
        return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def mesh_bg(seed: int = 7, dark: bool = True) -> Image.Image:
    rng = random.Random(seed)
    base = INK if dark else SAND
    img = Image.new("RGB", (W, H), base)
    px = img.load()
    c1 = TEAL_DK if dark else (180, 220, 214)
    c2 = (30, 58, 95) if dark else (200, 230, 236)
    for y in range(H):
        t = y / H
        row = _lerp(base, c2, t * 0.55)
        for x in range(0, W, 4):
            n = 0.5 + 0.5 * math.sin(x * 0.004 + y * 0.003 + seed)
            col = _lerp(row, c1, n * 0.35)
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = col
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for _ in range(18):
        x = rng.randint(-200, W)
        y = rng.randint(-200, H)
        r = rng.randint(120, 420)
        col = (*TEAL_LT, rng.randint(12, 38)) if dark else (*TEAL, rng.randint(18, 40))
        d.ellipse([x, y, x + r, y + r], fill=col)
    # geometric grid accents
    for i in range(0, W, 80):
        d.line([(i, 0), (i, H)], fill=(*TEAL, 18 if dark else 28), width=1)
    for j in range(0, H, 80):
        d.line([(0, j), (W, j)], fill=(*TEAL, 12 if dark else 22), width=1)
    # diagonal slash
    d.polygon([(W * 0.62, 0), (W, 0), (W, H), (W * 0.48, H)], fill=(*TEAL, 22 if dark else 30))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return img.filter(ImageFilter.GaussianBlur(radius=0.6))


def rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def brand_header(draw, title: str, subtitle: str = "", dark: bool = True):
    fg = WHITE if dark else INK
    sub = TEAL_LT if dark else TEAL_DK
    draw.text((72, 48), "成军台", font=font(28, True), fill=TEAL_LT if dark else TEAL)
    draw.text((72, 96), title, font=font(44, True), fill=fg)
    if subtitle:
        draw.text((72, 160), subtitle, font=font(22), fill=sub)
    # accent bar
    draw.rectangle([72, 210, 220, 216], fill=TEAL)


def save(img: Image.Image, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    img.save(path, "PNG", optimize=True)
    print(f"  {path.name}  {path.stat().st_size / 1024:.0f} KB")
    return path


def render_cover() -> Path:
    img = mesh_bg(11, dark=True).convert("RGBA")
    d = ImageDraw.Draw(img)
    # left glass panel
    rounded_rect(d, [56, 160, 1180, 920], 28, GLASS_DK, (*TEAL, 80), 2)
    d.rectangle([56, 160, 68, 920], fill=TEAL)
    d.text((110, 240), "2026 息壤杯 · 惠民 · AI+自选开放场景", font=font(24), fill=TEAL_LT)
    d.text((110, 320), "成军台", font=font(96, True), fill=WHITE)
    d.text((110, 450), "息壤育智 · 一人成军", font=font(40, True), fill=TEAL_LT)
    d.text(
        (110, 540),
        "目标驱动的一人公司 AI 作战系统\n多 Agent 协同 · 人审卡点 · Word 成军周报 · 真政采问数",
        font=font(26),
        fill=MUTED,
        spacing=12,
    )
    # right metric chips
    chips = [
        ("~382", "真实政采标讯"),
        ("60s", "评委零讲解路径"),
        ("5", "AI 员工角色"),
        ("Word", "可验收周报"),
    ]
    y = 220
    for val, lab in chips:
        rounded_rect(d, [1280, y, 1840, y + 140], 20, GLASS_DK, (*TEAL, 70), 2)
        d.text((1320, y + 28), val, font=font(42, True), fill=TEAL_LT)
        d.text((1320, y + 82), lab, font=font(22), fill=MUTED)
        y += 168
    d.text((110, 860), "OPC OS on 息壤 ｜ github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang", font=font(18), fill=SLATE)
    return save(img.convert("RGB"), "01_cover.png")


def render_pain() -> Path:
    img = mesh_bg(3, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "痛点：缺的是操作系统", "不是又一个对话框", dark=False)
    cards = [
        ("01", "团队量级的活", "一人公司 / 超级个体\n活是一支团队的量\n缺编辑部与作战台"),
        ("02", "Chat 套壳失效", "不可验收 · 无协作\n无周报 · 无法交付\n给客户或上级"),
        ("03", "政企链路割裂", "种草 · 标讯 · 标书\n各自为战\n缺统一闭环"),
    ]
    for i, (n, title, body) in enumerate(cards):
        x0 = 72 + i * 600
        rounded_rect(d, [x0, 280, x0 + 560, 920], 24, (255, 255, 255, 230), (*TEAL, 60), 2)
        d.rectangle([x0, 280, x0 + 560, 292], fill=TEAL)
        d.text((x0 + 40, 330), n, font=font(36, True), fill=TEAL)
        d.text((x0 + 40, 400), title, font=font(32, True), fill=INK)
        d.text((x0 + 40, 500), body, font=font(24), fill=SLATE, spacing=14)
    d.text((72, 980), "评委要的是可点通的路径，不是概念 PPT", font=font(22, True), fill=TEAL_DK)
    return save(img.convert("RGB"), "02_pain.png")


def render_solution() -> Path:
    img = mesh_bg(5, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "一句话方案", "惠民 · AI+自选 · 息壤底座", dark=False)
    steps = ["输入目标", "司令拆任务", "AI 员工执行", "人审卡点", "Word 周报"]
    x = 80
    y = 320
    for i, s in enumerate(steps):
        rounded_rect(d, [x, y, x + 280, y + 120], 18, WHITE, TEAL, 3)
        d.text((x + 28, y + 38), s, font=font(26, True), fill=INK)
        if i < len(steps) - 1:
            d.polygon([(x + 300, y + 50), (x + 330, y + 60), (x + 300, y + 70)], fill=TEAL)
        x += 360
    # bottom feature strip
    feats = [
        ("内容工厂", "种草话术闭环"),
        ("标书工作台", "证据矩阵 · Word"),
        ("真政采 NL2SQL", "浙江标讯问数"),
        ("息壤 / 星辰", "双轨 LLM 诚信"),
    ]
    for i, (a, b) in enumerate(feats):
        x0 = 80 + i * 460
        rounded_rect(d, [x0, 560, x0 + 430, 880], 20, (255, 255, 255, 235), (*TEAL, 50), 2)
        d.text((x0 + 36, 620), a, font=font(28, True), fill=TEAL_DK)
        d.text((x0 + 36, 700), b, font=font(24), fill=SLATE)
    return save(img.convert("RGB"), "03_solution.png")


def render_timeline() -> Path:
    img = mesh_bg(9, dark=True).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "评委 60 秒路径", "零讲解 · 自己点也能走通", dark=True)
    steps = [
        ("01", "点评委体验", "自动登录 judge\n打开获客样例战役"),
        ("02", "看产物抽屉", "调研 / 内容 / 问数\n运营可预览验收"),
        ("03", "导出 Word", "成军周报一键下载\n交付不是聊天记录"),
        ("04", "智能问数", "真库出表；离线\n明确标注缓存样例"),
    ]
    # timeline rail
    d.line([(140, 520), (1780, 520)], fill=TEAL, width=6)
    for i, (n, title, body) in enumerate(steps):
        cx = 220 + i * 430
        d.ellipse([cx - 28, 492, cx + 28, 548], fill=TEAL)
        d.text((cx - 16, 500), n[-1], font=font(28, True), fill=WHITE)
        rounded_rect(d, [cx - 160, 600, cx + 180, 920], 20, GLASS_DK, (*TEAL, 80), 2)
        d.text((cx - 130, 640), title, font=font(28, True), fill=WHITE)
        d.text((cx - 130, 720), body, font=font(22), fill=MUTED, spacing=10)
        d.text((cx - 130, 300), n, font=font(48, True), fill=TEAL_LT)
    return save(img.convert("RGB"), "04_timeline_60s.png")


def render_agent_matrix() -> Path:
    img = mesh_bg(13, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "AI 员工矩阵", "一人输入目标 · 五类角色并行 · 产物可验收", dark=False)
    roles = [
        ("调研官", "渠道 / 竞品情报", "Research"),
        ("内容官", "种草文案与话术包", "Content"),
        ("数据参谋", "NL2SQL 真标讯问数", "Data"),
        ("运营官", "跟进表与节奏", "Ops"),
        ("复盘官", "周报结构与总结", "Review"),
    ]
    for i, (name, duty, en) in enumerate(roles):
        x0 = 56 + i * 370
        rounded_rect(d, [x0, 280, x0 + 340, 920], 22, WHITE, (*TEAL, 70), 2)
        d.rectangle([x0, 280, x0 + 340, 420], fill=INK)
        d.text((x0 + 28, 310), en.upper(), font=font(16), fill=TEAL_LT)
        d.text((x0 + 28, 350), name, font=font(34, True), fill=WHITE)
        # icon circle
        cy = 560
        d.ellipse([x0 + 110, cy - 50, x0 + 230, cy + 70], outline=TEAL, width=4)
        d.text((x0 + 145, cy - 10), str(i + 1), font=font(36, True), fill=TEAL)
        d.text((x0 + 28, 700), duty, font=font(22), fill=SLATE)
        d.text((x0 + 28, 820), "产物进抽屉", font=font(18, True), fill=TEAL_DK)
    return save(img.convert("RGB"), "05_agent_matrix.png")


def render_architecture() -> Path:
    img = mesh_bg(17, dark=True).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "技术架构（可演示）", "工程底座可走通 · 禁止静默 mock", dark=True)

    def box(x, y, w, h, title, sub, fill=GLASS_DK):
        rounded_rect(d, [x, y, x + w, y + h], 16, fill, (*TEAL, 90), 2)
        d.text((x + 24, y + 22), title, font=font(24, True), fill=WHITE)
        d.text((x + 24, y + 62), sub, font=font(18), fill=MUTED)

    box(80, 280, 400, 140, "用户目标 / Web", "FastAPI · 成军看板")
    box(560, 280, 400, 140, "司令 Agent", "拆任务 · 模板战役")
    box(1040, 280, 400, 140, "战役状态机", "人审门 · 级联执行")
    # arrow lines
    for x0, x1 in [(480, 560), (960, 1040)]:
        d.line([(x0, 350), (x1, 350)], fill=TEAL_LT, width=3)

    agents = ["调研", "内容", "数据", "运营", "复盘"]
    for i, a in enumerate(agents):
        x = 80 + i * 360
        box(x, 500, 320, 120, f"{a} Agent", "并行产物", fill=(13, 148, 136, 55))

    outs = [
        (80, "产物抽屉 / Word", "可预览 · 成军周报导出"),
        (520, "内容工厂", "种草话术 · 初审门"),
        (960, "标书工作台", "证据矩阵 · 材料包"),
        (1400, "NL2SQL + 标讯库", "MCP/znws · ~382 真库"),
    ]
    for x, t, sub in outs:
        box(x, 700, 400, 120, t, sub)
    d.text((80, 900), "Primary：息壤 wishub-x6 ｜ Interim：TokenPlan / SenseNova ｜ 无 Key 明确失败", font=font(20), fill=MUTED)
    return save(img.convert("RGB"), "06_architecture.png")


def render_metrics() -> Path:
    img = mesh_bg(19, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "真实数据与可验收产物", "浙江政采公开标讯入库 · 可刷新", dark=False)
    metrics = [
        ("~382", "真实标讯条数", "owner=real"),
        ("~12", "演示标讯", "样例兜底"),
        ("2", "标准战役周包", "获客 + 综述"),
        ("4", "问数产物位", "可预览验收"),
    ]
    for i, (v, lab, sub) in enumerate(metrics):
        x0 = 72 + i * 460
        rounded_rect(d, [x0, 280, x0 + 430, 520], 22, WHITE, (*TEAL, 60), 2)
        d.text((x0 + 36, 320), v, font=font(64, True), fill=TEAL)
        d.text((x0 + 36, 410), lab, font=font(26, True), fill=INK)
        d.text((x0 + 36, 460), sub, font=font(20), fill=SLATE)
    bullets = [
        "种草内容包写作注入真实统计；初审约束「示例 / 来源」标注",
        "样例战役周包种子化：评委无需等长推理也能走通 60 秒",
        "产物可预览、可导出 Word、可同步内容工厂 / 推入标书知识库",
    ]
    rounded_rect(d, [72, 580, 1848, 980], 22, WHITE, (*TEAL, 50), 2)
    for i, b in enumerate(bullets):
        d.ellipse([110, 640 + i * 100, 130, 660 + i * 100], fill=TEAL)
        d.text((160, 630 + i * 100), b, font=font(26), fill=INK)
    return save(img.convert("RGB"), "07_metrics.png")


def render_evidence_matrix() -> Path:
    """Professional evidence-matrix table still (Pillow, not native pptx table)."""
    img = mesh_bg(21, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "标书证据矩阵（示意）", "要求拆解 → 证据 → 负责人 → 优先级 · 一键导出 Word", dark=False)

    headers = ["要求类型", "摘要", "证据来源", "负责人", "优先级"]
    rows = [
        ("资质", "近三年类似业绩", "业绩证明扫描件", "售前", "高"),
        ("技术", "NL2SQL 问数能力", "Demo + 架构说明", "研发", "高"),
        ("交付", "成军周报 Word", "样例导出包", "交付", "中"),
        ("安全", "密钥仅环境变量", "PROD_HARDENING", "运维", "高"),
        ("惠民", "降低一人公司门槛", "60s 路径 + 叙事", "产品", "中"),
        ("数据", "真政采标讯入库", "bid_telecom.db ~382", "数据", "高"),
    ]
    # table geometry
    x0, y0 = 72, 260
    col_w = [220, 420, 420, 240, 220]
    row_h = 88
    # header
    cx = x0
    for i, h in enumerate(headers):
        rounded_rect(d, [cx, y0, cx + col_w[i] - 8, y0 + row_h - 6], 10, INK)
        d.text((cx + 20, y0 + 26), h, font=font(22, True), fill=WHITE)
        cx += col_w[i]
    for r, row in enumerate(rows):
        cy = y0 + (r + 1) * row_h
        bg = WHITE if r % 2 == 0 else ROW_ALT
        cx = x0
        for i, cell in enumerate(row):
            fill = bg
            if i == 4 and cell == "高":
                fill = CHIP_HI
            elif i == 4 and cell == "中":
                fill = CHIP_OK
            rounded_rect(d, [cx, cy, cx + col_w[i] - 8, cy + row_h - 6], 8, fill, (226, 232, 240), 1)
            d.text((cx + 18, cy + 28), cell, font=font(20), fill=INK)
            cx += col_w[i]
    d.text((72, 980), "材料工作台：粘贴招标文本 → 要求拆解 → 生成证据矩阵 → 导出 Word 附卷", font=font(20), fill=TEAL_DK)
    return save(img.convert("RGB"), "08_evidence_matrix.png")


def render_five_dim() -> Path:
    """Radar + score bars for five contest dimensions."""
    img = mesh_bg(23, dark=True).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "五大评审维度对位", "创新在 OS · 实用在周报 · 完整在 60 秒 · 技术在多智能体 · 价值在惠民", dark=True)

    dims = [
        ("创新性", 0.92, "一人成军 OS，而非 Chat 套壳"),
        ("实用性", 0.90, "60 秒可走通 + Word 可交"),
        ("完整性", 0.88, "周包 + 工厂 + 问数 + 标书"),
        ("技术实现", 0.90, "多 Agent · NL2SQL · 真库"),
        ("商业社会", 0.86, "席位+Token · 惠民门槛"),
    ]

    # radar
    cx, cy, R = 520, 620, 280
    n = len(dims)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(*TEAL, 80), width=2)
    d.ellipse([cx - R * 0.66, cy - R * 0.66, cx + R * 0.66, cy + R * 0.66], outline=(*TEAL, 50), width=1)
    d.ellipse([cx - R * 0.33, cy - R * 0.33, cx + R * 0.33, cy + R * 0.33], outline=(*TEAL, 40), width=1)
    pts = []
    for i, (_, score, _) in enumerate(dims):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        rr = R * score
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        ax = cx + R * math.cos(ang)
        ay = cy + R * math.sin(ang)
        d.line([(cx, cy), (ax, ay)], fill=(*TEAL, 60), width=1)
        lx = cx + (R + 36) * math.cos(ang) - 40
        ly = cy + (R + 36) * math.sin(ang) - 12
        d.text((lx, ly), dims[i][0], font=font(18, True), fill=TEAL_LT)
    d.polygon(pts, fill=(*TEAL, 70), outline=TEAL_LT)
    for p in pts:
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=TEAL_LT)

    # bars
    for i, (name, score, note) in enumerate(dims):
        y = 280 + i * 120
        rounded_rect(d, [980, y, 1840, y + 100], 16, GLASS_DK, (*TEAL, 60), 2)
        d.text((1010, y + 18), name, font=font(24, True), fill=WHITE)
        d.text((1010, y + 56), note, font=font(18), fill=MUTED)
        # bar
        bw = int(700 * score)
        rounded_rect(d, [1280, y + 28, 1280 + 700, y + 52], 8, (30, 41, 59))
        rounded_rect(d, [1280, y + 28, 1280 + bw, y + 52], 8, TEAL)
        d.text((1760, y + 22), f"{int(score * 100)}", font=font(22, True), fill=TEAL_LT)
    return save(img.convert("RGB"), "09_five_dimensions.png")


def render_business() -> Path:
    img = mesh_bg(27, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "商业模式与社会价值", "惠民不是口号：让个体用得起、看得见交付", dark=False)
    left = [
        ("对谁", "OPC / 超级个体 / 小微 / 政企一线"),
        ("怎么赚", "席位 + Token + 行业战役模板包"),
        ("护城河", "模板库 · 人审工作流 · 息壤亲和"),
    ]
    right = [
        ("降低门槛", "请得起小队 → 调得起 AI 员工"),
        ("可验收", "周报 / 问数表 / 证据矩阵"),
        ("电信叙事", "息壤育智 · 能力交到个人手里"),
    ]
    rounded_rect(d, [72, 280, 920, 980], 24, WHITE, (*TEAL, 50), 2)
    d.rectangle([72, 280, 920, 360], fill=INK)
    d.text((110, 300), "商业模式", font=font(32, True), fill=WHITE)
    for i, (a, b) in enumerate(left):
        y = 420 + i * 160
        d.text((110, y), a, font=font(26, True), fill=TEAL)
        d.text((110, y + 50), b, font=font(24), fill=INK)

    rounded_rect(d, [1000, 280, 1848, 980], 24, WHITE, (*TEAL, 50), 2)
    d.rectangle([1000, 280, 1848, 360], fill=TEAL)
    d.text((1040, 300), "社会价值 · 惠民", font=font(32, True), fill=WHITE)
    for i, (a, b) in enumerate(right):
        y = 420 + i * 160
        d.text((1040, y), a, font=font(26, True), fill=TEAL_DK)
        d.text((1040, y + 50), b, font=font(24), fill=INK)
    return save(img.convert("RGB"), "10_business_value.png")


def render_demo_proof() -> Path:
    img = mesh_bg(29, dark=True).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "演示证明 · 提交对齐", "截止 2026-08-20 · 智云 Store 惠民赛道", dark=True)
    items = [
        ("演示视频", "≤60 秒 · 1080p · 硬烧字幕 · CTA→Word→问数"),
        ("答辩 PPT", "本文件 · 图文并茂 · 现代科技风"),
        ("代码仓库", "chengjuntai-opc-xirang（主仓唯一）"),
        ("评委账号", "只读 judge · 口令现场提供（勿公开）"),
        ("双轨 LLM", "息壤 primary 占位 · interim 真实 E2E"),
        ("公网 Demo", "天翼云 HTTPS · 审批推进中"),
    ]
    for i, (t, s) in enumerate(items):
        col = i % 2
        row = i // 2
        x0 = 80 + col * 920
        y0 = 280 + row * 220
        rounded_rect(d, [x0, y0, x0 + 860, y0 + 180], 18, GLASS_DK, (*TEAL, 70), 2)
        d.rectangle([x0, y0, x0 + 12, y0 + 180], fill=TEAL)
        d.text((x0 + 48, y0 + 40), t, font=font(28, True), fill=TEAL_LT)
        d.text((x0 + 48, y0 + 100), s, font=font(22), fill=MUTED)
    return save(img.convert("RGB"), "11_demo_proof.png")


def render_roadmap() -> Path:
    img = mesh_bg(31, dark=False).convert("RGBA")
    d = ImageDraw.Draw(img)
    brand_header(d, "下一步 · 复赛 / 决赛", "预赛打穿 60 秒与材料完整", dark=False)
    phases = [
        ("近", "竞赛 Token 主链路\n公网 HTTPS 加固\n标讯刷新常态化"),
        ("中", "战役模板库扩展\n证据矩阵深化\n成效回流闭环"),
        ("远", "行业方案包\n政企增值席位\n孵化与融资叙事"),
    ]
    for i, (tag, body) in enumerate(phases):
        x0 = 100 + i * 600
        rounded_rect(d, [x0, 300, x0 + 540, 880], 24, WHITE, (*TEAL, 60), 2)
        d.ellipse([x0 + 200, 360, x0 + 340, 500], fill=INK)
        d.text((x0 + 240, 400), tag, font=font(40, True), fill=TEAL_LT)
        d.text((x0 + 48, 560), body, font=font(26), fill=INK, spacing=14)
        if i < 2:
            d.polygon([(x0 + 555, 560), (x0 + 590, 580), (x0 + 555, 600)], fill=TEAL)
    return save(img.convert("RGB"), "12_roadmap.png")


def render_thanks() -> Path:
    img = mesh_bg(33, dark=True).convert("RGBA")
    d = ImageDraw.Draw(img)
    rounded_rect(d, [200, 260, 1720, 820], 32, GLASS_DK, (*TEAL, 90), 2)
    d.rectangle([200, 260, 220, 820], fill=TEAL)
    d.text((320, 360), "谢谢评委", font=font(72, True), fill=WHITE)
    d.text((320, 480), "息壤育智 · 一人成军", font=font(40, True), fill=TEAL_LT)
    d.text((320, 580), "成军台 · 欢迎现场体验「评委 60 秒」路径", font=font(26), fill=MUTED)
    d.text((320, 680), "仓库 · Demo URL · 评委账号当面提供", font=font(22), fill=SLATE)
    return save(img.convert("RGB"), "13_thanks.png")


def render_all() -> list[Path]:
    print(f"Rendering PPT assets → {OUT_DIR}")
    paths = [
        render_cover(),
        render_pain(),
        render_solution(),
        render_timeline(),
        render_agent_matrix(),
        render_architecture(),
        render_metrics(),
        render_evidence_matrix(),
        render_five_dim(),
        render_business(),
        render_demo_proof(),
        render_roadmap(),
        render_thanks(),
    ]
    return paths


if __name__ == "__main__":
    render_all()
    print("DONE")
