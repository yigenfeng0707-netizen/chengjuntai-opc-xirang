# -*- coding: utf-8 -*-
"""战役执行器：计划 → 人审 → 跑任务 → 周报"""
import os
import sys
import queue
import threading
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


_TASK_MAX_RETRIES = 1  # 单任务内部失败自动重试 1 次（不改变状态机，仅 Agent 调用重试）
_TASK_HARD_TIMEOUT_SEC = 600  # 单任务硬性上限 10 分钟（防御永久挂死：TCP死连接/LLM不返回等）
_BG_RUNNERS_LOCK = threading.Lock()
_BG_RUNNERS = {}  # cid -> thread 句柄，避免重复启动


def _fallback_plan(goal: str, template: str) -> dict:
    """commander.plan_campaign 失败时的降级计划：保证能生成一条调研+一条内容+一条复盘。"""
    return {
        "summary": f"（降级计划）目标：{goal}",
        "hours_saved_est": 2,
        "gate_message": "计划生成失败，已启用 3 任务最小骨架",
        "_fallback": True,
        "tasks": [
            {"id": "t_research", "title": f"调研：{goal[:30]}", "role": "research",
             "brief": f"围绕目标「{goal}」输出调研骨架", "depends_on": []},
            {"id": "t_content", "title": f"种草：{goal[:30]}", "role": "content",
             "brief": f"基于调研撰写一篇种草骨架稿", "depends_on": ["t_research"]},
            {"id": "t_review", "title": f"复盘：{goal[:30]}", "role": "review",
             "brief": f"基于调研+种草输出成军周报复盘", "depends_on": ["t_research", "t_content"]},
        ],
    }


def start_campaign_async(goal: str, template: str = "lead_gen", created_by: str = "admin",
                         allow_mock: bool = False, auto_approve: bool = False) -> dict:
    """异步版 start_campaign：先创建 campaign（status=planning），后台线程生成计划。
    HTTP 立即返回 campaign 快照，前端轮询 /api/campaign/{cid} 等待 status 变为 planned。
    """
    g = (goal or "").strip()
    if not g:
        raise ValueError("战役目标不能为空")
    tpl = (template or "lead_gen").strip() or "lead_gen"
    # 先创建 campaign，status=planning
    camp = store.create_campaign(g, template=tpl, created_by=(created_by or "admin"))
    store.update_campaign(camp["id"], status="planning")

    def _bg():
        import time as _time
        _start = _time.time()
        try:
            plan = commander.plan_campaign(g, template=tpl, allow_mock=allow_mock)
        except Exception as ex:
            op_logger.log("campaign_runner", f"计划生成异常[{camp['id']}]: {type(ex).__name__}: {ex}，启用降级计划", level="WARN")
            plan = _fallback_plan(g, tpl)

        if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list) or not plan["tasks"]:
            plan = _fallback_plan(g, tpl)

        tasks = []
        for t in plan.get("tasks", []):
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id") or "").strip()
            if not tid:
                continue
            deps_raw = t.get("depends_on") or []
            deps = [str(d).strip() for d in deps_raw if isinstance(d, str) or isinstance(d, int)]
            tasks.append({
                "id": tid,
                "title": str(t.get("title") or tid)[:120],
                "role": str(t.get("role") or "ops")[:32],
                "brief": str(t.get("brief") or "")[:2000],
                "depends_on": deps,
                "status": "pending",
                "result_artifact_id": None,
                "error": None,
                "retry_count": 0,
            })

        try:
            st = llm_client.provider_status()
            active = st.get("active_name") or (st.get("providers") or [{}])[0].get("name")
        except Exception:
            active = None

        elapsed = _time.time() - _start
        store.update_campaign(
            camp["id"],
            status="planned",
            plan={
                "summary": plan.get("summary") or "",
                "hours_saved_est": int(plan.get("hours_saved_est") or 4),
                "gate_message": plan.get("gate_message") or "",
                "fallback": bool(plan.get("_fallback")),
            },
            tasks=tasks,
            llm_provider=active,
            metrics={"hours_saved_est": int(plan.get("hours_saved_est") or 4)},
            gate={"required": True, "approved": False, "note": plan.get("gate_message") or ""},
        )
        op_logger.log("campaign_runner", f"{camp['id']} 计划生成完成 tasks={len(tasks)} 耗时 {elapsed:.1f}s")

        if auto_approve:
            try:
                approve_gate(camp["id"], note="auto_approve")
            except Exception as ex:
                op_logger.log("campaign_runner", f"自动审批失败: {ex}", level="WARN")

    th = threading.Thread(target=_bg, name=f"camp_plan_{camp['id']}", daemon=True)
    th.start()
    op_logger.log("campaign_runner", f"{camp['id']} 已启动异步计划生成线程")
    # Watchdog：90 秒后检查战役是否还在 planning，若是则强制写入降级计划
    _start_watchdog(camp["id"], 90)
    return camp


