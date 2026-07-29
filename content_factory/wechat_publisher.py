# -*- coding: utf-8 -*-
"""
微信公众号 · 草稿箱优先发布
- 凭证：环境变量 / config.yaml wechat 段 / config.wechat.local.yaml（均 gitignore）
- 流程：client_credential 取 token → draft/add 写入草稿箱（不群发）
- 失败可见：未配置凭证 / token 失败 / IP 白名单 / 缺封面 media_id 均明确返回，不伪装成功
"""
from __future__ import annotations

import html
import json
import os
import re
import time
from typing import Any, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

import yaml

from config_loader import ARTICLES_DIR, ROOT, load_config
import op_logger

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
MATERIAL_ADD_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"

# 常见错误码 → 面向用户的说明（不全量枚举）
ERRCODE_HINTS = {
    40001: "access_token 无效或 AppSecret 错误，请检查凭证后重试",
    40013: "AppID 无效",
    40014: "access_token 不合法",
    40125: "AppSecret 无效",
    40164: "调用 IP 不在公众号白名单，请在公众平台「开发 → 基本配置」添加本机公网 IP",
    41001: "缺少 access_token",
    42001: "access_token 过期，请重试",
    45009: "接口调用超过日限额",
    48001: "接口未授权：确认公众号已开通草稿箱/素材相关权限",
    53500: "草稿发布相关权限未开通",
}

_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0, "app_id": None}


def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return ""
    if len(s) <= keep * 2:
        return s[:1] + "***" + s[-1:]
    return s[:keep] + "***" + s[-keep:]


def _is_placeholder(val: str) -> bool:
    if not val or not str(val).strip():
        return True
    v = str(val).strip().upper()
    placeholders = (
        "YOUR_", "CHANGE_ME", "TODO", "XXX", "PLACEHOLDER",
        "APPID", "APPSECRET", "请填写", "示例",
    )
    return any(p in v for p in placeholders) or v in ("APP_ID", "APP_SECRET", "SECRET")


def _load_local_wechat_file() -> dict:
    """读取 gitignore 的独立本地凭证文件（优先于 config.yaml 内嵌段以外的补充）。"""
    for name in ("config.wechat.local.yaml", "config.wechat.local.yml"):
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict) and "wechat" in data and isinstance(data["wechat"], dict):
                return data["wechat"]
            if isinstance(data, dict):
                return data
        except Exception as ex:
            op_logger.log("wechat_publisher", f"读取 {name} 失败: {ex}", level="WARN")
    return {}


def get_wechat_credentials() -> dict:
    """
    合并凭证（优先级：环境变量 > config.wechat.local.yaml > config.yaml wechat 段）
    """
    cfg_section: dict = {}
    try:
        cfg_section = dict(load_config().get("wechat") or {})
    except Exception:
        cfg_section = {}
    local = _load_local_wechat_file()
    env_map = {
        "app_id": os.environ.get("WECHAT_APP_ID", ""),
        "app_secret": os.environ.get("WECHAT_APP_SECRET", ""),
        "thumb_media_id": os.environ.get("WECHAT_THUMB_MEDIA_ID", ""),
        "author": os.environ.get("WECHAT_AUTHOR", ""),
        "content_source_url": os.environ.get("WECHAT_CONTENT_SOURCE_URL", ""),
        "cover_image": os.environ.get("WECHAT_COVER_IMAGE", ""),
    }
    creds: dict[str, Any] = {}
    for key in ("app_id", "app_secret", "thumb_media_id", "author",
                "content_source_url", "cover_image"):
        val = (env_map.get(key) or "").strip()
        if not val:
            val = str(local.get(key) or "").strip()
        if not val:
            val = str(cfg_section.get(key) or "").strip()
        creds[key] = val
    if "enabled" in os.environ:
        creds["enabled"] = os.environ.get("WECHAT_ENABLED", "").lower() in ("1", "true", "yes")
    elif "enabled" in local:
        creds["enabled"] = bool(local.get("enabled"))
    else:
        creds["enabled"] = bool(cfg_section.get("enabled", True))
    try:
        creds["timeout"] = int(
            os.environ.get("WECHAT_TIMEOUT")
            or local.get("timeout")
            or cfg_section.get("timeout")
            or 20
        )
    except (TypeError, ValueError):
        creds["timeout"] = 20
    return creds


