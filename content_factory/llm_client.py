# -*- coding: utf-8 -*-
"""
LLM 统一客户端 —— OpenAI 兼容多 provider 级联 fallback
按 config.yaml 中 llm.providers 顺序逐个尝试，任一成功即返回其 content；
全部失败才返回调用方传入的 fallback（保证流水线可跑通）。

兼容两种配置形态：
  · 新格式：llm.providers 列表（推荐，支持多级降级）
  · 旧格式：llm.api_base / api_key / model 扁平字段（向后兼容）

成军台增强：
  · 支持环境变量覆盖 api_key（XIRANG / TOKENHUB / TOKEN_PLAN / SENSENOVA / DASHSCOPE / BIREN）
  · provider_status() 供 UI 展示模型徽章
  · 占位 Key（YOUR_ / CHANGE_ / 空）视为未配置，避免静默假成功
  · 指数退避重试 + 连接池复用 + JSON 解析鲁棒性 + 单 provider 熔断保护
"""

import os
import time
import json
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import op_logger
from config_loader import load_config

_LAST_SUCCESS = {"name": None, "model": None, "api_base": None}
_COUNTERS = {"ok": 0, "fail": 0}
# 进程内累计 token（OpenAI 兼容 usage；网关未返回时为 0）
_TOKEN_USAGE = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "calls_with_usage": 0,
    "last": {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model": None,
        "name": None,
    },
}

# ---------- 连接池 + 熔断 + 重试状态 ----------
_SESSION_LOCK = threading.Lock()
_HTTP_SESSION = None
# 单 provider 熔断：连续失败阈值、冷却秒数
_CIRCUIT_BREAKER = {}  # name -> {"fail_count": int, "open_until": float(ts)}
_CB_FAIL_THRESHOLD = 3   # 连续失败 N 次后熔断
_CB_COOLDOWN_SEC = 60    # 熔断冷却 60s


def _get_http_session() -> requests.Session:
    """带连接池与重试适配器的全局 Session（线程安全懒加载）。"""
    global _HTTP_SESSION
    if _HTTP_SESSION is not None:
        return _HTTP_SESSION
    with _SESSION_LOCK:
        if _HTTP_SESSION is not None:
            return _HTTP_SESSION
        s = requests.Session()
        retry = Retry(
            total=0,  # 我们自己做指数退避重试，这里让 Adapter 不自动重试
            connect=0,
            read=0,
            redirect=0,
            backoff_factor=0,
        )
        adapter = HTTPAdapter(
            pool_connections=20,
            pool_maxsize=50,
            max_retries=retry,
            pool_block=False,
        )
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        # 防止进程挂死：单个连接最长保持
        s.headers.update({"Connection": "keep-alive"})
        _HTTP_SESSION = s
        return _HTTP_SESSION


def _cb_is_open(name: str) -> bool:
    """检查 provider 是否处于熔断冷却期。"""
    cb = _CIRCUIT_BREAKER.get(name) or {}
    open_until = cb.get("open_until") or 0
    if open_until and time.time() < open_until:
        return True
    return False


def _cb_record_fail(name: str):
    """记录一次失败；达到阈值则打开熔断。"""
    cb = _CIRCUIT_BREAKER.setdefault(name, {"fail_count": 0, "open_until": 0})
    cb["fail_count"] = int(cb.get("fail_count") or 0) + 1
    if cb["fail_count"] >= _CB_FAIL_THRESHOLD:
        cb["open_until"] = time.time() + _CB_COOLDOWN_SEC
        op_logger.log(
            "llm_client",
            f"熔断开启[{name}] 连续失败{cb['fail_count']}次，冷却{_CB_COOLDOWN_SEC}s",
            level="WARN",
        )


def _cb_record_ok(name: str):
    """调用成功：清零失败计数、关闭熔断。"""
    cb = _CIRCUIT_BREAKER.get(name)
    if not cb:
        return
    if cb.get("fail_count") or cb.get("open_until"):
        cb["fail_count"] = 0
        cb["open_until"] = 0
        op_logger.log("llm_client", f"熔断恢复[{name}]", level="INFO")