_PLAN_WATCHDOG_TIMEOUT = 90  # 计划生成最长 90 秒，超过则降级


def _start_watchdog(cid: str, timeout_sec: int):
    """监控计划生成后台线程；超时则强制写入降级计划，避免战役永远 planning。"""
    def _wd():
        import time as _time
        _time.sleep(int(timeout_sec or _PLAN_WATCHDOG_TIMEOUT) + 1)
        try:
            camp = store.get_campaign(cid)
            if not camp:
                return
            if camp.get("status") != "planning":
                return  # 已正常推进
            # 还在 planning：写降级计划
            g = camp.get("goal") or ""
            tpl = camp.get("template") or "lead_gen"
            plan = _fallback_plan(g, tpl)
            tasks = []
            for t in plan.get("tasks", []):
                if not isinstance(t, dict):
                    continue
                tid = str(t.get("id") or "").strip()
                if not tid:
                    continue
                tasks.append({
                    "id": tid, "title": str(t.get("title") or tid)[:120],
                    "role": str(t.get("role") or "ops")[:32],
                    "brief": str(t.get("brief") or "")[:2000],
                    "depends_on": [str(d) for d in (t.get("depends_on") or [])],
                    "status": "pending", "result_artifact_id": None, "error": None, "retry_count": 0,
                })
            store.update_campaign(
                cid, status="planned",
                plan={"summary": plan.get("summary", ""), "hours_saved_est": 2,
                      "gate_message": "⚠️ 计划生成超时，已启用降级计划骨架", "fallback": True},
                tasks=tasks,
                gate={"required": True, "approved": False, "note": "watchdog 降级"},
            )
            op_logger.log("campaign_runner", f"{cid} watchdog 触发：超过 {timeout_sec}s 仍 planning，已写入降级计划", level="WARN")
        except Exception as ex:
            op_logger.log("campaign_runner", f"{cid} watchdog 异常: {type(ex).__name__}: {ex}", level="ERROR")

    w = threading.Thread(target=_wd, name=f"camp_wd_{cid}", daemon=True)
    w.start()


def reset_stuck_planning(cid: str = None, max_age_sec: int = 120) -> dict:
    """修复卡在 planning 状态的战役：直接写入降级计划。
    - cid 为空时，扫描所有 planning 战役并修复超过 max_age_sec 的。
    - 返回 {fixed: [cid...], skipped: [cid...]}。
    """
    import time as _time
    import datetime as _dt
    fixed, skipped = [], []
    targets = []
    if cid:
        targets = [cid]
    else:
        for csum in store.list_campaigns(limit=200):
            if (csum.get("status") or "") == "planning":
                targets.append(csum["id"])
    for tid in targets:
        try:
            camp = store.get_campaign(tid)
            if not camp or camp.get("status") != "planning":
                skipped.append(tid)
                continue
            # 计算年龄
            try:
                created = _dt.datetime.fromisoformat(camp.get("created_at") or "")
                age = _time.time() - created.timestamp()
            except Exception:
                age = 1e9  # 解析失败 → 视为很老
            if cid is None and age < max_age_sec:
                # 批量扫描时跳过年轻战役
                skipped.append(tid)
                continue
            # 写降级计划
            g = camp.get("goal") or ""
            tpl = camp.get("template") or "lead_gen"
            plan = _fallback_plan(g, tpl)
            tasks = []
            for t in plan.get("tasks", []):
                if not isinstance(t, dict):
                    continue
                t_id = str(t.get("id") or "").strip()
                if not t_id:
                    continue
                tasks.append({
                    "id": t_id, "title": str(t.get("title") or t_id)[:120],
                    "role": str(t.get("role") or "ops")[:32],
                    "brief": str(t.get("brief") or "")[:2000],
                    "depends_on": [str(d) for d in (t.get("depends_on") or [])],
                    "status": "pending", "result_artifact_id": None, "error": None, "retry_count": 0,
                })
            store.update_campaign(
                tid, status="planned",
                plan={"summary": plan.get("summary", ""), "hours_saved_est": 2,
                      "gate_message": "⚠️ 计划生成超时，已启用降级计划骨架", "fallback": True},
                tasks=tasks,
                gate={"required": True, "approved": False, "note": "reset_stuck_planning 降级"},
            )
            fixed.append(tid)
            op_logger.log("campaign_runner", f"{tid} reset_stuck_planning 已修复为 planned（降级计划）")
        except Exception as ex:
            op_logger.log("campaign_runner", f"reset_stuck_planning 异常 {tid}: {type(ex).__name__}: {ex}", level="ERROR")
            skipped.append(tid)
    return {"fixed": fixed, "skipped": skipped}


