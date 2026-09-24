# -*- coding: utf-8 -*-
"""
公共配置加载模块（鲁棒增强版）
- 读取 config.yaml 并完成 ${var} 变量替换
- 统一提供路径常量，自动适配 Windows 正反斜杠
- 供所有业务模块 import 使用

鲁棒增强：
  · 配置文件缺失 / 格式损坏 / 磁盘 IO 失败 → 返回默认空配置，不崩溃
  · 变量替换异常 → 安全回退为原始 dict
  · 目录创建失败 → 静默，不抛出
  · 读取线程安全（线程锁 + 缓存）
"""
import os
import re
import threading
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))

# 产物目录重定向，**仅无 Key 回归测试设置**（生产/演示勿设）：不重定向的话，跑一次测试就污染
# data/、articles/ 里被 git 跟踪的演示种子，以及 gitignored 但会累积 mock 文档的检索索引。
WRITE_ROOT = os.environ.get("CHENGJUNTAI_WRITE_ROOT") or ROOT

ARTICLES_DIR = os.path.join(WRITE_ROOT, "articles")
EXPORT_PDF_DIR = os.path.join(WRITE_ROOT, "export_pdf")
LOGS_DIR = os.path.join(WRITE_ROOT, "logs")
DATA_DIR = os.path.join(WRITE_ROOT, "data")
VECTOR_DB_DIR = os.path.join(WRITE_ROOT, "vector_db")
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")
TEMPLATES_DIR = os.path.join(ROOT, "templates")

# 目录创建：失败不抛出
for _d in [ARTICLES_DIR, EXPORT_PDF_DIR, LOGS_DIR, DATA_DIR, VECTOR_DB_DIR, KNOWLEDGE_DIR, TEMPLATES_DIR]:
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception:
        try:
            # 兜底：尝试用默认权限再次创建
            os.makedirs(_d, mode=0o755, exist_ok=True)
        except Exception:
            pass

_CFG_CACHE = None
_CFG_LOCK = threading.RLock()
_DEFAULT_CFG = {
    "product_name": "成军台",
    "product_slogan": "一人成军 · OPC OS on 息壤",
    "web_host": "127.0.0.1",
    "web_port": 8090,
    "llm": {"enabled": False, "providers": [], "require_real_llm": False},
    "demo_mode": {"allow_mock_llm": True, "auto_approve_gate": False},
    "article": {"target_min_words": 800, "target_max_words": 4000},
    "log_roll_days": 30,
}


def _replace_vars(cfg: dict) -> dict:
    """递归替换 ${key} 变量；异常则原样返回（不崩溃）。"""
    if not isinstance(cfg, dict):
        return cfg or {}
    try:
        raw = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
        if not isinstance(raw, str):
            return cfg
    except Exception:
        return cfg
    try:
        top = {k: v for k, v in cfg.items() if isinstance(v, (str, int, float))}
    except Exception:
        top = {}

    def repl(m):
        try:
            key = m.group(1)
            return str(top.get(key, m.group(0)))
        except Exception:
            return m.group(0)

    try:
        raw = re.sub(r"\$\{(\w+)\}", repl, raw)
    except Exception:
        return cfg
    try:
        result = yaml.safe_load(raw)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return cfg


import json as _json


def json_dumps(obj):
    try:
        return _json.dumps(obj, ensure_ascii=False)
    except Exception:
        try:
            return _json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            return "{}"


def _load_config_from_disk(path: str) -> dict:
    """从磁盘读取配置，IO/解析失败返回 {}。"""
    try:
        if not os.path.exists(path):
            # config.yaml.example 兼容
            example = path + ".example"
            if os.path.exists(example):
                path = example
            else:
                return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            return {}
        return data
    except FileNotFoundError:
        return {}
    except yaml.YAMLError:
        # 配置损坏：记录但不抛（此处无法引 op_logger，避免循环 import）
        try:
            crash = os.path.join(LOGS_DIR, "config_corrupt.log")
            with open(crash, "a", encoding="utf-8") as f:
                import datetime as _dt
                f.write(f"{_dt.datetime.now().isoformat()} config.yaml 格式损坏，使用默认配置\n")
        except Exception:
            pass
        return {}
    except Exception:
        return {}


def load_config(force: bool = False) -> dict:
    """加载配置（线程安全 + 异常安全）。永远返回 dict，不会返回 None 或抛异常。"""
    global _CFG_CACHE
    if not force and _CFG_CACHE is not None and isinstance(_CFG_CACHE, dict):
        return _CFG_CACHE
    with _CFG_LOCK:
        if not force and _CFG_CACHE is not None and isinstance(_CFG_CACHE, dict):
            return _CFG_CACHE
        path = os.path.join(ROOT, "config.yaml")
        raw = _load_config_from_disk(path)
        if not raw:
            # 返回拷贝：避免外部修改污染默认配置
            cfg = dict(_DEFAULT_CFG)
        else:
            # 用默认值补齐缺省字段（浅 merge）
            cfg = dict(_DEFAULT_CFG)
            try:
                cfg.update(raw)
            except Exception:
                cfg = raw if isinstance(raw, dict) else dict(_DEFAULT_CFG)
        try:
            cfg = _replace_vars(cfg)
        except Exception:
            pass
        if not isinstance(cfg, dict):
            cfg = dict(_DEFAULT_CFG)
        _CFG_CACHE = cfg
        return cfg


def safe_get(cfg: dict, key: str, default=None):
    if not isinstance(cfg, dict):
        return default
    return cfg.get(key, default)


def get_llm_settings() -> dict:
    try:
        llm = load_config().get("llm")
        if isinstance(llm, dict):
            return llm
    except Exception:
        pass
    return {"enabled": False, "providers": []}


def ensure_dirs():
    """外部调用确保目录存在（兜底：模块加载时若首次失败，再尝试一次）。"""
    for _d in [ARTICLES_DIR, EXPORT_PDF_DIR, LOGS_DIR, DATA_DIR, VECTOR_DB_DIR, KNOWLEDGE_DIR, TEMPLATES_DIR]:
        try:
            os.makedirs(_d, exist_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    c = load_config()
    print(json_dumps(c, indent=2))