_ENV_KEY_MAP = {
    "息壤": "XIRANG_API_KEY",
    "星辰": "TOKENHUB_API_KEY",
    "TokenHub": "TOKENHUB_API_KEY",
    "SenseNova": "SENSENOVA_API_KEY",
    "商汤": "SENSENOVA_API_KEY",
    "TokenPlan": "TOKEN_PLAN_API_KEY",
    "token-plan": "TOKEN_PLAN_API_KEY",
    "tokenplan": "TOKEN_PLAN_API_KEY",
    "百炼": "DASHSCOPE_API_KEY",
    "DashScope": "DASHSCOPE_API_KEY",
    "壁韧": "BIREN_API_KEY",
    "biren": "BIREN_API_KEY",
}


def _is_placeholder_key(key: str) -> bool:
    if not key or not str(key).strip():
        return True
    k = str(key).strip().upper()
    bad = ("YOUR_", "CHANGE_", "TODO", "PLACEHOLDER", "XXX", "SK-XXXX")
    return any(b in k for b in bad)


def _is_xirang_provider(name: str) -> bool:
    n = (name or "").lower()
    return "息壤" in (name or "") or "xirang" in n or "wishub" in n


def _resolve_api_key(provider: dict) -> str:
    key = provider.get("api_key") or ""
    name = provider.get("name") or ""
    # 显式 env 字段优先
    env_name = provider.get("api_key_env")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name].strip()
    for hint, env in _ENV_KEY_MAP.items():
        if hint.lower() in name.lower() and os.environ.get(env):
            return os.environ[env].strip()
    # 通用环境变量
    for env in ("XIRANG_API_KEY", "TOKENHUB_API_KEY", "TELEAI_API_KEY"):
        if (
            "息壤" in name
            or "星辰" in name
            or "TokenHub" in name
            or "xirang" in name.lower()
        ):
            if os.environ.get(env):
                return os.environ[env].strip()
    if _is_placeholder_key(key):
        return ""
    return str(key).strip()


def _resolve_api_base(provider: dict) -> str:
    env_name = provider.get("api_base_env")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name].strip().rstrip("/")
    name = provider.get("name") or ""
    if _is_xirang_provider(name) and os.environ.get("XIRANG_BASE_URL"):
        return os.environ["XIRANG_BASE_URL"].strip().rstrip("/")
    base = (provider.get("api_base") or "").strip().rstrip("/")
    return base


def _resolve_model(provider: dict) -> str:
    env_name = provider.get("model_env")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name].strip()
    name = provider.get("name") or ""
    if _is_xirang_provider(name) and os.environ.get("XIRANG_MODEL"):
        return os.environ["XIRANG_MODEL"].strip()
    model = (provider.get("model") or "").strip()
    if _is_placeholder_key(model):
        return ""
    return model


def _get_providers() -> list:
    """读取当前生效的 provider 列表；Llm 未启用或未配置时返回 []"""
    cfg = load_config().get("llm", {})
    if not cfg.get("enabled", False):
        return []

    # 新格式：显式 providers 列表
    providers_cfg = cfg.get("providers")
    if isinstance(providers_cfg, list) and providers_cfg:
        out = []
        for p in providers_cfg:
            if not p.get("enabled", True):
                continue
            api_key = _resolve_api_key(p)
            api_base = _resolve_api_base(p)
            model = _resolve_model(p)
            if api_base and api_key and model:
                item = dict(p)
                item["api_key"] = api_key
                item["api_base"] = api_base
                item["model"] = model
                item.setdefault("name", api_base or "?")
                out.append(item)
        return out

    # 旧格式：扁平单 provider
    if (
        cfg.get("api_base")
        and cfg.get("api_key")
        and not _is_placeholder_key(cfg.get("api_key"))
    ):
        return [
            {
                "name": "default",
                "api_base": cfg["api_base"],
                "api_key": cfg["api_key"],
                "model": cfg.get("model", "gpt-4o-mini"),
                "timeout": cfg.get("timeout", 60),
            }
        ]
    return []


def is_llm_enabled() -> bool:
    """是否有任意一个可用 provider"""
    return len(_get_providers()) > 0


