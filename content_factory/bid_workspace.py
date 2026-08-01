# -*- coding: utf-8 -*-
"""
标书材料工作台（轻量）
- 粘贴招标文件文本 → 要求清单（LLM 或规则）
- 对照知识库 → 证据/缺口矩阵
- 导出 Word
"""
from __future__ import annotations

import os
import re
import json
import datetime
from typing import List, Optional

from config_loader import DATA_DIR, ROOT
import op_logger
import llm_client
import bid_pipeline_link
import docx_exporter

WORKSPACE_DIR = os.path.join(DATA_DIR, "bid_workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

# 通用投标包章节大纲（可复用模板；无客户密钥）
BID_PACKAGE_OUTLINE_PATH = os.path.join(DATA_DIR, "bid_package_outline.md")


def load_bid_package_outline() -> str:
    """读取投标包章节大纲模板；缺失时返回内置短大纲。"""
    try:
        if os.path.isfile(BID_PACKAGE_OUTLINE_PATH):
            with open(BID_PACKAGE_OUTLINE_PATH, "r", encoding="utf-8") as f:
                text = (f.read() or "").strip()
            if text:
                return text
    except OSError as ex:
        op_logger.log("bid_workspace", f"读取投标包大纲失败: {ex}", level="WARN")
    return (
        "# 投标文件章节大纲（内置短版）\n\n"
        "## 第一册 商务\n投标函 / 授权 / 商务响应 / 报价\n\n"
        "## 第二册 技术\n项目理解 / 架构 / 实施方案 / 安全 / 售后\n\n"
        "## 第三册 资质与业绩\n资质清单 / 同类业绩\n\n"
        "## 第四册 合规自检\n参数响应表 / 废标风险 / 提交前清单\n"
    )

# 招标文本常见条款关键词 → 默认要求项
_RULE_PATTERNS = [
    (r"等保|等级保护|安全测评", "信息安全等保合规证明与测评报告"),
    (r"资质|证书|ISO|CMMI", "企业资质与体系认证复印件"),
    (r"业绩|同类项目|案例", "近三年同类项目业绩证明"),
    (r"技术方案|实施方案", "总体技术方案与实施计划"),
    (r"人员|项目经理|团队", "项目团队组织与关键人员简历"),
    (r"售后|运维|响应时间", "售后服务与运维响应承诺"),
    (r"培训|移交", "培训与知识移交方案"),
    (r"进度|工期|里程碑", "项目进度计划与里程碑"),
    (r"报价|商务|价格", "商务报价与分项明细"),
    (r"云|算力|IDC|息壤", "云网/算力能力与资源证明"),
    (r"5G|专网|切片", "5G 专网/切片能力说明"),
    (r"物联网|感知|边缘", "物联网感知与边缘计算方案"),
]


def _rule_extract(text: str) -> List[dict]:
    items = []
    seen = set()
    for pat, title in _RULE_PATTERNS:
        if re.search(pat, text or "", re.I):
            if title not in seen:
                seen.add(title)
                items.append({
                    "id": f"REQ_{len(items)+1:02d}",
                    "title": title,
                    "priority": "高" if any(k in title for k in ("资质", "业绩", "安全", "技术方案")) else "中",
                    "source": "rule",
                    "hint": f"匹配关键词: {pat}",
                })
    # 按行抽取「必须/应当/需提供」句
    for line in (text or "").splitlines():
        line = line.strip()
        if len(line) < 8 or len(line) > 120:
            continue
        if re.search(r"(必须|应当|需提供|投标人应|须具备)", line):
            title = re.sub(r"^[\d\.、\-\*\s]+", "", line)[:80]
            if title and title not in seen:
                seen.add(title)
                items.append({
                    "id": f"REQ_{len(items)+1:02d}",
                    "title": title,
                    "priority": "高",
                    "source": "rule_line",
                    "hint": "从招标文本强制条款抽取",
                })
    if not items:
        items = [
            {"id": "REQ_01", "title": "总体技术方案", "priority": "高", "source": "default", "hint": "文本未命中关键词，给默认清单"},
            {"id": "REQ_02", "title": "同类项目业绩证明", "priority": "高", "source": "default", "hint": ""},
            {"id": "REQ_03", "title": "项目团队与资质证明", "priority": "中", "source": "default", "hint": ""},
            {"id": "REQ_04", "title": "售后服务承诺", "priority": "中", "source": "default", "hint": ""},
            {"id": "REQ_05", "title": "商务报价明细", "priority": "中", "source": "default", "hint": ""},
        ]
    return items


def _llm_extract(text: str) -> Optional[List[dict]]:
    if not llm_client.is_llm_enabled():
        return None
    prompt = (
        "你是电信政企标书助手。从下列招标文本中提取「投标响应要求清单」。\n"
        "只输出 JSON 数组，每项含 title, priority(高/中/低), hint。最多 12 条。不要 markdown。\n"
        f"文本:\n{(text or '')[:3500]}"
    )
    try:
        raw = llm_client.call_llm(prompt, fallback="", max_tokens=1200, temperature=0.2, timeout=60)
        raw = (raw or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if not isinstance(data, list):
            return None
        out = []
        for i, it in enumerate(data[:12]):
            if isinstance(it, str):
                out.append({"id": f"REQ_{i+1:02d}", "title": it, "priority": "中", "source": "llm", "hint": ""})
            elif isinstance(it, dict) and it.get("title"):
                out.append({
                    "id": f"REQ_{i+1:02d}",
                    "title": it["title"],
                    "priority": it.get("priority") or "中",
                    "source": "llm",
                    "hint": it.get("hint") or "",
                })
        return out or None
    except Exception as ex:
        op_logger.log("bid_workspace", f"LLM 拆解失败，降级规则: {ex}", level="WARN")
        return None


def parse_tender_requirements(text: str, project_id: str = "", use_llm: bool = True) -> dict:
    """粘贴招标文本 → 要求清单。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("请粘贴招标文件或需求文本")
    mode = "rule"
    items = None
    if use_llm:
        items = _llm_extract(text)
        if items:
            mode = "llm"
    if not items:
        items = _rule_extract(text)
        mode = "rule" if mode != "llm" else "rule_fallback"
    session = {
        "id": f"WS_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "project_id": project_id or "",
        "created_at": datetime.datetime.now().isoformat(),
        "mode": mode,
        "text_preview": text[:200],
        "requirements": items,
    }
    path = os.path.join(WORKSPACE_DIR, f"{session['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    op_logger.log("bid_workspace", f"要求拆解 {len(items)} 项 mode={mode} → {session['id']}")
    return session


def build_evidence_gap_matrix(
    requirements: List[dict],
    knowledge_items: Optional[List[dict]] = None,
) -> dict:
    """要求清单 × 知识库 → 证据/缺口矩阵。"""
    if knowledge_items is None:
        knowledge_items = bid_pipeline_link.list_knowledge_index(80).get("items") or []
    rows = []
    covered = 0
    for req in requirements or []:
        title = req.get("title") or ""
        tokens = [t for t in re.split(r"[\s/、，,]+", title) if len(t) >= 2][:6]
        hits = []
        for k in knowledge_items:
            blob = " ".join([
                str(k.get("title") or ""),
                str(k.get("summary") or ""),
                str(k.get("category") or ""),
                " ".join(k.get("tags") or []),
            ])
            score = sum(1 for t in tokens if t in blob)
            if score > 0 or (title[:6] and title[:6] in blob):
                hits.append({
                    "id": k.get("id"),
                    "title": k.get("title"),
                    "category": k.get("category"),
                    "score": score,
                })
        hits.sort(key=lambda x: x.get("score", 0), reverse=True)
        status = "有证据" if hits else "缺口"
        if hits:
            covered += 1
        rows.append({
            "req_id": req.get("id"),
            "requirement": title,
            "priority": req.get("priority", "中"),
            "status": status,
            "evidence": hits[:3],
            "gap_action": "" if hits else "需补材料或从内容工厂/战役生成对应证明稿",
        })
    total = len(rows) or 1
    return {
        "total": len(rows),
        "covered": covered,
        "gap": len(rows) - covered,
        "coverage_pct": round(100.0 * covered / total, 1),
        "rows": rows,
        "knowledge_scanned": len(knowledge_items),
    }


def export_matrix_docx(
    requirements: List[dict],
    matrix: dict,
    title: str = "标书材料包",
    project_name: str = "",
) -> dict:
    """导出标书材料包 Word：封面 + 响应检查清单 + 证据/缺口矩阵（非法律排版）。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    proj = project_name or "（未指定项目）"
    cov = matrix.get("coverage_pct", 0)
    covered = matrix.get("covered", 0)
    total = matrix.get("total", 0) or len(requirements or [])
    gap_n = int(matrix.get("gap") or max(0, (total or 0) - (covered or 0)))

    lines = [
        f"# {title}",
        "",
        "## 封面",
        "",
        f"- **材料名称**：成军台 · 标书响应材料包",
        f"- **关联项目**：{proj}",
        f"- **生成时间**：{now}",
        f"- **证据覆盖率**：{cov}%（有证据 {covered} / 要求 {total} · 缺口 {gap_n}）",
        f"- **说明**：本包由招标文本拆解 + 知识库对照生成，供内部编制参考，不构成正式法律文本。",
        "",
        "---",
        "",
        "## 一、响应检查清单（Checklist）",
        "",
        "编制前请逐项勾选：",
        "",
        "- [ ] 封面信息与项目名称已核对",
        "- [ ] 高优先级要求均已有证据或明确缺口动作",
        "- [ ] 缺口项已指派内容工厂/战役产物补齐",
        "- [ ] 「有证据」项已打开原文核对评分点",
        "- [ ] 商务报价与技术方案分册交叉引用已标注",
        "- [ ] 导出 Word 已归档至投标工作目录",
        "",
        "### 要求清单（按优先级）",
        "",
    ]
    # 高优在前
    sorted_reqs = sorted(
        requirements or [],
        key=lambda r: {"高": 0, "中": 1, "低": 2}.get(r.get("priority") or "中", 1),
    )
    for r in sorted_reqs:
        pri = r.get("priority") or "中"
        lines.append(
            f"- [ ] **[{pri}]** `{r.get('id', '')}` {r.get('title', '')}"
            + (f" — _{r.get('hint')}_" if r.get("hint") else "")
        )

    lines += [
        "",
        "---",
        "",
        "## 二、证据 / 缺口矩阵",
        "",
        f"> 扫描知识条目：{matrix.get('knowledge_scanned', 0)} · 覆盖率 **{cov}%**",
        "",
        "| 要求 | 优先级 | 状态 | 证据摘要 | 缺口动作 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in matrix.get("rows") or []:
        ev = "；".join(
            (e.get("title") or e.get("id") or "") for e in (row.get("evidence") or [])
        ) or "-"
        # 表格单元格避免破坏 markdown
        req_t = str(row.get("requirement", "")).replace("|", "/")
        ev = str(ev).replace("|", "/")
        gap = str(row.get("gap_action") or "-").replace("|", "/")
        lines.append(
            f"| {req_t} | {row.get('priority', '')} | "
            f"{row.get('status', '')} | {ev} | {gap} |"
        )

    # 缺口专章
    gap_rows = [r for r in (matrix.get("rows") or []) if r.get("status") != "有证据"]
    lines += ["", "## 三、缺口补齐建议", ""]
    if gap_rows:
        for i, row in enumerate(gap_rows, 1):
            lines.append(
                f"{i}. **{row.get('requirement', '')}**（{row.get('priority', '中')}）→ "
                f"{row.get('gap_action') or '在内容工厂生成证明类文稿，或从战役产物推入知识库后重跑矩阵'}"
            )
    else:
        lines.append("当前无缺口项。请仍核对证据原文是否满足评分细则。")

    lines += [
        "",
        "## 四、下一步（成军台闭环）",
        "",
        "1. 缺口项：内容工厂生成 / 标讯一键获客·综述战役 →「推入标书知识库」→ 重跑矩阵。",
        "2. 有证据项：导出本 Word 附卷，并在智能问数侧用赛道问题补充市场佐证（bid_telecom.db）。",
        "3. 正式投标文本请依法务与商务终审；本包仅作材料编排辅助。",
        "",
        "---",
        "",
        "## 五、投标包章节大纲（模板）",
        "",
        "以下为通用分册结构，编制时按招标范围裁剪；与上方清单/矩阵对照勾选。",
        "",
    ]
    outline = load_bid_package_outline()
    # 大纲文件自带一级标题时降为正文，避免与导出标题重复抢层级
    outline_body = outline
    if outline_body.lstrip().startswith("# "):
        outline_body = "\n".join(outline_body.splitlines()[1:]).lstrip()
    lines.append(outline_body)
    lines.append("")
    md = "\n".join(lines)
    safe = re.sub(r'[\\/:*?"<>|]', "_", (project_name or title))[:40]
    out_name = f"bid_pack_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe}.docx"
    out_path = os.path.join(docx_exporter.EXPORT_DOCX_DIR, out_name)
    path = docx_exporter.md_to_docx(md, out_path, title=title)
    op_logger.log("bid_workspace", f"导出标书材料包 Word: {path}")
    return {
        "ok": True,
        "docx": path,
        "download": f"/api/download_docx?path={os.path.basename(path)}",
        "filename": os.path.basename(path),
        "pack": "cover+checklist+matrix+outline",
        "outline": os.path.basename(BID_PACKAGE_OUTLINE_PATH),
    }
