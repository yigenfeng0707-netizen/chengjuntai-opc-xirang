# -*- coding: utf-8 -*-
"""组装魔搭创空间推送目录 studio/（CI 中在仓库根执行）

- 拷贝 content_factory 整目录（排除缓存/日志/本机环境文件）
- 脱敏 config.yaml：真实 api_key → 占位符（运行时由魔搭空间环境变量注入真实 Key，
  llm_client._resolve_key 优先读 api_key_env 环境变量）
- 覆写 web_host=0.0.0.0 / web_port=7860（魔搭平台硬性要求）
- 拷贝 Dockerfile / ms_deploy.json
"""
import os
import shutil

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CF = os.path.join(ROOT, "content_factory")
STUDIO = os.path.join(ROOT, "studio")

EXCLUDE_DIRS = {"__pycache__", ".git", ".trae", "node_modules", "logs"}
EXCLUDE_FILES = {".env", ".DS_Store"}


def copy_tree(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s = os.path.join(src, name)
        if os.path.isdir(s):
            if name in EXCLUDE_DIRS:
                continue
            copy_tree(s, os.path.join(dst, name))
        else:
            if name in EXCLUDE_FILES or name.endswith(".pyc"):
                continue
            shutil.copy2(s, os.path.join(dst, name))


def sanitize_config(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # 端口/监听：魔搭硬性要求 7860
    cfg["web_host"] = "0.0.0.0"
    cfg["web_port"] = 7860
    # LLM Key 脱敏：真实 Key 走魔搭空间环境变量（XIRANG_API_KEY 等）
    providers = (cfg.get("llm") or {}).get("providers") or []
    for p in providers:
        if p.get("api_key"):
            p["api_key"] = "DEPLOY-PLACEHOLDER-USE-ENV"
    # 本机敏感字段清空
    for k in ("smtp_user", "smtp_password"):
        if cfg.get(k):
            cfg[k] = ""
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def main():
    if os.path.exists(STUDIO):
        shutil.rmtree(STUDIO)
    os.makedirs(STUDIO)
    copy_tree(CF, os.path.join(STUDIO, "content_factory"))
    sanitize_config(os.path.join(STUDIO, "content_factory", "config.yaml"))
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copy2(os.path.join(here, "Dockerfile"), os.path.join(STUDIO, "Dockerfile"))
    shutil.copy2(os.path.join(here, "ms_deploy.json"), os.path.join(STUDIO, "ms_deploy.json"))
    print("studio/ assembled:", sorted(os.listdir(STUDIO)))


if __name__ == "__main__":
    main()
