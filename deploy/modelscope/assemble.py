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
# config.yaml 含真实 Key 且已 gitignore（本地有/仓库无）——一律排除，
# 部署配置统一由 deploy/modelscope/config.deploy.yaml 提供（可公开，Key 走环境变量）
EXCLUDE_FILES = {".env", ".DS_Store", "config.yaml", "config.wechat.local.yaml"}


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


def place_config(dst_path):
    """用部署专用脱敏配置生成 content_factory/config.yaml（0.0.0.0:7860，Key 占位）"""
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.deploy.yaml")
    with open(src, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    with open(dst_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def place_users(dst_path):
    """部署内置账号表（users.json 被 gitignore，仓库不含；
    users.deploy.json 为随仓库提交的部署副本，仅 scrypt 哈希无明文）"""
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.deploy.json")
    if os.path.isfile(src):
        shutil.copy2(src, dst_path)


def copy_support_modules():
    """拷贝仓库根的支撑模块到 studio 根（= 容器内 REPO_ROOT=/app）。
    content_factory 多处 sys.path 插入上级目录后 import db / fetch_real_data，
    缺失会导致启动崩溃（DeployFailed）。seed_demo_db.py 供构建期初始化演示库。
    """
    for name in ("db.py", "fetch_real_data.py", "seed_demo_db.py"):
        src = os.path.join(ROOT, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(STUDIO, name))


def main():
    if os.path.exists(STUDIO):
        shutil.rmtree(STUDIO)
    os.makedirs(STUDIO)
    copy_tree(CF, os.path.join(STUDIO, "content_factory"))
    place_config(os.path.join(STUDIO, "content_factory", "config.yaml"))
    place_users(os.path.join(STUDIO, "content_factory", "users.json"))
    copy_support_modules()
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copy2(os.path.join(here, "Dockerfile"), os.path.join(STUDIO, "Dockerfile"))
    shutil.copy2(os.path.join(here, "ms_deploy.json"), os.path.join(STUDIO, "ms_deploy.json"))
    print("studio/ assembled:", sorted(os.listdir(STUDIO)))


if __name__ == "__main__":
    main()