def credentials_configured(creds: Optional[dict] = None) -> bool:
    creds = creds or get_wechat_credentials()
    app_id = creds.get("app_id") or ""
    secret = creds.get("app_secret") or ""
    return bool(app_id and secret and not _is_placeholder(app_id) and not _is_placeholder(secret))


def status_summary() -> dict:
    """供 UI / health：不泄露完整密钥。"""
    creds = get_wechat_credentials()
    configured = credentials_configured(creds)
    local_file = any(
        os.path.isfile(os.path.join(ROOT, n))
        for n in ("config.wechat.local.yaml", "config.wechat.local.yml")
    )
    return {
        "configured": configured,
        "app_id_masked": _mask(creds.get("app_id") or "") if configured else "",
        "has_thumb_media_id": bool(creds.get("thumb_media_id") and not _is_placeholder(creds.get("thumb_media_id") or "")),
        "has_cover_image_path": bool(creds.get("cover_image") and os.path.isfile(creds.get("cover_image") or "")),
        "local_file_present": local_file,
        "hint": (
            "已配置 AppID/AppSecret，可推送草稿"
            if configured else
            "未配置公众号凭证 — 请设 WECHAT_APP_ID/WECHAT_APP_SECRET 或填写 config.wechat.local.yaml（勿粘贴到聊天）"
        ),
        "docs": "docs/WECHAT_PUBLISH.md",
    }


def markdown_to_wechat_html(md: str) -> str:
    """轻量 Markdown → 公众号可用 HTML（无额外依赖）。"""
    if not md:
        return ""
    text = md.replace("\r\n", "\n")
    # fenced code
    parts: list[str] = []
    cursor = 0
    for m in re.finditer(r"```(\w*)\n(.*?)```", text, flags=re.S):
        parts.append(_md_inline_blocks(text[cursor:m.start()]))
        code = html.escape(m.group(2).rstrip("\n"))
        parts.append(f"<pre><code>{code}</code></pre>")
        cursor = m.end()
    parts.append(_md_inline_blocks(text[cursor:]))
    return "\n".join(p for p in parts if p)


def _md_inline_blocks(chunk: str) -> str:
    lines = chunk.split("\n")
    out: list[str] = []
    para: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            body = "<br/>".join(_inline(x) for x in para)
            out.append(f"<p>{body}</p>")
            para = []

    for line in lines:
        s = line.rstrip()
        if not s.strip():
            flush_para()
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", s)
        if hm:
            flush_para()
            level = min(len(hm.group(1)), 3)
            out.append(f"<h{level}>{_inline(hm.group(2))}</h{level}>")
            continue
        if re.match(r"^[-*]\s+", s):
            flush_para()
            out.append(f"<p>· {_inline(re.sub(r'^[-*]\\s+', '', s))}</p>")
            continue
        if re.match(r"^\d+\.\s+", s):
            flush_para()
            out.append(f"<p>{_inline(s)}</p>")
            continue
        para.append(s)
    flush_para()
    return "\n".join(out)


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def _http_get_json(url: str, timeout: int = 20) -> dict:
    req = urlrequest.Request(url, method="GET")
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict, timeout: int = 20) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _explain_errcode(errcode: Any, errmsg: str = "") -> str:
    try:
        code = int(errcode)
    except (TypeError, ValueError):
        return errmsg or str(errcode)
    hint = ERRCODE_HINTS.get(code)
    base = f"errcode={code}"
    if errmsg:
        base += f" errmsg={errmsg}"
    if hint:
        return f"{hint}（{base}）"
    # IP whitelist often embeds IP in errmsg
    if "ip" in (errmsg or "").lower() or "whitelist" in (errmsg or "").lower():
        return f"疑似 IP 白名单限制：{errmsg or base}"
    return base