def start_campaign(goal: str, template: str = "lead_gen", created_by: str = "admin",
                   allow_mock: bool = False, auto_approve: bool = False) -> dict:
    g = (goal or "").strip()
    if not g:
        raise ValueError("战役目标不能为空")
    tpl = (template or "lead_gen").strip() or "lead_gen"
    camp = store.create_campaign(g, template=tpl, created_by=(created_by or "admin"))
    try:
        plan = commander.plan_campaign(g, template=tpl, allow_mock=allow_mock)
    except Exception as ex:
        op_logger.log(
            "campaign_runner",
            f"计划生成异常[{camp['id']}]: {type(ex).__name__}: {ex}，启用降级计划",
            level="WARN",
        )
        plan = _fallback_plan(g, tpl)

    if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list) or not plan["tasks"]:
        op_logger.log(
            "campaign_runner",
            f"计划任务为空[{camp['id']}]，启用降级计划",
            level="WARN",
        )
        plan = _fallback_plan(g, tpl)

    tasks = []
    for t in plan.get("tasks", []):
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "").strip()
        if not tid:
            continue
        deps_raw = t.get("depends_on") or []
        deps = [str(d).strip() for d in deps_raw if isinstance(d, str) or isinstance(d, int)]
        tasks.append({
            "id": tid,
            "title": str(t.get("title") or tid)[:120],
            "role": str(t.get("role") or "ops")[:32],
            "brief": str(t.get("brief") or "")[:2000],
            "depends_on": deps,
            "status": "pending",
            "result_artifact_id": None,
            "error": None,
            "retry_count": 0,
        })

    try:
        st = llm_client.provider_status()
        active = st.get("active_name") or (st.get("providers") or [{}])[0].get("name")
    except Exception:
        active = None

    cid = camp["id"]
    camp = store.update_campaign(
        cid,
        status="planned",
        plan={
            "summary": plan.get("summary") or "",
            "hours_saved_est": int(plan.get("hours_saved_est") or 4),
            "gate_message": plan.get("gate_message") or "",
            "fallback": bool(plan.get("_fallback")),
        },
        tasks=tasks,
        llm_provider=active,
        metrics={"hours_saved_est": int(plan.get("hours_saved_est") or 4)},
        gate={"required": True, "approved": False, "note": plan.get("gate_message") or ""},
    )

    if camp is None:
        raise RuntimeError(f"战役计划未能落盘：{cid}")

    if auto_approve:
        try:
            return approve_gate(cid, note="auto_approve")
        except Exception as ex:
            op_logger.log("campaign_runner", f"自动审批失败: {ex}", level="WARN")
            return camp
    return camp


