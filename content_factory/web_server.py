# -*- coding: utf-8 -*-
"""
模块10：简易 Web 前端管理面板
FastAPI 后端 + 极简 HTML 前端（无需前端编译）
默认端口 8090，可在 config.yaml 修改
Web 面板功能：看板/选题/文稿/流水线/队列/定时/向量检索/标书同步/PDF/日志/权限
账号登录、权限控制
"""
import os
import socket
import datetime
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
import json

from config_loader import TEMPLATES_DIR, load_config
import auth_users
import topic_collector
import agents
import quality_gate
import data_feedback
import bid_pipeline_link
import scheduler
import vector_store
import pdf_exporter
import task_queue
import op_logger
from env_check import check_nl2sql_service

app = FastAPI(title="AI Content Factory Web")
_sessions = {}


def _token_user(request: Request):
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    user = _sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话过期")
    return user


def _perm(user, action):
    if not auth_users.check_permission(user, action):
        raise HTTPException(status_code=403, detail="权限不足")


# ---------- 登录 ----------
class LoginReq(BaseModel):
    u: str
    p: str


@app.post("/api/login")
def login(req: LoginReq):
    user = auth_users.authenticate(req.u, req.p)
    if not user:
        return {"error": "用户名或密码错误"}
    token = f"tk_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{req.u}"
    _sessions[token] = user
    op_logger.log("web_login", f"用户登录: {req.u}", user=req.u)
    return {"token": token, "user": req.u, "role": user["role"]}


# ---------- 页面 ----------
@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(TEMPLATES_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


# ---------- 各业务接口 ----------
@app.get("/api/status")
def status(user=Depends(_token_user)):
    _, blocked = None, False
    nl2sql = "在线" if check_nl2sql_service()["pass"] else "离线"
    fb = data_feedback.get_feedback_history()
    return {"topics": len(topic_collector.load_topics()),
            "queue_load": task_queue.list_queue()["load"],
            "nl2sql": nl2sql, "feedback": len(fb)}


@app.get("/api/articles")
def articles(user=Depends(_token_user)):
    return agents.list_articles()


@app.get("/api/article/preview")
def preview(file: str, user=Depends(_token_user)):
    fp = os.path.join(os.path.dirname(__file__), "articles", file)
    if not os.path.exists(fp):
        return {"text": "文件不存在"}
    with open(fp, "r", encoding="utf-8") as f:
        return {"text": f.read()}


@app.get("/api/topics")
def topics(user=Depends(_token_user)):
    return topic_collector.load_topics()


@app.post("/api/topic/mark")
def mark(data: dict, user=Depends(_token_user)):
    _perm(user, "run_task")
    topic_collector.mark_topic(data["id"], data["status"])
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
        return agents.generate_article(req.params.get("topic", ""), req.params.get("summary", ""), req.params.get("tags"))
    if req.action == "quality_check":
        return quality_gate.run_quality_check(article_id=req.params.get("article_id"))
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
    raise HTTPException(400, f"未知 action: {req.action}")


@app.get("/api/queue")
def queue(user=Depends(_token_user)):
    return task_queue.list_queue()


@app.get("/api/schedule")
def schedule(user=Depends(_token_user)):
    return scheduler.load_schedule()


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
    return auth_users.list_users()


def start():
    cfg = load_config()
    host = cfg.get("web_host", "127.0.0.1")
    port = int(cfg.get("web_port", 8090))
    op_logger.log("web_server", f"Web面板启动: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start()