def provider_status() -> dict:
    """供成军台 UI 展示的模型徽章信息"""
    providers = _get_providers()
    enabled = bool(providers)
    hint = ""
    if not enabled:
        hint = (
            "未配置可用 LLM。参赛 primary：主办方发放后设 XIRANG_API_KEY / TOKENHUB_API_KEY；"
            "等 Token 期间可用 TOKEN_PLAN_API_KEY / SENSENOVA_API_KEY（interim，亦可写入 gitignore 的 config.yaml）。"
            "重启 Web 后生效。禁止静默 mock；结构验证：python tests/test_campaign_core.py；"
            "双路径：docs/CTYUN_TRIAL.md"
        )
    usage = dict(_TOKEN_USAGE)
    usage["last"] = dict(_TOKEN_USAGE.get("last") or {})
    return {
        "enabled": enabled,
        "providers": [
            {
                "name": p.get("name"),
                "model": p.get("model"),
                "api_base": p.get("api_base"),
            }
            for p in providers
        ],
        "active_name": _LAST_SUCCESS.get("name")
        or (providers[0]["name"] if providers else None),
        "active_model": _LAST_SUCCESS.get("model")
        or (providers[0]["model"] if providers else None),
        "ok": _COUNTERS["ok"],
        "fail": _COUNTERS["fail"],
        "token_usage": usage,
        "require_real_llm": bool(
            load_config().get("llm", {}).get("require_real_llm", True)
        ),
        "hint": hint,
    }


def token_usage() -> dict:
    """进程内累计 token 消耗快照。"""
    out = dict(_TOKEN_USAGE)
    out["last"] = dict(_TOKEN_USAGE.get("last") or {})
    return out


def _record_usage(payload: dict, name: str, model: str) -> dict:
    """从 chat/completions 响应提取 usage 并累加。"""
    u = (payload or {}).get("usage") or {}
    pt = int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
    ct = int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    tt = int(u.get("total_tokens") or (pt + ct) or 0)
    last = {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
        "model": model,
        "name": name,
    }
    _TOKEN_USAGE["last"] = last
    if tt or pt or ct:
        _TOKEN_USAGE["prompt_tokens"] += pt
        _TOKEN_USAGE["completion_tokens"] += ct
        _TOKEN_USAGE["total_tokens"] += tt
        _TOKEN_USAGE["calls_with_usage"] += 1
    return last


def bump_ok():
    _COUNTERS["ok"] += 1


def bump_fail():
    _COUNTERS["fail"] += 1


def last_success() -> dict:
    return dict(_LAST_SUCCESS)


def _safe_parse_json_response(r: requests.Response, name: str, model: str) -> dict:
    """安全解析 chat/completions 响应 JSON，防御空内容、非法 JSON、截断载荷。"""
    if not r or not getattr(r, "content", None):
        return {}
    raw = r.content
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = ""
    else:
        text = str(raw or "")
    if not text.strip():
        return {}
    # 部分网关可能在 JSON 前返回前缀（BOM/文本），尝试找第一个 { 到最后一个 }
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception as ex2:
                op_logger.log(
                    "llm_client",
                    f"JSON二次解析失败[{name}/{model}]: {ex2} snippet={text[:120]!r}",
                    level="WARN",
                )
        return {}


def _call_once(
    session: requests.Session,
    p: dict,
    req_body: dict,
    timeout: int,
) -> tuple[int, dict, str, str]:
    """单次 HTTP 调用，返回 (status_code, payload_or_empty, content_or_empty, error_msg)。"""
    name = p.get("name", "?")
    model = p.get("model", "?")
    url = f"{p['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {p['api_key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        r = session.post(url, headers=headers, json=req_body, timeout=timeout)
        status = int(getattr(r, "status_code", 0) or 0)
        if status == 200:
            payload = _safe_parse_json_response(r, name, model)
            choices = payload.get("choices") if isinstance(payload, dict) else None
            choice0 = (choices or [{}])[0] if isinstance(choices, list) and choices else {}
            msg = choice0.get("message") if isinstance(choice0, dict) else {}
            content = msg.get("content") if isinstance(msg, dict) else ""
            content = "" if content is None else str(content)
            return status, payload, content, ""
        # 非 200：尝试截取错误信息
        err_snippet = ""
        try:
            t = r.text if hasattr(r, "text") else ""
            err_snippet = (t or "")[:300]
        except Exception:
            err_snippet = ""
        return status, {}, "", err_snippet or f"HTTP {status}"
    except requests.exceptions.Timeout as ex:
        return 0, {}, "", f"timeout: {ex}"
    except requests.exceptions.ConnectionError as ex:
        return 0, {}, "", f"connection_error: {ex}"
    except Exception as ex:
        return 0, {}, "", f"exception: {type(ex).__name__}: {ex}"


