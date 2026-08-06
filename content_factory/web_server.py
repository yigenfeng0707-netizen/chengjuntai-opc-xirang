# -*- coding: utf-8 -*-
"""
成军台 Web：FastAPI + 成军看板前端
保留原内容工厂接口，新增战役（Campaign）API
含邮箱登录/注册、权限隔离、超级管理员用户洞察
"""

import os
import secrets
import datetime
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from config_loader import TEMPLATES_DIR, load_config
import auth_users
import user_analytics
import topic_collector
import agents
import quality_gate
import data_feedback
import bid_pipeline_link
import bid_workspace
import scheduler
import vector_store
import pdf_exporter
import docx_exporter
import task_queue
import op_logger
import llm_client
from env_check import check_nl2sql_service
from campaign import store as camp_store
from campaign import runner as camp_runner
import agents_data

app = FastAPI(title="成军台 · OPC OS on 息壤")

# CORS 安全配置：仅允许同源访问（Nginx 反代场景下前后端同源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Nginx 反代同源部署，无需跨域
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

_sessions = {}
_SESSION_TTL = 7200  # 会话有效期 2 小时（秒）


def _token_user(request: Request):
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    user = _sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话过期")
    # 检查会话是否过期
    expires_at = user.get("_expires_at")
    if expires_at and datetime.datetime.now().timestamp() > expires_at:
        _sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    return user


def _perm(user, action):
    if not auth_users.check_permission(user, action):
        raise HTTPException(status_code=403, detail="权限不足")


def _require_super_admin(user):
    if not auth_users.is_super_admin(user):
        raise HTTPException(status_code=403, detail="仅超级管理员可操作")


def _campaign_owner_ok(user, camp: dict) -> bool:
    if auth_users.can_view_all_campaigns(user):
        return True
    # 评委/全员可读演示快照
    if camp.get("demo_snapshot"):
        return True
    owner = camp.get("created_by") or ""
    return owner == user.get("username") or owner == (user.get("email") or "")


def _filter_campaigns(user, items: list) -> list:
    if auth_users.can_view_all_campaigns(user):
        return items
    uname = user.get("username")
    email = user.get("email") or ""
    out = []
    for c in items:
        if (c.get("created_by") or "") in (uname, email):
            out.append(c)
            continue
        # list_campaigns 摘要无 demo_snapshot 字段时补读
        if c.get("demo_snapshot"):
            out.append(c)
            continue
        full = camp_store.get_campaign(c["id"])
        if full and full.get("demo_snapshot"):
            out.append(c)
    return out


def _allow_mock() -> bool:
    cfg = load_config()
    return bool(cfg.get("demo_mode", {}).get("allow_mock_llm", False))


class LoginReq(BaseModel):
    u: str
    p: str


class RegisterReq(BaseModel):
    email: str
    password: str
    display_name: str = ""


@app.post("/api/login")
def login(req: LoginReq):
    if not (req.u or "").strip() or not req.p:
        return {"error": "请输入邮箱/用户名和密码"}
    user = auth_users.authenticate(req.u, req.p)
    if not user:
        return {"error": "邮箱/用户名或密码错误"}
    auth_users.touch_login(req.u)
    # 刷新会话用户（含 last_login）
    user = auth_users.authenticate(req.u, req.p) or user
    display = user.get("email") or user.get("username") or req.u
    token = f"tk_{secrets.token_hex(16)}"
    _sessions[token] = user
    _sessions[token]["_expires_at"] = datetime.datetime.now().timestamp() + _SESSION_TTL
    op_logger.log("web_login", f"用户登录: {display}", user=user["username"])
    user_analytics.log_event(
        user["username"], "login", {"via": req.u, "role": user.get("role")}
    )
    return {
        "token": token,
        "user": user.get("username"),
        "email": user.get("email") or "",
        "display_name": user.get("display_name") or user.get("username"),
        "role": user["role"],
    }