def get_access_token(creds: Optional[dict] = None, force: bool = False) -> dict:
    """返回 {ok, access_token?, error?, expires_in?}，不打印 secret。"""
    creds = creds or get_wechat_credentials()
    if not credentials_configured(creds):
        return {
            "ok": False,
            "status": "skipped",
            "reason": "未配置公众号凭证",
            "hint": status_summary()["hint"],
        }
    app_id = creds["app_id"]
    now = time.time()
    if (
        not force
        and _token_cache.get("token")
        and _token_cache.get("app_id") == app_id
        and now < float(_token_cache.get("expires_at") or 0) - 60
    ):
        return {"ok": True, "access_token": _token_cache["token"], "cached": True}

    from urllib.parse import quote
    url = (
        f"{TOKEN_URL}?grant_type=client_credential"
        f"&appid={quote(app_id)}"
        f"&secret={quote(creds['app_secret'])}"
    )
    try:
        data = _http_get_json(url, timeout=int(creds.get("timeout") or 20))
    except urlerror.HTTPError as ex:
        body = ex.read().decode("utf-8", errors="replace") if ex.fp else ""
        op_logger.log("wechat_publisher", f"token HTTPError {ex.code}", level="ERROR")
        return {"ok": False, "status": "failed", "error": f"获取 access_token HTTP {ex.code}: {body[:200]}"}
    except Exception as ex:
        op_logger.log("wechat_publisher", f"token 请求失败: {ex}", level="ERROR")
        return {"ok": False, "status": "failed", "error": f"获取 access_token 失败: {ex}"}

    if data.get("access_token"):
        expires = int(data.get("expires_in") or 7200)
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + expires
        _token_cache["app_id"] = app_id
        op_logger.log("wechat_publisher", f"access_token 获取成功 app_id={_mask(app_id)}")
        return {"ok": True, "access_token": data["access_token"], "expires_in": expires, "cached": False}

    err = _explain_errcode(data.get("errcode"), data.get("errmsg") or "")
    op_logger.log("wechat_publisher", f"token 失败: {err}", level="ERROR")
    return {
        "ok": False,
        "status": "failed",
        "error": f"获取 access_token 失败: {err}",
        "errcode": data.get("errcode"),
    }


def upload_permanent_image(access_token: str, image_path: str, timeout: int = 30) -> dict:
    """上传永久图片素材，返回 media_id（封面用）。"""
    if not os.path.isfile(image_path):
        return {"ok": False, "error": f"封面图片不存在: {image_path}"}
    import requests
    url = f"{MATERIAL_ADD_URL}?access_token={access_token}&type=image"
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(url, files={"media": f}, timeout=timeout)
        data = resp.json()
    except Exception as ex:
        return {"ok": False, "error": f"上传封面失败: {ex}"}
    if data.get("media_id"):
        return {"ok": True, "media_id": data["media_id"], "url": data.get("url")}
    return {
        "ok": False,
        "error": _explain_errcode(data.get("errcode"), data.get("errmsg") or "上传封面失败"),
        "errcode": data.get("errcode"),
    }


def resolve_thumb_media_id(access_token: str, creds: dict) -> dict:
    thumb = (creds.get("thumb_media_id") or "").strip()
    if thumb and not _is_placeholder(thumb):
        return {"ok": True, "thumb_media_id": thumb, "source": "config"}
    cover = (creds.get("cover_image") or "").strip()
    if cover:
        up = upload_permanent_image(access_token, cover, timeout=int(creds.get("timeout") or 30))
        if up.get("ok"):
            return {"ok": True, "thumb_media_id": up["media_id"], "source": "upload"}
        return up
    return {
        "ok": False,
        "status": "failed",
        "error": (
            "缺少封面 thumb_media_id：微信图文草稿要求永久素材封面。"
            "请在公众平台上传封面后填入 WECHAT_THUMB_MEDIA_ID，"
            "或配置 wechat.cover_image 本地图片路径自动上传。"
        ),
    }


def load_article_for_publish(article_id: str) -> dict:
    """按 article_id 解析标题与正文 Markdown。"""
    if not article_id:
        return {"ok": False, "error": "缺少 article_id"}
    file_path = None
    title = article_id
    if os.path.isdir(ARTICLES_DIR):
        for fn in os.listdir(ARTICLES_DIR):
            if fn.startswith(article_id) and fn.endswith(".md"):
                file_path = os.path.join(ARTICLES_DIR, fn)
                break
    if not file_path or not os.path.exists(file_path):
        return {"ok": False, "error": f"稿件文件不存在: {article_id}"}

    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()
    fm = {}
    body = raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, flags=re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip("\"'")
        body = m.group(2)
        title = fm.get("title") or title
    # strip leading H1 duplicate
    body = re.sub(r"^#\s+.+\n+", "", body.lstrip(), count=1)
    return {
        "ok": True,
        "article_id": article_id,
        "title": title[:64],
        "markdown": body,
        "file": file_path,
        "digest": re.sub(r"\s+", " ", body)[:54],
    }


