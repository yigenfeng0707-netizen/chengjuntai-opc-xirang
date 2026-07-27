# -*- coding: utf-8 -*-
"""
模块11：用户权限分级
1. 角色：超级管理员、运维操作员、只读访客
2. 权限隔离：访客仅查看；操作员可执行任务不能改核心配置；管理员拥有全部权限
3. 用户信息持久化 users.json
4. Web 面板、MCP 接口同步鉴权
5. 支持新增/禁用账户、修改密码
"""
import os
import json
import datetime
from config_loader import ROOT

USERS_FILE = os.path.join(ROOT, "users.json")


def _load():
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def authenticate(username: str, password: str) -> dict:
    """鉴权，返回用户信息(含权限)或 None"""
    data = _load()
    for u in data["users"]:
        if u["username"] == username and u["password"] == password and u.get("enabled", True):
            roles = data.get("roles", {})
            return {"username": u["username"], "role": u["role"],
                    "permissions": roles.get(u["role"], [])}
    return None


def check_permission(user: dict, action: str) -> bool:
    """校验权限，* 表示全部权限"""
    if not user:
        return False
    perms = user.get("permissions", [])
    return "*" in perms or action in perms


def list_users() -> list:
    data = _load()
    return [{"username": u["username"], "role": u["role"], "enabled": u.get("enabled", True),
             "created_at": u.get("created_at")} for u in data["users"]]


def list_roles() -> dict:
    return _load().get("roles", {})


def add_user(username: str, password: str, role: str) -> bool:
    data = _load()
    if any(u["username"] == username for u in data["users"]):
        return False
    data["users"].append({"username": username, "password": password, "role": role,
                          "enabled": True, "created_at": datetime.date.today().isoformat()})
    _save(data)
    return True


def disable_user(username: str) -> bool:
    data = _load()
    for u in data["users"]:
        if u["username"] == username:
            u["enabled"] = False
            _save(data)
            return True
    return False


def change_password(username: str, new_password: str) -> bool:
    data = _load()
    for u in data["users"]:
        if u["username"] == username:
            u["password"] = new_password
            _save(data)
            return True
    return False
