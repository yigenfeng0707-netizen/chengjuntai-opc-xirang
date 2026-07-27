# -*- coding: utf-8 -*-
"""
公共配置加载模块
- 读取 config.yaml 并完成 ${var} 变量替换
- 统一提供路径常量，自动适配 Windows 正反斜杠
- 供所有业务模块 import 使用
"""
import os
import re
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))

ARTICLES_DIR = os.path.join(ROOT, "articles")
EXPORT_PDF_DIR = os.path.join(ROOT, "export_pdf")
LOGS_DIR = os.path.join(ROOT, "logs")
DATA_DIR = os.path.join(ROOT, "data")
VECTOR_DB_DIR = os.path.join(ROOT, "vector_db")
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")
TEMPLATES_DIR = os.path.join(ROOT, "templates")

for _d in [ARTICLES_DIR, EXPORT_PDF_DIR, LOGS_DIR, DATA_DIR, VECTOR_DB_DIR, KNOWLEDGE_DIR, TEMPLATES_DIR]:
    os.makedirs(_d, exist_ok=True)

_CFG_CACHE = None


def _replace_vars(cfg: dict) -> dict:
    """递归替换 ${key} 变量"""
    raw = json_dumps(cfg) if False else yaml.safe_dump(cfg, allow_unicode=True)
    top = {k: v for k, v in cfg.items() if isinstance(v, (str, int, float))}

    def repl(m):
        key = m.group(1)
        return str(top.get(key, m.group(0)))

    raw = re.sub(r"\$\{(\w+)\}", repl, raw)
    return yaml.safe_load(raw)


import json as _json


def json_dumps(obj):
    return _json.dumps(obj, ensure_ascii=False)


def load_config(force: bool = False) -> dict:
    global _CFG_CACHE
    if _CFG_CACHE is not None and not force:
        return _CFG_CACHE
    path = os.path.join(ROOT, "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg = _replace_vars(cfg)
    _CFG_CACHE = cfg
    return cfg


def safe_get(cfg: dict, key: str, default=None):
    return cfg.get(key, default)


def get_llm_settings() -> dict:
    return load_config().get("llm", {"enabled": False})


def ensure_dirs():
    """外部调用确保目录存在"""
    pass  # 模块加载时已创建


if __name__ == "__main__":
    c = load_config()
    print(json_dumps(c, indent=2))