def approve_gate(cid: str, note: str = "") -> dict:
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    if camp["status"] not in ("planned", "awaiting_review", "rejected"):
        # 允许 planned 放行执行；awaiting_review 放行完成；rejected 重跑
        # planning/draft/running/completed/failed/partial_success 不应直接放行
        if camp["status"] == "planning":
            raise ValueError("计划还在生成中，请稍候刷新页面（后台约 30–60 秒完成）")
        if camp["status"] == "running":
            raise ValueError("任务正在执行中，请稍候刷新页面")
        if camp["status"] in ("completed", "partial_success"):
            raise ValueError(f"战役已是终态：{camp['status']}，无需审批")
        if camp["status"] == "failed":
            raise ValueError("战役已失败，请重新发起")
        # draft 等其他状态：不允许直接放行
        raise ValueError(f"当前状态 {camp['status']} 不可审批放行")

    if camp["status"] == "planned":
        store.update_campaign(
            cid,
            status="running",
            gate={"required": True, "approved": True, "note": note or camp.get("gate", {}).get("note", "")},
        )
        # 异步启动任务执行，避免 HTTP 阻塞导致 504
        return run_pending_tasks_async(cid)

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
        return run_pending_tasks_async(cid)

    return store.get_campaign(cid)


def reject_gate(cid: str, note: str = "") -> dict:
    camp = store.update_campaign(
        cid,
        status="rejected",
        gate={"required": True, "approved": False, "note": note or "已驳回"},
    )
    if camp is None:
        raise RuntimeError(f"驳回结果未能落盘：{cid}")
    return camp


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


def _execute_task(camp: dict, task: dict, timeout_sec: int = None):
    """`_execute_task_raw` 的硬超时包装：超时 >10 分钟（默认）时返回降级骨架，**永不挂死**。
    使用子线程执行 + 队列接收结果；超时后任务线程仍在跑，但主流程已推进，避免战役永远 running。
    """
    tlimit = int(timeout_sec or _TASK_HARD_TIMEOUT_SEC)
    if tlimit <= 0:
        tlimit = _TASK_HARD_TIMEOUT_SEC
    q: "queue.Queue" = queue.Queue(maxsize=1)

    def _worker():
        try:
            q.put(("ok", _execute_task_raw(camp, task)))
        except BaseException as ex:  # noqa: BLE001 — worker 里全部兜底
            try:
                q.put(("err", ex))
            except Exception:
                pass

    th = threading.Thread(target=_worker, name=f"camp_task_{camp.get('id')}_{task.get('id')}", daemon=True)
    th.start()
    try:
        kind, payload = q.get(timeout=tlimit)
    except queue.Empty:
        tid = task.get("id")
        role = task.get("role")
        title = task.get("title") or tid
        op_logger.log(
            "campaign_runner",
            f"任务硬超时 {camp.get('id')}/{tid}({role}) 超过{tlimit}s，返回降级骨架（后台仍可能在跑）",
            level="ERROR",
        )
        return (
            f"# {title}\n\n"
            f"> ⚠️ 任务执行超过 {tlimit} 秒，被强制降级。\n"
            f"> 建议：重新发起战役（该任务后台线程可能仍在执行，请稍后查产物）。\n\n"
            f"## 降级要点\n- 角色：{role}\n- 原始目标：{str(camp.get('goal',''))[:200]}\n"
        )
    if kind == "ok":
        return payload
    # kind == "err"：把子线程抛出的异常原样 raise，交给外层重试/失败逻辑
    raise payload


def run_pending_tasks_async(cid: str) -> dict:
    """异步启动 `run_pending_tasks`，立即返回当前战役快照，避免 HTTP 请求卡同步 LLM。
    同 cid 并发幂等：若已有同 cid 线程在跑则直接返回快照不重复启动。
    """
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    with _BG_RUNNERS_LOCK:
        th = _BG_RUNNERS.get(cid)
        if th is None or not th.is_alive():
            def _runner():
                try:
                    run_pending_tasks(cid)
                finally:
                    with _BG_RUNNERS_LOCK:
                        _BG_RUNNERS.pop(cid, None)
            th = threading.Thread(target=_runner, name=f"camp_async_{cid}", daemon=True)
            _BG_RUNNERS[cid] = th
            th.start()
            op_logger.log("campaign_runner", f"{cid} 已启动异步执行线程")
        else:
            op_logger.log("campaign_runner", f"{cid} 执行线程已存在，跳过重复启动")
    # 立即返回当前快照
    return store.get_campaign(cid) or camp