def add_draft(
    title: str,
    content_html: str,
    *,
    author: str = "",
    digest: str = "",
    thumb_media_id: str = "",
    content_source_url: str = "",
    access_token: str = "",
    creds: Optional[dict] = None,
) -> dict:
    creds = creds or get_wechat_credentials()
    if not access_token:
        tok = get_access_token(creds)
        if not tok.get("ok"):
            return tok
        access_token = tok["access_token"]

    article: dict[str, Any] = {
        "title": (title or "未命名")[:64],
        "author": (author or creds.get("author") or "成军台")[:16],
        "digest": (digest or title or "")[:120],
        "content": content_html,
        "content_source_url": content_source_url or creds.get("content_source_url") or "",
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    payload = {"articles": [article]}
    url = f"{DRAFT_ADD_URL}?access_token={access_token}"
    try:
        data = _http_post_json(url, payload, timeout=int(creds.get("timeout") or 20))
    except urlerror.HTTPError as ex:
        body = ex.read().decode("utf-8", errors="replace") if ex.fp else ""
        return {"ok": False, "status": "failed", "error": f"draft/add HTTP {ex.code}: {body[:300]}"}
    except Exception as ex:
        return {"ok": False, "status": "failed", "error": f"draft/add 请求失败: {ex}"}

    if data.get("media_id"):
        return {
            "ok": True,
            "status": "ok",
            "media_id": data["media_id"],
            "tip": "已写入公众号草稿箱，请在公众平台「草稿箱」核对后手动发布（成军台不自动群发）",
        }
    err = _explain_errcode(data.get("errcode"), data.get("errmsg") or "")
    return {
        "ok": False,
        "status": "failed",
        "error": f"draft/add 失败: {err}",
        "errcode": data.get("errcode"),
    }


def publish_article_to_draft(article_id: str) -> dict:
    """主入口：稿件 → 公众号草稿。未配置凭证 → skipped（明确文案，非静默成功）。"""
    creds = get_wechat_credentials()
    if not credentials_configured(creds):
        op_logger.log(
            "publish_wechat",
            f"公众号推送跳过[{article_id}]：未配置公众号凭证",
            level="WARN",
        )
        return {
            "ok": False,
            "status": "skipped",
            "reason": "未配置公众号凭证",
            "hint": (
                "请在本机设置环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET，"
                "或复制 config.wechat.local.yaml.example 为 config.wechat.local.yaml 自行填写（勿粘贴密钥到聊天）。"
                "详见 docs/WECHAT_PUBLISH.md"
            ),
            "article_id": article_id,
        }

    art = load_article_for_publish(article_id)
    if not art.get("ok"):
        return {"ok": False, "status": "failed", "error": art.get("error"), "article_id": article_id}

    tok = get_access_token(creds)
    if not tok.get("ok"):
        return {**tok, "article_id": article_id}

    thumb = resolve_thumb_media_id(tok["access_token"], creds)
    if not thumb.get("ok"):
        op_logger.log("publish_wechat", f"封面缺失[{article_id}]: {thumb.get('error')}", level="ERROR")
        return {**thumb, "article_id": article_id, "status": thumb.get("status") or "failed"}

    content_html = markdown_to_wechat_html(art["markdown"])
    if len(content_html) < 10:
        return {"ok": False, "status": "failed", "error": "正文过短或转换失败", "article_id": article_id}

    result = add_draft(
        art["title"],
        content_html,
        author=creds.get("author") or "成军台",
        digest=art.get("digest") or art["title"],
        thumb_media_id=thumb["thumb_media_id"],
        access_token=tok["access_token"],
        creds=creds,
    )
    result["article_id"] = article_id
    result["title"] = art["title"]
    result["thumb_source"] = thumb.get("source")
    if result.get("ok"):
        op_logger.log(
            "publish_wechat",
            f"草稿已创建[{article_id}] media_id={result.get('media_id')}",
        )
    else:
        op_logger.log(
            "publish_wechat",
            f"草稿失败[{article_id}]: {result.get('error')}",
            level="ERROR",
        )
    return result