def call_llm(
    prompt: str,
    fallback: str = "",
    max_tokens: int = None,
    temperature: float = None,
    timeout: int = None,
    reverse_order: bool = False,
    thinking: object = None,
    system_prompt: str = None,
    retries_per_provider: int = None,
) -> str:
    """
    级联调用 LLM（鲁棒增强版）。
    - 逐个尝试 provider，HTTP 200 且 content 非空即返回（content 已 strip）。
    - 每个 provider 内部做指数退避重试（默认 2 次重试 = 最多 3 次尝试）。
    - 熔断保护：连续失败达阈值后冷却 60s 跳过该 provider。
    - 全部失败返回 fallback。
    - reverse_order=True 时反转 provider 顺序（最强模型优先），适用于 NL2SQL 等
      对推理质量要求高、可容忍较长延迟的场景。
    - thinking: None=使用 config 配置；True=强制开启推理模型思考（适用于 NL2SQL 等
      复杂推理任务）；False=强制关闭。
    - system_prompt: 若提供，则发送 system+user 双消息。
    """
    try:
        cfg = load_config().get("llm", {})
    except Exception:
        cfg = {}
    providers = _get_providers()
    if not providers:
        return fallback

    if reverse_order:
        providers = list(reversed(providers))

    temp = temperature if temperature is not None else cfg.get("temperature", 0.7)
    mt = max_tokens if max_tokens is not None else cfg.get("max_tokens", 4096)
    think = cfg.get("enable_thinking", None)
    if thinking is not None:
        think = thinking

    retries = int(
        retries_per_provider
        if retries_per_provider is not None
        else cfg.get("retries_per_provider", 2)
    )
    if retries < 0:
        retries = 0

    if system_prompt:
        messages = [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": prompt or ""},
        ]
    else:
        messages = [{"role": "user", "content": prompt or ""}]

    session = _get_http_session()
    attempted_any = False

    for p in providers:
        name = p.get("name", "?")
        model = p.get("model", "?")
        # 熔断跳过
        if _cb_is_open(name):
            op_logger.log(
                "llm_client",
                f"跳过熔断中的provider[{name}]",
                level="INFO",
            )
            continue
        tmo = timeout if timeout is not None else p.get("timeout", 60)
        req_body = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": mt,
        }
        if think is not None:
            req_body["enable_thinking"] = think

        success_on_provider = False
        last_err = ""
        for attempt in range(retries + 1):
            attempted_any = True
            if attempt > 0:
                # 指数退避：1s, 2s, 4s... 封顶 8s
                backoff = min(2 ** (attempt - 1), 8)
                op_logger.log(
                    "llm_client",
                    f"重试[{name}/{model}] 第{attempt}次，退避{backoff}s",
                    level="INFO",
                )
                time.sleep(backoff)
            status, payload, content, err = _call_once(session, p, req_body, tmo)
            if status == 200 and content and content.strip():
                usage_last = _record_usage(
                    payload if isinstance(payload, dict) else {}, name, model
                )
                _LAST_SUCCESS.update(
                    {"name": name, "model": model, "api_base": p.get("api_base")}
                )
                _COUNTERS["ok"] += 1
                _cb_record_ok(name)
                tok = usage_last.get("total_tokens") or 0
                op_logger.log(
                    "llm_client",
                    f"LLM调用成功[{name}/{model}] tokens={tok}",
                    level="INFO",
                )
                try:
                    return str(content).strip()
                except Exception:
                    return fallback or ""
            # 失败：记录
            if status == 200:
                reason = "空content"
            else:
                reason = f"HTTP{status}" if status else (err or "unknown")
            last_err = reason
            op_logger.log(
                "llm_client",
                f"LLM失败[{name}/{model}] 尝试{attempt+1}/{retries+1}: {reason}",
                level="WARN",
            )
        # 该 provider 所有尝试均失败：熔断计数
        _cb_record_fail(name)

    _COUNTERS["fail"] += 1
    if attempted_any:
        op_logger.log(
            "llm_client", "所有 provider 均失败，降级 fallback", level="WARN"
        )
    else:
        op_logger.log(
            "llm_client", "所有 provider 均处于熔断中，降级 fallback", level="WARN"
        )
    return fallback


if __name__ == "__main__":
    # 自检：打印生效的 provider 列表并做一次最小调用
    ps = _get_providers()
    print(f"生效 provider 数: {len(ps)}")
    for p in ps:
        print(f"  - {p.get('name')}: {p['model']} @ {p['api_base']}")
    if ps:
        ans = call_llm("用一句话说明什么是MCP协议。", max_tokens=2000)
        print("\nLLM 回复:", ans[:200])
