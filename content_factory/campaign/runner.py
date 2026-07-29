# -*- coding: utf-8 -*-
"""战役执行器：计划 → 人审 → 跑任务 → 周报"""
import os
from typing import Optional
import commander
import agents
import agents_research
import agents_ops
import agents_review
import agents_data
import llm_client
import op_logger
from . import store
from config_loader import ARTICLES_DIR, EXPORT_PDF_DIR, load_config


def start_campaign(goal: str, template: str = "lead_gen", created_by: str = "admin",
                   allow_mock: bool = False, auto_approve: bool = False) -> dict:
    camp = store.create_campaign(goal, template=template, created_by=created_by)
    try:
        plan = commander.plan_campaign(goal, template=template, allow_mock=allow_mock)
    except Exception as ex:
        store.update_campaign(camp["id"], status="failed", error=str(ex))
        raise

    tasks = []
    for t in plan.get("tasks", []):
        tasks.append({
            **t,
            "status": "pending",
            "result_artifact_id": None,
            "error": None,
        })

    status = llm_client.provider_status()
    active = status.get("active_name") or (status.get("providers") or [{}])[0].get("name")

    gate_needed = True
    new_status = "planned"
    camp = store.update_campaign(
        camp["id"],
        status=new_status,
        plan={
            "summary": plan.get("summary"),
            "hours_saved_est": plan.get("hours_saved_est", 4),
            "gate_message": plan.get("gate_message", ""),
            "fallback": bool(plan.get("_fallback")),
        },
        tasks=tasks,
        llm_provider=active,
        metrics={"hours_saved_est": plan.get("hours_saved_est", 4)},
        gate={"required": gate_needed, "approved": False, "note": plan.get("gate_message", "")},
    )

    if auto_approve:
        return approve_gate(camp["id"], note="auto_approve")
    return camp


def approve_gate(cid: str, note: str = "") -> dict:
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    if camp["status"] not in ("planned", "awaiting_review", "rejected"):
        # 允许 planned 放行执行；awaiting_review 放行完成
        pass

    if camp["status"] == "planned":
        store.update_campaign(
            cid,
            status="running",
            gate={"required": True, "approved": True, "note": note or camp.get("gate", {}).get("note", "")},
        )
        return run_pending_tasks(cid)

    if camp["status"] == "awaiting_review":
        store.update_campaign(
            cid,
            status="completed",
            gate={"required": True, "approved": True, "note": note},
        )
        store.bump_metric("campaigns_completed", 1)
        hrs = float((camp.get("metrics") or {}).get("hours_saved_est") or 0)
        store.bump_metric("est_hours_saved", hrs)
        return store.get_campaign(cid)

    # rejected → 重新跑
    if camp["status"] == "rejected":
        store.update_campaign(cid, status="running", gate={"required": True, "approved": True, "note": note})
        return run_pending_tasks(cid)

    return store.get_campaign(cid)


def reject_gate(cid: str, note: str = "") -> dict:
    return store.update_campaign(
        cid,
        status="rejected",
        gate={"required": True, "approved": False, "note": note or "已驳回"},
    )


def _deps_done(task: dict, tasks: list) -> bool:
    done_ids = {t["id"] for t in tasks if t.get("status") == "done"}
    for d in task.get("depends_on") or []:
        if d not in done_ids:
            return False
    return True


def _artifact_digest(cid: str) -> str:
    parts = []
    for a in store.list_artifacts(cid):
        body = store.read_artifact_content(cid, a["id"])
        parts.append(f"### {a['title']}（{a['role']}）\n{body[:1500]}")
    return "\n\n".join(parts)


def _read_factory_article(art: dict) -> str:
    raw = art.get("file") or ""
    candidates = []
    if raw:
        candidates.append(raw)
        candidates.append(os.path.join(ARTICLES_DIR, os.path.basename(raw)))
    if art.get("id"):
        try:
            for fn in os.listdir(ARTICLES_DIR):
                if fn.startswith(art["id"]) and fn.endswith(".md"):
                    candidates.append(os.path.join(ARTICLES_DIR, fn))
                    break
        except Exception:
            pass
    for fpath in candidates:
        if fpath and os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                return f.read()
    return f"# {art.get('title')}\n\n已生成文稿 ID: {art.get('id')}\n质检: {art.get('review_pass')}"