def _execute_task_raw(camp: dict, task: dict):
    """返回 str 或 {content, meta}（内容角色附带工厂稿件 ID）。
    全链路异常只在此处包装；不返回 None，至少返回一段错误说明文本。
    注意：此函数本身 **不** 做硬超时，由外层 _execute_task 包线程超时保护。
    """
    goal = str(camp.get("goal") or "").strip()
    brief = str(task.get("brief") or task.get("title") or goal).strip()
    role = str(task.get("role") or "ops").strip().lower()
    camp_id = str(camp.get("id") or "")

    def _safe_text(x) -> str:
        if x is None:
            return ""
        if isinstance(x, dict) and "content" in x and isinstance(x["content"], str):
            return x["content"]
        if isinstance(x, str):
            return x
        try:
            return str(x)
        except Exception:
            return ""

    try:
        if role == "research":
            return _safe_text(agents_research.run_research(goal, brief)) or "# 调研报告\n\n（空返回，降级骨架）"
        if role == "content":
            try:
                art = agents.generate_article(
                    topic=str(task.get("title") or goal)[:120],
                    summary=brief,
                    tags=["成军台", camp.get("template") or ""],
                    campaign_id=camp_id,
                )
            except Exception as ex:
                op_logger.log("campaign_runner", f"内容工厂失败，降级骨架稿: {type(ex).__name__}: {ex}", level="WARN")
                return (
                    f"# {task.get('title') or '种草内容'}\n\n"
                    f"> 内容工厂异常：{type(ex).__name__}。以下为骨架稿，建议人工补全。\n\n"
                    f"## 背景\n{goal}\n\n## 产品亮点\n1. 多智能体协同  2. 可验收周报  3. 息壤原生部署\n\n"
                    f"## 转化话术\n欢迎试用成军台，零门槛拉起 AI 员工矩阵。\n"
                )
            qa = {"pass": None}
            try:
                import quality_gate
                qa = quality_gate.run_quality_check(article_id=art.get("id")) or {}
            except Exception as ex:
                qa = {"error": str(ex), "pass": art.get("review_pass") if isinstance(art, dict) else None}
                op_logger.log("campaign_runner", f"quality_gate 降级: {ex}", level="WARN")
            body = _read_factory_article(art if isinstance(art, dict) else {})
            art_title = art.get("title") if isinstance(art, dict) else ""
            art_id = art.get("id") if isinstance(art, dict) else ""
            art_review = art.get("review_pass") if isinstance(art, dict) else None
            art_real = art.get("real_data_used") if isinstance(art, dict) else False
            art_tokens = art.get("tokens_used") if isinstance(art, dict) else 0
            qa_pass = qa.get("pass") if isinstance(qa, dict) else "-"
            header = (
                f"> 内容工厂稿件：`{art_id}` · 初审:{art_review} · "
                f"质检门控:{qa_pass} · 真实数据:{'是' if art_real else '否'} · "
                f"tokens≈{art_tokens or 0}\n\n"
            )
            if isinstance(body, str) and body and not body.lstrip().startswith(">"):
                body = header + body
            qg_out = {}
            if isinstance(qa, dict):
                for k in ("pass", "word_count", "issues", "suggestion", "error"):
                    if k in qa:
                        qg_out[k] = qa[k]
            return {
                "content": body or f"# {art_title or task.get('title') or '内容'}\n\n（空产物）",
                "meta": {
                    "factory_article_id": art_id,
                    "factory_title": art_title,
                    "factory_review_pass": art_review,
                    "quality_gate": qg_out,
                },
            }
        if role == "data":
            try:
                return _safe_text(agents_data.run_data(goal, brief)) or "## 数据洞察\n（数据洞察暂不可用）"
            except Exception as ex:
                return f"## 数据洞察（降级）\n> 数据模块异常: {type(ex).__name__}\n"
        if role == "ops":
            ctx = _artifact_digest(camp_id)
            try:
                return _safe_text(agents_ops.run_ops(goal, brief, context=ctx)) or "## 运营计划\n（运营输出暂不可用）"
            except Exception as ex:
                return f"## 运营计划（降级）\n> 运营模块异常: {type(ex).__name__}\n"
        if role == "review":
            ctx = _artifact_digest(camp_id)
            try:
                return _safe_text(agents_review.run_review(goal, brief, ctx)) or "## 复盘\n（复盘输出暂不可用）"
            except Exception as ex:
                return f"## 复盘（降级）\n> 复盘模块异常: {type(ex).__name__}\n"
        raise ValueError(f"未知角色: {role}")
    except ValueError:
        raise
    except Exception as ex:
        # 未预期的异常：封装成降级文本，避免任务级直接挂死
        op_logger.log(
            "campaign_runner",
            f"任务执行兜底降级[{camp_id}/{task.get('id')}]: {type(ex).__name__}: {ex}",
            level="ERROR",
        )
        return (
            f"# 任务输出（降级）\n\n"
            f"> 该任务执行时发生异常：{type(ex).__name__}。以下为最小骨架，不影响后续任务推进。\n\n"
            f"## 目标\n{goal}\n\n## 任务说明\n{brief}\n"
        )