@app.post("/api/register")
def register(req: RegisterReq):
    try:
        user = auth_users.register_user(req.email, req.password, req.display_name)
    except ValueError as ex:
        return {"error": str(ex)}
    user_analytics.log_event(user["username"], "register", {"email": user.get("email")})
    op_logger.log(
        "web_register", f"用户注册: {user.get('email')}", user=user["username"]
    )
    return {
        "ok": True,
        "user": user["username"],
        "email": user.get("email"),
        "role": user["role"],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(TEMPLATES_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


def _mcp_packaging_status() -> dict:
    """成军台/内容工厂 stdio MCP 是否已打包（不启进程；文件+工具清单可见即可）。"""
    base = os.path.dirname(os.path.abspath(__file__))
    campaign = os.path.join(base, "mcp_campaign_server.py")
    factory = os.path.join(base, "mcp_server.py")
    root_mcp = os.path.join(os.path.dirname(base), "mcp.json")
    campaign_tools = [
        "start_campaign",
        "list_campaigns",
        "list_tasks",
        "approve_gate",
        "export_report",
    ]
    factory_tools = [
        "collect_topics",
        "generate_article",
        "quality_check",
        "publish_wechat_draft",
        "analysis_topic_data",
        "export_knowledge_doc",
        "sync_vector_store",
        "run_scheduled_task",
        "export_article_pdf",
        "task_queue_control",
    ]
    ready = os.path.isfile(campaign) and os.path.isfile(factory)
    return {
        "ready": ready,
        "label": "MCP 工具已就绪" if ready else "MCP 封装缺失",
        "servers": {
            "chengjuntai-campaign": {
                "file": "content_factory/mcp_campaign_server.py",
                "present": os.path.isfile(campaign),
                "tools": campaign_tools,
            },
            "content-factory": {
                "file": "content_factory/mcp_server.py",
                "present": os.path.isfile(factory),
                "tools": factory_tools,
            },
        },
        "config": "mcp.json（仓库根）" if os.path.isfile(root_mcp) else "mcp.json 缺失",
        "smoke": "python scripts/smoke_mcp.py",
        "note": "评委 60s 走 Web；MCP 供 Cursor/TeleAgent 宿主挂载同套战役能力",
    }


@app.get("/api/health")
def health():
    """无需登录的健康检查"""
    llm = llm_client.provider_status()
    nl2sql_ok = False
    try:
        nl2sql_ok = bool(check_nl2sql_service().get("pass"))
    except Exception:
        nl2sql_ok = False
    cfg = load_config()
    demo_ready = bool(llm.get("enabled"))
    public = _is_public_deploy(cfg)
    pwd_risk = auth_users.default_password_risk()
    mcp_pkg = _mcp_packaging_status()
    try:
        import wechat_publisher

        wechat_st = wechat_publisher.status_summary()
    except Exception as ex:
        wechat_st = {"configured": False, "hint": f"wechat 模块不可用: {ex}"}
    return {
        "ok": True,
        "product": cfg.get("product_name", "成军台"),
        "slogan": cfg.get("product_slogan", ""),
        "llm": llm,
        "nl2sql": "在线" if nl2sql_ok else "离线",
        "wechat": wechat_st,
        "mcp": mcp_pkg,
        "campaigns": len(camp_store.list_campaigns(20)),
        "metrics": camp_store.metrics_snapshot(),
        "demo_ready": demo_ready,
        "public_deploy": public,
        "password_hygiene": {
            "recommend_change_defaults": bool(pwd_risk.get("recommend_change"))
            and public,
            "demo_accounts_present": bool(pwd_risk.get("demo_accounts_enabled")),
            # 不返回口令；仅提示公网须改密
            "message": (
                "公网部署检测到演示账号仍启用 — 请立即修改 admin/operator 密码（见 docs/PROD_HARDENING.md）"
                if public and pwd_risk.get("recommend_change")
                else None
            ),
        },
        "scheduler": scheduler.status(),
        "auth": {
            "email_login": True,
            "register": True,
            "password_hashing": True,
            "roles": ["super_admin", "operator", "user", "guest"],
        },
        "hint": llm.get("hint")
        or (
            "评委路径就绪：登录成军看板 → 发起成军 → 人审 → 导出周报"
            if demo_ready
            else "结构可浏览；配置 XIRANG_API_KEY 后可真实演示。见 docs/NEXT_SPRINT.md"
        ),
    }


def _is_public_deploy(cfg: Optional[dict] = None) -> bool:
    """公网/非本机部署探测：env CHENGJUNTAI_PUBLIC=1 或 config.public_deploy / 非 loopback host。"""
    if (os.environ.get("CHENGJUNTAI_PUBLIC") or "").strip() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    cfg = cfg or load_config()
    if cfg.get("public_deploy") is True:
        return True
    host = (
        str(cfg.get("web_host") or os.environ.get("CHENGJUNTAI_HOST") or "127.0.0.1")
        .strip()
        .lower()
    )
    if host in ("0.0.0.0", "::", "*"):
        # 绑定全网卡时仍可能是本地演示；仅 env/config 强制时才算公网
        return bool(cfg.get("public_deploy"))
    if host not in ("127.0.0.1", "localhost", "::1"):
        return True
    return False


@app.get("/api/status")
def status(user=Depends(_token_user)):
    nl2sql = "在线" if check_nl2sql_service()["pass"] else "离线"
    fb = data_feedback.get_feedback_history()
    llm = llm_client.provider_status()
    camps = _filter_campaigns(user, camp_store.list_campaigns(10))
    return {
        "topics": len(topic_collector.load_topics()),
        "queue_load": task_queue.list_queue()["load"],
        "nl2sql": nl2sql,
        "feedback": len(fb),
        "llm": llm,
        "product": load_config().get("product_name", "成军台"),
        "slogan": load_config().get("product_slogan", ""),
        "metrics": camp_store.metrics_snapshot(),
        "campaigns": camps,
    }


# ---------- 成军台战役 API ----------
class StartCampaignReq(BaseModel):
    goal: str
    template: str = "lead_gen"
    auto_approve: bool = False


@app.post("/api/campaign/start")
def campaign_start(req: StartCampaignReq, user=Depends(_token_user)):
    _perm(user, "run_task")
    if not req.goal.strip():
        raise HTTPException(400, "目标不能为空")
    try:
        camp = camp_runner.start_campaign(
            req.goal.strip(),
            template=req.template,
            created_by=user["username"],
            allow_mock=_allow_mock(),
            auto_approve=req.auto_approve
            or bool(load_config().get("demo_mode", {}).get("auto_approve_gate")),
        )
        auth_users.bump_usage(user["username"], "campaigns_started", 1)
        user_analytics.log_event(
            user["username"],
            "campaign_start",
            {"cid": camp.get("id"), "template": req.template},
        )
        return camp
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/campaigns")
def campaigns(user=Depends(_token_user)):
    return _filter_campaigns(user, camp_store.list_campaigns(50))


@app.get("/api/campaign/{cid}")
def campaign_detail(cid: str, user=Depends(_token_user)):
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权查看该战役")
    return c


class GateReq(BaseModel):
    note: str = ""


@app.post("/api/campaign/{cid}/approve")
def campaign_approve(cid: str, req: GateReq, user=Depends(_token_user)):
    _perm(user, "run_task")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    try:
        result = camp_runner.approve_gate(cid, note=req.note)
        auth_users.bump_usage(user["username"], "tasks_done", 1)
        user_analytics.log_event(
            user["username"], "approve", {"cid": cid, "note": req.note}
        )
        return result
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.post("/api/campaign/{cid}/reject")
def campaign_reject(cid: str, req: GateReq, user=Depends(_token_user)):
    _perm(user, "run_task")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    return camp_runner.reject_gate(cid, note=req.note)


@app.post("/api/campaign/{cid}/run")
def campaign_run(cid: str, user=Depends(_token_user)):
    _perm(user, "run_task")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    try:
        return camp_runner.run_pending_tasks(cid)
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.post("/api/campaign/{cid}/report")
def campaign_report(cid: str, user=Depends(_token_user)):
    _perm(user, "export")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    try:
        path = camp_runner.export_weekly_report(cid)
        auth_users.bump_usage(user["username"], "reports_exported", 1)
        camp = camp_store.get_campaign(cid)
        report = (camp or {}).get("report") or {}
        user_analytics.log_event(
            user["username"],
            "report",
            {
                "cid": cid,
                "path": path,
                "docx": report.get("docx"),
                "pdf": report.get("pdf"),
            },
        )
        return {
            "ok": True,
            "path": path,
            "docx": report.get("docx") or "",
            "pdf": report.get("pdf") or "",
            "md": report.get("md") or "",
            "campaign": camp,
        }
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.post("/api/campaign/{cid}/report_docx")
def campaign_report_docx(cid: str, user=Depends(_token_user)):
    _perm(user, "export")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    try:
        path = camp_runner.export_weekly_report_docx(cid)
        auth_users.bump_usage(user["username"], "reports_exported", 1)
        user_analytics.log_event(
            user["username"], "report_docx", {"cid": cid, "path": path}
        )
        return {
            "ok": True,
            "docx": path,
            "download": f"/api/campaign/{cid}/report_docx/file",
        }
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/campaign/{cid}/report_docx/file")
def campaign_report_docx_file(cid: str, user=Depends(_token_user)):
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    path = ((c.get("report") or {}).get("docx")) or ""
    if not path or not os.path.exists(path):
        try:
            path = camp_runner.export_weekly_report_docx(cid)
        except Exception as ex:
            raise HTTPException(500, str(ex))
    return FileResponse(
        path,
        filename=os.path.basename(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/api/campaign/{cid}/sync_to_factory")
def campaign_sync_factory(cid: str, user=Depends(_token_user)):
    """战役内容产物 → 内容工厂（登记/关联）"""
    _perm(user, "run_task")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    try:
        return camp_runner.sync_campaign_to_factory(cid)
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.post("/api/article/link_campaign")
def article_link_campaign(req: dict, user=Depends(_token_user)):
    """内容工厂稿件 → 关联指定战役"""
    _perm(user, "run_task")
    aid = (req or {}).get("article_id") or ""
    cid = (req or {}).get("campaign_id") or ""
    if not aid or not cid:
        raise HTTPException(400, "需要 article_id 与 campaign_id")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    try:
        linked = agents.link_article_campaign(aid, cid)
        return {"ok": True, "article": linked}
    except Exception as ex:
        raise HTTPException(400, str(ex))


@app.get("/api/campaign/{cid}/factory_articles")
def campaign_factory_articles(cid: str, user=Depends(_token_user)):
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权查看")
    return agents.articles_for_campaign(cid)


@app.get("/api/bid/status")
def bid_status(user=Depends(_token_user)):
    """标书工作台路径状态（优先 bid_telecom.db，JSON 冷回退）"""
    return bid_pipeline_link.bid_status()


@app.get("/api/bid/projects")
def bid_projects(user=Depends(_token_user)):
    return bid_pipeline_link.list_bid_projects()


@app.get("/api/bid/refresh_status")
def bid_refresh_status(user=Depends(_token_user)):
    """轮询真实标讯抓取进度（logs/fetch_status.json）。"""
    import sys

    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from fetch_real_data import load_status, db_stats

    st = load_status()
    stats = db_stats()
    return {**st, "db_stats": stats}


@app.post("/api/bid/refresh_real")
def bid_refresh_real(req: dict = None, user=Depends(_token_user)):
    """
    后台刷新浙江政采网真实标讯。
    body: {quick?: bool, full_rebuild?: bool, max_districts?: int, skip_detail?: bool}
    权限：super_admin / operator（run_task）。
    """
    _perm(user, "run_task")
    if not (
        auth_users.is_super_admin(user)
        or user.get("role") in ("operator", "super_admin")
        or auth_users.check_permission(user, "*")
    ):
        # run_task 用户也可触发（运维友好）；超管/运营优先
        pass
    import sys
    import subprocess
    import threading

    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from fetch_real_data import load_status, write_status, db_stats

    cur = load_status()
    if cur.get("running"):
        return {
            "ok": False,
            "started": False,
            "message": "已有抓取任务在运行",
            "status": cur,
            "db_stats": db_stats(),
        }

    body = req if isinstance(req, dict) else {}
    quick = bool(body.get("quick", True))
    full_rebuild = bool(body.get("full_rebuild", False))
    max_districts = body.get("max_districts")
    skip_detail = body.get("skip_detail")
    args = [sys.executable, os.path.join(root, "scripts", "refresh_real_bids.py")]
    if full_rebuild:
        args.append("--full-rebuild")
    if quick and not full_rebuild:
        args.append("--quick")
    elif max_districts:
        args.extend(["--max-districts", str(int(max_districts))])
    if skip_detail:
        args.append("--skip-detail")
    # 子进程自带超时保护，避免僵尸挂死 UI
    args.extend(["--timeout", str(int(body.get("timeout") or 600))])

    write_status(
        running=True,
        phase="spawn",
        ok=None,
        progress=0,
        message="已启动后台刷新…",
        started_by=user.get("username"),
        started_at=datetime.datetime.now().isoformat(timespec="seconds"),
        error=None,
    )

    def _spawn():
        try:
            subprocess.run(
                args,
                cwd=root,
                timeout=int(body.get("timeout") or 620),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            write_status(
                running=False,
                phase="timeout",
                ok=False,
                message="子进程超时",
                error="subprocess timeout",
                finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
            )
        except Exception as ex:
            write_status(
                running=False,
                phase="failed",
                ok=False,
                message=str(ex),
                error=str(ex),
                finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
            )

    threading.Thread(target=_spawn, daemon=True).start()
    op_logger.log(
        "bid_refresh", f"用户 {user.get('username')} 触发真实标讯刷新 quick={quick}"
    )
    return {
        "ok": True,
        "started": True,
        "message": "已在后台刷新真实标讯，请稍后点「刷新状态」或重新打开标书工作台",
        "args": args[2:],
        "db_stats": db_stats(),
    }


@app.get("/api/bid/themes")
def bid_themes(user=Depends(_token_user)):
    return bid_pipeline_link.fetch_bid_project_themes()


@app.get("/api/bid/knowledge")
def bid_knowledge(user=Depends(_token_user)):
    return bid_pipeline_link.list_knowledge_index(60)


@app.post("/api/bid/seed")
def bid_seed(user=Depends(_token_user)):
    _perm(user, "run_task")
    return bid_pipeline_link.ensure_demo_projects(force=True)


@app.post("/api/bid/sync")
def bid_sync(user=Depends(_token_user)):
    _perm(user, "run_task")
    return bid_pipeline_link.sync_knowledge_to_bid()


@app.post("/api/bid/push_article")
def bid_push_article(req: dict, user=Depends(_token_user)):
    _perm(user, "run_task")
    aid = (req or {}).get("article_id") or ""
    if not aid:
        raise HTTPException(400, "需要 article_id")
    try:
        return bid_pipeline_link.push_article_to_knowledge(aid)
    except Exception as ex:
        raise HTTPException(400, str(ex))


@app.post("/api/bid/push_campaign")
def bid_push_campaign(req: dict, user=Depends(_token_user)):
    """战役产物 → 标书知识库。body: campaign_id, artifact_id?"""
    _perm(user, "run_task")
    cid = (req or {}).get("campaign_id") or ""
    aid = (req or {}).get("artifact_id") or ""
    if not cid:
        raise HTTPException(400, "需要 campaign_id")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作")
    if aid:
        text = camp_store.read_artifact_content(cid, aid)
        if not text:
            raise HTTPException(404, "产物不存在")
        meta = next((a for a in (c.get("artifacts") or []) if a.get("id") == aid), {})
        title = meta.get("title") or aid
        tags = [meta.get("role") or "战役产物", "标书知识"]
        return bid_pipeline_link.push_campaign_text_to_knowledge(
            cid,
            title,
            text,
            tags=tags,
            artifact_id=aid,
        )
    # 无 artifact：汇总全部产物
    arts = c.get("artifacts") or []
    pushed = []
    for a in arts:
        text = camp_store.read_artifact_content(cid, a.get("id") or "")
        if not text:
            continue
        pushed.append(
            bid_pipeline_link.push_campaign_text_to_knowledge(
                cid,
                a.get("title") or a.get("id"),
                text,
                tags=[a.get("role") or "战役产物", "标书知识"],
                artifact_id=a.get("id") or "",
            )
        )
    if not pushed:
        raise HTTPException(400, "该战役暂无产物可推送")
    return {"ok": True, "pushed_count": len(pushed), "items": pushed}


@app.post("/api/bid/themes_to_topics")
def bid_themes_to_topics(req: dict = None, user=Depends(_token_user)):
    _perm(user, "run_task")
    suggestions = (req or {}).get("suggestions") if isinstance(req, dict) else None
    return bid_pipeline_link.write_themes_to_topic_pool(suggestions=suggestions)


@app.post("/api/bid/theme_to_campaign")
def bid_theme_to_campaign(req: dict, user=Depends(_token_user)):
    _perm(user, "run_task")
    industry = (req or {}).get("industry") or ""
    template = (req or {}).get("template") or "lead_gen"
    auto_approve = bool((req or {}).get("auto_approve"))
    project_name = (req or {}).get("project_name") or ""
    project_id = (req or {}).get("project_id") or ""
    try:
        result = bid_pipeline_link.theme_to_campaign(
            industry=industry,
            template=template,
            created_by=user.get("username") or "admin",
            auto_approve=auto_approve,
            project_name=project_name,
            project_id=project_id,
        )
        auth_users.bump_usage(user["username"], "campaigns_started", 1)
        return result
    except Exception as ex:
        raise HTTPException(400, str(ex))


@app.post("/api/bid/workspace/parse")
def bid_workspace_parse(req: dict, user=Depends(_token_user)):
    _perm(user, "run_task")
    text = (req or {}).get("text") or ""
    project_id = (req or {}).get("project_id") or ""
    use_llm = (req or {}).get("use_llm", True)
    try:
        return bid_workspace.parse_tender_requirements(
            text, project_id=project_id, use_llm=use_llm
        )
    except Exception as ex:
        raise HTTPException(400, str(ex))


@app.post("/api/bid/workspace/matrix")
def bid_workspace_matrix(req: dict, user=Depends(_token_user)):
    requirements = (req or {}).get("requirements") or []
    if not requirements:
        raise HTTPException(400, "需要 requirements")
    return bid_workspace.build_evidence_gap_matrix(requirements)


@app.post("/api/bid/workspace/export_docx")
def bid_workspace_export(req: dict, user=Depends(_token_user)):
    _perm(user, "export")
    requirements = (req or {}).get("requirements") or []
    matrix = (req or {}).get("matrix")
    if not matrix:
        matrix = bid_workspace.build_evidence_gap_matrix(requirements)
    try:
        return bid_workspace.export_matrix_docx(
            requirements,
            matrix,
            title=(req or {}).get("title") or "成军台·标书材料包",
            project_name=(req or {}).get("project_name") or "",
        )
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/campaign/{cid}/artifact/{aid}")
def campaign_artifact(cid: str, aid: str, user=Depends(_token_user)):
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权查看该战役")
    text = camp_store.read_artifact_content(cid, aid)
    if not text:
        raise HTTPException(404, "产物不存在")
    meta = next((a for a in (c.get("artifacts") or []) if a.get("id") == aid), {})
    return {
        "id": aid,
        "title": meta.get("title") or aid,
        "role": meta.get("role") or "",
        "text": text,
        "campaign_id": cid,
        "factory_article_id": meta.get("factory_article_id"),
        "quality_gate": meta.get("quality_gate"),
    }


@app.post("/api/campaign/{cid}/artifact/{aid}/docx")
def campaign_artifact_docx(cid: str, aid: str, user=Depends(_token_user)):
    _perm(user, "export")
    c = camp_store.get_campaign(cid)
    if not c:
        raise HTTPException(404, "战役不存在")
    if not _campaign_owner_ok(user, c):
        raise HTTPException(403, "无权操作该战役")
    text = camp_store.read_artifact_content(cid, aid)
    if not text:
        raise HTTPException(404, "产物不存在")
    meta = next((a for a in (c.get("artifacts") or []) if a.get("id") == aid), {})
    try:
        out = os.path.join(docx_exporter.EXPORT_DOCX_DIR, f"{cid}_{aid}.docx")
        path = docx_exporter.md_to_docx(text, out, title=meta.get("title") or aid)
        return {
            "ok": True,
            "docx": path,
            "download": f"/api/download_docx?path={os.path.basename(path)}",
        }
    except Exception as ex:
        raise HTTPException(500, str(ex))


@app.get("/api/artifacts/center")
def artifacts_center(user=Depends(_token_user)):
    arts = camp_store.list_all_artifacts(80)
    # 权限过滤
    if not auth_users.can_view_all_campaigns(user):
        allowed = {
            c["id"] for c in _filter_campaigns(user, camp_store.list_campaigns(50))
        }
        arts = [a for a in arts if a.get("campaign_id") in allowed]
    articles = agents.list_articles()
    return {"campaign_artifacts": arts, "articles": articles}


@app.get("/api/download_docx")
def download_docx(path: str, user=Depends(_token_user)):
    """仅允许下载 export_docx 目录内文件名。"""
    safe = os.path.basename(path or "")
    if not safe or not safe.endswith(".docx"):
        raise HTTPException(400, "非法文件")
    fp = os.path.join(docx_exporter.EXPORT_DOCX_DIR, safe)
    if not os.path.exists(fp):
        raise HTTPException(404, "文件不存在")
    return FileResponse(
        fp,
        filename=safe,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/metrics")
def metrics(user=Depends(_token_user)):
    return camp_store.metrics_snapshot()


@app.get("/api/templates")
def templates(user=Depends(_token_user)):
    from commander import TEMPLATES

    return TEMPLATES


# ---------- 原内容工厂接口 ----------
@app.get("/api/articles")
def articles(user=Depends(_token_user)):
    return agents.list_articles()


@app.get("/api/wechat/status")
def wechat_status(user=Depends(_token_user)):
    """公众号草稿通道状态（不返回完整密钥）。"""
    import wechat_publisher

    return wechat_publisher.status_summary()


@app.post("/api/wechat/publish_draft")
def wechat_publish_draft(req: dict, user=Depends(_token_user)):
    """将内容工厂稿件推送到微信公众号草稿箱（不群发）。"""
    _perm(user, "run_task")
    aid = (req or {}).get("article_id") or ""
    if not aid:
        raise HTTPException(400, "需要 article_id")
    import wechat_publisher

    result = wechat_publisher.publish_article_to_draft(aid)
    # 未配置：200 + skipped（前端大声提示）；业务失败也返回 JSON，由前端渲染 error
    return result


@app.get("/api/article/preview")
def preview(file: str, user=Depends(_token_user)):
    from config_loader import ARTICLES_DIR

    safe = os.path.basename(file or "").strip()
    if not safe:
        raise HTTPException(400, "缺少文件名")
    fp = os.path.join(ARTICLES_DIR, safe)
    if not os.path.exists(fp) or not os.path.isfile(fp):
        raise HTTPException(404, "文件不存在")
    with open(fp, "r", encoding="utf-8") as f:
        return {"text": f.read(), "file": safe, "ok": True}


@app.get("/api/article/{aid}/docx")
def article_docx_get(aid: str, user=Depends(_token_user)):
    _perm(user, "export")
    try:
        path = docx_exporter.export_article_by_id(aid)
        return FileResponse(
            path,
            filename=os.path.basename(path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as ex:
        raise HTTPException(404, str(ex))


@app.post("/api/article/{aid}/docx")
def article_docx_post(aid: str, user=Depends(_token_user)):
    _perm(user, "export")
    try:
        path = docx_exporter.export_article_by_id(aid)
        return {"ok": True, "docx": path, "download": f"/api/article/{aid}/docx"}
    except Exception as ex:
        raise HTTPException(404, str(ex))


@app.get("/api/topics")
def topics(user=Depends(_token_user)):
    return topic_collector.load_topics()


@app.post("/api/topic/mark")
def mark(data: dict, user=Depends(_token_user)):
    _perm(user, "run_task")
    tid = (data or {}).get("id") or ""
    status = (data or {}).get("status") or ""
    if not tid or not status:
        raise HTTPException(400, "缺少 id 或 status")
    ok = topic_collector.mark_topic(tid, status)
    if not ok:
        raise HTTPException(404, "选题不存在")
    return {"ok": True}


class RunReq(BaseModel):
    action: str
    params: dict = {}


@app.post("/api/run")
def run(req: RunReq, user=Depends(_token_user)):
    _perm(user, "run_task")
    op_logger.log("web_run", f"手动执行: {req.action}", user=user["username"])
    if req.action == "collect_topics":
        return topic_collector.collect_topics(req.params.get("topk", 6))
    if req.action == "generate_article":
        result = agents.generate_article(
            req.params.get("topic", ""),
            req.params.get("summary", ""),
            req.params.get("tags"),
            campaign_id=req.params.get("campaign_id"),
        )
        auth_users.bump_usage(user["username"], "articles_generated", 1)
        user_analytics.log_event(
            user["username"],
            "generate_article",
            {"article_id": result.get("id") if isinstance(result, dict) else None},
        )
        return result
    if req.action == "quality_check":
        return quality_gate.run_quality_check(article_id=req.params.get("article_id"))
    if req.action == "publish_wechat_draft":
        import wechat_publisher

        return wechat_publisher.publish_article_to_draft(
            req.params.get("article_id") or ""
        )
    if req.action == "full_pipeline":
        # 选题→生成→质检→向量（generate_article 已入库向量）
        from main import run_full_pipeline

        topic = req.params.get("topic") or None
        result = run_full_pipeline(
            topic=topic,
            summary=req.params.get("summary", ""),
            tags=req.params.get("tags"),
            priority=int(req.params.get("priority", 5)),
        )
        if isinstance(result, dict) and result.get("article_id"):
            auth_users.bump_usage(user["username"], "articles_generated", 1)
        return result or {"ok": False, "error": "流水线无产出"}
    if req.action == "analysis_topic_data":
        return data_feedback.analyze_topic_data_with_nl2sql()
    if req.action == "sync_knowledge_to_bid":
        return bid_pipeline_link.sync_knowledge_to_bid()
    if req.action == "fetch_bid_project_themes":
        return bid_pipeline_link.fetch_bid_project_themes()
    if req.action == "export_all":
        return pdf_exporter.export_all()
    if req.action == "export_article_pdf":
        return {"file": pdf_exporter.export_article_by_id(req.params.get("article_id"))}
    if req.action == "export_article_docx":
        path = docx_exporter.export_article_by_id(req.params.get("article_id"))
        return {
            "ok": True,
            "docx": path,
            "download": f"/api/article/{req.params.get('article_id')}/docx",
        }
    raise HTTPException(400, f"未知 action: {req.action}")


class Nl2sqlReq(BaseModel):
    question: str
    dataset_name: str = ""
    chart_type: str = "table"


@app.get("/api/nl2sql/status")
def nl2sql_status(user=Depends(_token_user)):
    mcp_ok = agents_data.nl2sql_online()
    znws_ok = agents_data.znws_online()
    import sys

    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from fetch_real_data import db_stats, load_status

        stats = db_stats()
        fetch_st = load_status()
    except Exception:
        stats = {
            "db_path": os.path.join(root, "bid_telecom.db"),
            "db_exists": os.path.exists(os.path.join(root, "bid_telecom.db")),
            "row_count": None,
            "real_count": None,
            "demo_count": None,
            "last_refresh": None,
            "mtime": None,
        }
        fetch_st = {}
        db_path = stats["db_path"]
        if stats["db_exists"]:
            try:
                import sys as _sys

                _repo_root = os.path.dirname(os.path.dirname(__file__))
                if _repo_root not in _sys.path:
                    _sys.path.insert(0, _repo_root)
                import db as _db

                conn = _db.get_conn()
                stats["row_count"] = conn.execute(
                    "SELECT COUNT(*) FROM bid_projects"
                ).fetchone()[0]
                conn.close()
            except Exception:
                pass
    online = mcp_ok or znws_ok
    real_n = stats.get("real_count") or 0
    hint = (
        f"可提问真实库（real={real_n} / total={stats.get('row_count')}）"
        if online and real_n
        else (
            "可提问（库内多为演示种子，请刷新真实标讯）"
            if online
            else "离线：请运行 scripts/start_real_data.bat 或 start_nl2sql_demo.bat"
        )
    )
    return {
        "online": online,
        "mcp": mcp_ok,
        "znws": znws_ok,
        "db_path": stats.get("db_path"),
        "db_exists": stats.get("db_exists"),
        "row_count": stats.get("row_count"),
        "real_count": stats.get("real_count"),
        "demo_count": stats.get("demo_count"),
        "last_refresh": stats.get("last_refresh") or stats.get("mtime"),
        "last_ok": stats.get("last_ok"),
        "fetch_running": bool(fetch_st.get("running")),
        "fetch_message": fetch_st.get("message"),
        "data_mode": "real"
        if real_n
        else ("demo" if (stats.get("row_count") or 0) else "empty"),
        "hint": hint,
    }


@app.post("/api/nl2sql/query")
def nl2sql_query(req: Nl2sqlReq, user=Depends(_token_user)):
    if not req.question.strip():
        raise HTTPException(400, "问题不能为空")
    result = agents_data.query_nl2sql(
        req.question.strip(), req.dataset_name, req.chart_type
    )
    user_analytics.log_event(
        user["username"],
        "nl2sql_query",
        {
            "ok": result.get("ok"),
            "offline": result.get("offline"),
            "q": req.question[:80],
        },
    )
    return result


@app.post("/api/nl2sql/seed")
def nl2sql_seed(user=Depends(_token_user)):
    """写入最小演示库（不启动进程；进程请用 bat）。"""
    _perm(user, "run_task")
    import sys

    root = os.path.dirname(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    from seed_demo_db import ensure_demo_db

    info = ensure_demo_db(force=False)
    return {"ok": True, **info, "start_script": "scripts/start_nl2sql_demo.bat"}


@app.get("/api/queue")
def queue(user=Depends(_token_user)):
    return task_queue.list_queue()


@app.get("/api/schedule")
def schedule(user=Depends(_token_user)):
    cfg = scheduler.load_schedule()
    st = scheduler.status()
    return {**cfg, "runtime": st}


@app.get("/api/schedule/status")
def schedule_status(user=Depends(_token_user)):
    return scheduler.status()


@app.post("/api/schedule/start")
def schedule_start(user=Depends(_token_user)):
    """在 Web 进程内嵌启动轻量调度线程（Windows 友好；亦可用 start_scheduler.bat）。"""
    _perm(user, "schedule_control")
    return scheduler.start_background(embedded=True)


@app.post("/api/schedule/stop")
def schedule_stop(user=Depends(_token_user)):
    _perm(user, "schedule_control")
    return scheduler.stop_background()


class ToggleReq(BaseModel):
    id: str
    enabled: bool


@app.post("/api/schedule/toggle")
def toggle(req: ToggleReq, user=Depends(_token_user)):
    _perm(user, "schedule_control")
    return {"ok": scheduler.toggle_task(req.id, req.enabled)}


@app.get("/api/vector/search")
def vsearch(q: str, user=Depends(_token_user)):
    return vector_store.search(q, topk=8)


@app.get("/api/logs")
def logs(user=Depends(_token_user)):
    return op_logger.tail(150)


@app.get("/api/users")
def users(user=Depends(_token_user)):
    _perm(user, "view")
    # 普通用户只看到脱敏列表；超级管理员看完整用量
    if auth_users.is_super_admin(user):
        return auth_users.list_users(include_usage=True)
    return [
        {
            "username": u["username"],
            "email": u.get("email") or "",
            "role": u["role"],
            "enabled": u.get("enabled", True),
            "display_name": u.get("display_name") or u["username"],
        }
        for u in auth_users.list_users(include_usage=False)
    ]


# ---------- 超级管理员：权限管理 / 用户洞察 ----------
class UserEnableReq(BaseModel):
    identity: str
    enabled: bool


class UserRoleReq(BaseModel):
    identity: str
    role: str


class ProfileReq(BaseModel):
    identity: str
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    segment: Optional[str] = None


@app.get("/api/admin/usage")
def admin_usage(user=Depends(_token_user)):
    _require_super_admin(user)
    return user_analytics.usage_table()


@app.get("/api/admin/persona/{identity}")
def admin_persona(identity: str, user=Depends(_token_user)):
    _require_super_admin(user)
    return user_analytics.infer_persona(identity)


@app.get("/api/admin/trail/{identity}")
def admin_trail(identity: str, user=Depends(_token_user), limit: int = 100):
    _require_super_admin(user)
    return {
        "identity": identity,
        "events": user_analytics.read_events(identity, limit=limit),
        "persona": user_analytics.infer_persona(identity),
    }


@app.post("/api/admin/user/enable")
def admin_user_enable(req: UserEnableReq, user=Depends(_token_user)):
    _require_super_admin(user)
    if not auth_users.set_user_enabled(req.identity, req.enabled):
        raise HTTPException(404, "用户不存在")
    user_analytics.log_event(
        user["username"],
        "admin_enable",
        {"target": req.identity, "enabled": req.enabled},
    )
    return {"ok": True}


@app.post("/api/admin/user/role")
def admin_user_role(req: UserRoleReq, user=Depends(_token_user)):
    _require_super_admin(user)
    if not auth_users.set_user_role(req.identity, req.role):
        raise HTTPException(400, "角色无效或用户不存在")
    user_analytics.log_event(
        user["username"],
        "admin_role",
        {"target": req.identity, "role": req.role},
    )
    return {"ok": True}


@app.post("/api/admin/user/profile")
def admin_user_profile(req: ProfileReq, user=Depends(_token_user)):
    _require_super_admin(user)
    updated = auth_users.update_profile(
        req.identity,
        notes=req.notes,
        tags=req.tags,
        segment=req.segment,
    )
    if not updated:
        raise HTTPException(404, "用户不存在")
    return {"ok": True, "user": updated}


def start():
    cfg = load_config()
    host = cfg.get("web_host", "127.0.0.1")
    port = int(cfg.get("web_port", 8090))
    op_logger.log("web_server", f"成军台启动: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start()