def _execute_task(camp: dict, task: dict):
    """返回 str 或 {content, meta}（内容角色附带工厂稿件 ID）"""
    goal = camp["goal"]
    brief = task.get("brief") or task.get("title")
    role = task.get("role")
    if role == "research":
        return agents_research.run_research(goal, brief)
    if role == "content":
        # 全链路：内容工厂 generate_article + quality_gate，产物 meta 挂 factory_article_id
        art = agents.generate_article(
            topic=task.get("title") or goal,
            summary=brief,
            tags=["成军台", camp.get("template", "")],
            campaign_id=camp.get("id"),
        )
        qa = {}
        try:
            import quality_gate
            qa = quality_gate.run_quality_check(article_id=art.get("id"))
        except Exception as ex:
            qa = {"error": str(ex), "pass": art.get("review_pass")}
            op_logger.log("campaign_runner", f"quality_gate 降级: {ex}", level="WARN")
        body = _read_factory_article(art)
        header = (
            f"> 内容工厂稿件：`{art.get('id')}` · 初审:{art.get('review_pass')} · "
            f"质检门控:{qa.get('pass') if isinstance(qa, dict) else '-'}\n\n"
        )
        if not body.lstrip().startswith(">"):
            body = header + body
        return {
            "content": body,
            "meta": {
                "factory_article_id": art.get("id"),
                "factory_title": art.get("title"),
                "factory_review_pass": art.get("review_pass"),
                "quality_gate": {k: qa.get(k) for k in ("pass", "word_count", "issues", "suggestion", "error") if isinstance(qa, dict) and k in qa},
            },
        }
    if role == "data":
        return agents_data.run_data(goal, brief)
    if role == "ops":
        return agents_ops.run_ops(goal, brief, context=_artifact_digest(camp["id"]))
    if role == "review":
        return agents_review.run_review(goal, brief, _artifact_digest(camp["id"]))
    raise ValueError(f"未知角色: {role}")


def run_pending_tasks(cid: str) -> dict:
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    store.update_campaign(cid, status="running", error=None)
    tasks = list(camp.get("tasks") or [])
    progress = True
    while progress:
        progress = False
        camp = store.get_campaign(cid)
        tasks = list(camp.get("tasks") or [])
        for i, task in enumerate(tasks):
            if task.get("status") != "pending":
                continue
            if not _deps_done(task, tasks):
                continue
            # 任务级人审卡点：先标记 awaiting，由 approve 继续——预赛简化为自动继续但记录
            tasks[i]["status"] = "running"
            store.update_campaign(cid, tasks=tasks)
            try:
                result = _execute_task(camp, task)
                extra = {}
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    extra = result.get("meta") or {}
                else:
                    content = result
                meta = store.save_artifact(
                    cid,
                    role=task.get("role", "unknown"),
                    title=task.get("title", task.get("id")),
                    content=content,
                    extra=extra or None,
                )
                tasks[i]["status"] = "done"
                tasks[i]["result_artifact_id"] = meta["id"]
                if extra.get("factory_article_id"):
                    tasks[i]["factory_article_id"] = extra["factory_article_id"]
                tasks[i]["error"] = None
                store.bump_metric("tasks_done", 1)
                store.update_campaign(cid, tasks=tasks)
                progress = True
                op_logger.log("campaign_runner", f"{cid} 完成 {task.get('id')} {task.get('role')}")
            except Exception as ex:
                tasks[i]["status"] = "failed"
                tasks[i]["error"] = str(ex)
                store.update_campaign(cid, tasks=tasks, status="failed", error=str(ex))
                op_logger.log("campaign_runner", f"{cid} 失败 {task.get('id')}: {ex}", level="ERROR")
                return store.get_campaign(cid)

    # 全部完成？
    camp = store.get_campaign(cid)
    tasks = camp.get("tasks") or []
    if tasks and all(t.get("status") == "done" for t in tasks):
        store.update_campaign(cid, status="awaiting_review")
        op_logger.log("campaign_runner", f"{cid} 全部任务完成，等待终审")
    return store.get_campaign(cid)