def _task_failed(t: dict) -> bool:
    return (t.get("status") or "") == "failed"


def _deps_failed(task: dict, tasks: list) -> bool:
    """判断 task 的任何依赖是否已失败（此时该 task 应跳过）。"""
    failed_ids = {t.get("id") for t in tasks if _task_failed(t)}
    if not failed_ids:
        return False
    for d in task.get("depends_on") or []:
        if d in failed_ids:
            return True
    return False


def run_pending_tasks(cid: str) -> dict:
    """执行待处理任务。

    鲁棒策略：
      1. 单个任务异常不立刻把战役置为 failed；写任务状态为 failed，记 error
      2. 下游任务若依赖失败任务则跳过（skipped），保证至少可达稳定终态
      3. 最终根据是否有失败/跳过任务决定状态：awaiting_review（全done）/ partial_success（部分失败）
    """
    camp = store.get_campaign(cid)
    if not camp:
        raise ValueError("战役不存在")
    store.update_campaign(cid, status="running", error=None)
    tasks = list(camp.get("tasks") or [])
    for t in tasks:
        if t.get("status") is None:
            t["status"] = "pending"

    progress = True
    iterations = 0
    max_iterations = max(3, len(tasks) + 3)
    while progress and iterations < max_iterations:
        iterations += 1
        progress = False
        camp = store.get_campaign(cid) or camp
        tasks = list(camp.get("tasks") or [])
        for i, task in enumerate(tasks):
            st = task.get("status") or "pending"
            if st != "pending":
                continue
            if not _deps_done(task, tasks):
                # 依赖不满足：看看是否依赖已失败 → 标记 skipped
                if _deps_failed(task, tasks):
                    tasks[i]["status"] = "skipped"
                    tasks[i]["error"] = "上游依赖任务失败，已跳过"
                    store.update_campaign(cid, tasks=tasks)
                    progress = True
                    op_logger.log(
                        "campaign_runner",
                        f"{cid} 跳过 {task.get('id')}（上游失败）",
                        level="WARN",
                    )
                continue
            # 开始执行
            tasks[i]["status"] = "running"
            store.update_campaign(cid, tasks=tasks)
            retries_left = int(getattr(task, "get", lambda *_: 0)("retry_count", 0)) or 0
            retries_left = max(0, _TASK_MAX_RETRIES - retries_left)
            last_err = None
            while True:
                try:
                    result = _execute_task(camp, task)
                    extra = {}
                    if isinstance(result, dict) and "content" in result:
                        content = result.get("content") or ""
                        extra = result.get("meta") or {}
                    else:
                        content = result if isinstance(result, str) else str(result)
                    if not isinstance(content, str) or not content.strip():
                        content = f"# {task.get('title') or task.get('id')}\n\n（空产物）"
                    meta = store.save_artifact(
                        cid,
                        role=str(task.get("role") or "unknown"),
                        title=str(task.get("title") or task.get("id")),
                        content=content,
                        extra=extra or None,
                    )
                    tasks[i]["status"] = "done"
                    tasks[i]["result_artifact_id"] = meta.get("id")
                    if isinstance(extra, dict) and extra.get("factory_article_id"):
                        tasks[i]["factory_article_id"] = extra["factory_article_id"]
                    tasks[i]["error"] = None
                    store.bump_metric("tasks_done", 1)
                    store.update_campaign(cid, tasks=tasks)
                    progress = True
                    op_logger.log(
                        "campaign_runner",
                        f"{cid} 完成 {task.get('id')} {task.get('role')}",
                    )
                    last_err = None
                    break
                except ValueError as ex:
                    # 参数/配置错误（角色未知等）：不重试，直接失败
                    last_err = ex
                    retries_left = 0
                    break
                except Exception as ex:
                    last_err = ex
                    op_logger.log(
                        "campaign_runner",
                        f"{cid} 任务异常 {task.get('id')}(剩余重试{retries_left}): {type(ex).__name__}: {ex}",
                        level="WARN",
                    )
                    if retries_left <= 0:
                        break
                    retries_left -= 1
                    try:
                        tasks[i]["retry_count"] = int(task.get("retry_count") or 0) + 1
                    except Exception:
                        pass
            if last_err is not None:
                tasks[i]["status"] = "failed"
                tasks[i]["error"] = f"{type(last_err).__name__}: {str(last_err)[:300]}"
                store.update_campaign(cid, tasks=tasks)
                op_logger.log(
                    "campaign_runner",
                    f"{cid} 任务失败 {task.get('id')}: {tasks[i]['error']}",
                    level="ERROR",
                )
                # 注意：此处不 return！继续循环，允许推进其他无依赖任务
                progress = True

    # 终态判断
    camp = store.get_campaign(cid) or camp
    tasks = camp.get("tasks") or []
    if not tasks:
        store.update_campaign(cid, status="awaiting_review", error=None)
        return store.get_campaign(cid)

    done_n = sum(1 for t in tasks if (t.get("status") or "") == "done")
    failed_n = sum(1 for t in tasks if _task_failed(t))
    skipped_n = sum(1 for t in tasks if (t.get("status") or "") == "skipped")
    all_done = (done_n == len(tasks))

    if all_done:
        new_status = "awaiting_review"
        err = None
    elif done_n > 0 and (failed_n > 0 or skipped_n > 0):
        new_status = "partial_success"
        err = f"部分任务失败：{failed_n}失败 / {skipped_n}跳过 / 共{len(tasks)}条"
        op_logger.log(
            "campaign_runner",
            f"{cid} 部分完成（partial_success）：{err}",
            level="WARN",
        )
    else:
        new_status = "failed"
        err = f"任务全部失败/跳过：{failed_n}失败/{skipped_n}跳过"
        op_logger.log("campaign_runner", f"{cid} 任务全部不可用：{err}", level="ERROR")

    store.update_campaign(cid, status=new_status, error=err)
    if new_status == "awaiting_review":
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
        from pdf_exporter import _ensure_font, _md_to_flow
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.units import mm

        # _ensure_font() 返回实际生效的字体名（可能回退为 STSong-Light），
        # 不能用 import 的 _FONT_NAME（值绑定，拿不到回退后的新名）
        font_name = _ensure_font()
        # 用自定义样式字典而非 getSampleStyleSheet().add()，避免与默认 H1/H2/H3 重名冲突
        styles = {
            "H1": ParagraphStyle("H1", fontName=font_name, fontSize=16, leading=22, spaceAfter=8),
            "H2": ParagraphStyle("H2", fontName=font_name, fontSize=13, leading=18, spaceAfter=6),
            "H3": ParagraphStyle("H3", fontName=font_name, fontSize=11, leading=16, spaceAfter=4),
            "Body": ParagraphStyle("Body", fontName=font_name, fontSize=10, leading=14, alignment=TA_LEFT),
            "Bullet": ParagraphStyle("Bullet", fontName=font_name, fontSize=10, leading=14, leftIndent=12),
            "Quote": ParagraphStyle("Quote", fontName=font_name, fontSize=9, leading=13, textColor="#555555"),
        }
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