def export_weekly_report(cid: str) -> str:
    """汇总产物为成军周报 Markdown，并尝试导出 PDF"""
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    lines = [
        f"# 成军周报 · {camp['id']}",
        "",
        f"> 息壤育智 · 一人成军｜模板：{camp.get('template')}｜模型：{camp.get('llm_provider') or 'N/A'}",
        "",
        f"## 目标",
        camp["goal"],
        "",
        f"## 状态：{camp['status']}",
        f"- 创建时间：{camp.get('created_at')}",
        f"- 预估节省人时：{(camp.get('metrics') or {}).get('hours_saved_est', 0)} h",
        "",
        "## 任务看板",
    ]
    for t in camp.get("tasks") or []:
        lines.append(f"- [{t.get('status')}] {t.get('id')} · {t.get('role')} · {t.get('title')}")
        if t.get("error"):
            lines.append(f"  - 错误：{t['error']}")
    lines.append("")
    # 内容工厂关联稿件
    factory_arts = []
    try:
        factory_arts = agents.articles_for_campaign(cid)
    except Exception:
        factory_arts = []
    for a in camp.get("artifacts") or []:
        fid = a.get("factory_article_id")
        if fid and not any(x.get("id") == fid for x in factory_arts):
            factory_arts.append({"id": fid, "title": a.get("factory_title") or a.get("title")})
    if factory_arts:
        lines.append("## 内容工厂关联稿件")
        for fa in factory_arts:
            lines.append(f"- `{fa.get('id')}` · {fa.get('title') or ''}（质检:{fa.get('review_pass', '-')})")
        lines.append("")

    lines.append("## 产物")
    for a in camp.get("artifacts") or []:
        body = store.read_artifact_content(cid, a["id"])
        fid = a.get("factory_article_id")
        suffix = f" · 工厂稿 `{fid}`" if fid else ""
        lines.append(f"### {a['title']}（{a['role']}）{suffix}")
        lines.append("")
        lines.append(body)
        lines.append("")

    md = "\n".join(lines)
    meta = store.save_artifact(cid, role="report", title="成军周报", content=md)

    # PDF
    os.makedirs(EXPORT_PDF_DIR, exist_ok=True)
    pdf_path = os.path.join(EXPORT_PDF_DIR, f"{cid}_weekly_report.pdf")
    try:
        from pdf_exporter import _ensure_font, _md_to_flow, _FONT_NAME
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.units import mm

        _ensure_font()
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="H1", fontName=_FONT_NAME, fontSize=16, leading=22, spaceAfter=8))
        styles.add(ParagraphStyle(name="H2", fontName=_FONT_NAME, fontSize=13, leading=18, spaceAfter=6))
        styles.add(ParagraphStyle(name="H3", fontName=_FONT_NAME, fontSize=11, leading=16, spaceAfter=4))
        styles.add(ParagraphStyle(name="Body", fontName=_FONT_NAME, fontSize=10, leading=14, alignment=TA_LEFT))
        styles.add(ParagraphStyle(name="Bullet", fontName=_FONT_NAME, fontSize=10, leading=14, leftIndent=12))
        styles.add(ParagraphStyle(name="Quote", fontName=_FONT_NAME, fontSize=9, leading=13, textColor="#555555"))
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
        doc.build(_md_to_flow(md, styles))
        op_logger.log("campaign_runner", f"周报 PDF: {pdf_path}")
    except Exception as ex:
        op_logger.log("campaign_runner", f"PDF 导出降级为仅 Markdown: {ex}", level="WARN")
        pdf_path = ""

    # Word（演示主交付）
    docx_path = ""
    try:
        from docx_exporter import md_to_docx, EXPORT_DOCX_DIR
        docx_path = os.path.join(EXPORT_DOCX_DIR, f"{cid}_weekly_report.docx")
        md_to_docx(md, docx_path, title=f"成军周报 · {cid}")
        op_logger.log("campaign_runner", f"周报 Word: {docx_path}")
    except Exception as ex:
        op_logger.log("campaign_runner", f"Word 导出失败: {ex}", level="WARN")
        docx_path = ""

    store.update_campaign(
        cid,
        report={"artifact_id": meta["id"], "pdf": pdf_path, "docx": docx_path, "md": meta["path"]},
    )
    return docx_path or pdf_path or meta["path"]


def export_weekly_report_docx(cid: str) -> str:
    """仅导出 / 刷新成军周报 Word。若尚无周报 MD 则先汇总。"""
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    report = camp.get("report") or {}
    md_text = ""
    art_id = report.get("artifact_id")
    if art_id:
        md_text = store.read_artifact_content(cid, art_id)
    if not md_text:
        # 先走汇总（会写 MD/PDF/DOCX）
        export_weekly_report(cid)
        camp = store.get_campaign(cid)
        report = camp.get("report") or {}
        art_id = report.get("artifact_id")
        md_text = store.read_artifact_content(cid, art_id) if art_id else ""
        if report.get("docx") and os.path.exists(report["docx"]):
            return report["docx"]
    if not md_text:
        raise RuntimeError("无法生成周报内容")
    from docx_exporter import md_to_docx, EXPORT_DOCX_DIR
    docx_path = os.path.join(EXPORT_DOCX_DIR, f"{cid}_weekly_report.docx")
    md_to_docx(md_text, docx_path, title=f"成军周报 · {cid}")
    store.update_campaign(cid, report={**report, "docx": docx_path})
    return docx_path


def sync_campaign_to_factory(cid: str) -> dict:
    """将战役内容产物同步/登记到内容工厂（已有 factory_article_id 则只补关联）。"""
    import json
    import datetime as _dt
    import re
    from config_loader import DATA_DIR

    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    synced = []
    arts = list(camp.get("artifacts") or [])
    changed = False
    for i, a in enumerate(arts):
        if a.get("role") not in ("content", "report"):
            continue
        fid = a.get("factory_article_id")
        if fid:
            try:
                agents.link_article_campaign(fid, cid)
                synced.append({"artifact_id": a["id"], "factory_article_id": fid, "action": "linked"})
            except Exception as ex:
                synced.append({"artifact_id": a["id"], "factory_article_id": fid, "action": "link_failed", "error": str(ex)})
            continue
        body = store.read_artifact_content(cid, a["id"])
        if not body or len(body.strip()) < 40:
            continue
        art_id = f"ART{_dt.datetime.now().strftime('%Y%m%d%H%M%S')}S{i}"
        title = a.get("title") or f"战役产物 {a['id']}"
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:40]
        fname = f"{art_id}_{safe_title}.md"
        fpath = os.path.join(ARTICLES_DIR, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(
                f"---\nid: {art_id}\ntitle: {title}\ncampaign_id: {cid}\n"
                f"created_at: {_dt.datetime.now().isoformat()}\n---\n\n{body}"
            )
        try:
            import vector_store
            vector_store.index_document(art_id, title, body, ["成军台", "sync"], source="campaign_sync")
        except Exception:
            pass
        meta_path = os.path.join(DATA_DIR, "articles_meta.json")
        meta_list = []
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_list = json.load(f)
            except Exception:
                meta_list = []
        meta_list.append({
            "id": art_id,
            "title": title,
            "file": fname,
            "tags": ["成军台", "campaign_sync", camp.get("template") or ""],
            "summary": (body[:120] + "…") if len(body) > 120 else body,
            "review_pass": True,
            "review": {"pass": True, "issues": [], "suggestions": "战役同步入库"},
            "created_at": _dt.datetime.now().isoformat(),
            "campaign_id": cid,
            "synced_from_artifact": a["id"],
        })
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_list, f, ensure_ascii=False, indent=2)
        arts[i] = {**a, "factory_article_id": art_id, "factory_title": title}
        changed = True
        synced.append({"artifact_id": a["id"], "factory_article_id": art_id, "action": "created"})
    if changed:
        store.update_campaign(cid, artifacts=arts)
    op_logger.log("campaign_runner", f"{cid} 同步到内容工厂 {len(synced)} 件")
    return {"ok": True, "campaign_id": cid, "synced": synced, "count": len(synced)}
