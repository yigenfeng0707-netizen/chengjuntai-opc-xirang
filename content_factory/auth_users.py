# -*- coding: utf-8 -*-
"""
模块11：用户权限分级
1. 角色：超级管理员、运维操作员、终端用户、只读访客/评委
2. 权限隔离：访客仅查看；操作员可执行任务；终端用户仅操作自己的战役；管理员拥有全部权限
3. 用户信息持久化 users.json（含邮箱登录、画像、用量计数）
4. Web 面板、MCP 接口同步鉴权
5. 支持注册/新增/启用禁用/改角色/改密

密码策略（P1）：
- 新注册 / 管理端新增 / 改密 → werkzeug 哈希（pbkdf2/scrypt）
- 既有演示账号明文仍可登录；成功登录后惰性升级为哈希（不打断 judge/admin）
"""

import os
import json
import datetime
import threading
from typing import Optional
from config_loader import ROOT

try:
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:  # pragma: no cover - flask 依赖通常已装
    generate_password_hash = None
    check_password_hash = None

USERS_FILE = os.path.join(ROOT, "users.json")
_lock = threading.RLock()

DEFAULT_ROLES = {
    "super_admin": ["*"],
    "operator": [
        "run_task",
        "view",
        "export",
        "queue_control",
        "schedule_control",
        "view_all_campaigns",
    ],
    "user": ["run_task", "view", "export"],
    "guest": ["view", "export"],
    "judge": ["view"],
}

ROLE_ALIASES = {"judge": "guest"}

# werkzeug 哈希前缀；明文不会带这些
_HASH_PREFIXES = ("pbkdf2:", "scrypt:", "argon2:")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _empty_usage() -> dict:
    return {
        "campaigns_started": 0,
        "tasks_done": 0,
        "articles_generated": 0,
        "logins": 0,
        "reports_exported": 0,
    }


def _empty_profile() -> dict:
    return {"tags": [], "segment": "new", "notes": ""}


def _is_hashed(stored: str) -> bool:
    s = stored or ""
    return any(s.startswith(p) for p in _HASH_PREFIXES)


def _hash_password(plain: str) -> str:
    if generate_password_hash is None:
        return plain
    return generate_password_hash(plain)


def _verify_password(stored: str, plain: str) -> bool:
    if not plain and not stored:
        return False
    if _is_hashed(stored):
        if check_password_hash is None:
            return False
        try:
            return bool(check_password_hash(stored, plain))
        except Exception:
            return False
    return stored == plain


def _normalize_user(u: dict) -> dict:
    """补齐旧 users.json 字段，不写盘（由调用方决定是否 save）。"""
    u.setdefault("email", "")
    u.setdefault("display_name", u.get("username", ""))
    u.setdefault("enabled", True)
    u.setdefault("created_at", datetime.date.today().isoformat())
    u.setdefault("last_login_at", None)
    u.setdefault("profile", _empty_profile())
    if "usage" not in u or not isinstance(u["usage"], dict):
        u["usage"] = _empty_usage()
    else:
        for k, v in _empty_usage().items():
            u["usage"].setdefault(k, v)
    role = u.get("role") or "user"
    u["role"] = ROLE_ALIASES.get(role, role)
    return u


def _load() -> dict:
    with _lock:
        if not os.path.exists(USERS_FILE):
            data = {"users": [], "roles": dict(DEFAULT_ROLES)}
            _save_unlocked(data)
            return data
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("roles", dict(DEFAULT_ROLES))
        for r, perms in DEFAULT_ROLES.items():
            data["roles"].setdefault(r, perms)
        changed = False
        for u in data.get("users", []):
            before = json.dumps(u, sort_keys=True, ensure_ascii=False)
            _normalize_user(u)
            after = json.dumps(u, sort_keys=True, ensure_ascii=False)
            if before != after:
                changed = True
        if changed:
            _save_unlocked(data)
        return data


def _save_unlocked(data: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save(data: dict):
    with _lock:
        _save_unlocked(data)


def _find_user(data: dict, identity: str) -> Optional[dict]:
    """按 username 或 email（不区分大小写）查找。"""
    key = (identity or "").strip()
    if not key:
        return None
    key_l = key.lower()
    for u in data["users"]:
        if u.get("username") == key:
            return u
        email = (u.get("email") or "").strip().lower()
        if email and email == key_l:
            return u
    return None


def _public_user(u: dict, roles: dict) -> dict:
    role = ROLE_ALIASES.get(u.get("role"), u.get("role"))
    return {
        "username": u["username"],
        "email": u.get("email") or "",
        "display_name": u.get("display_name") or u["username"],
        "role": role,
        "enabled": u.get("enabled", True),
        "created_at": u.get("created_at"),
        "last_login_at": u.get("last_login_at"),
        "profile": u.get("profile") or _empty_profile(),
        "usage": u.get("usage") or _empty_usage(),
        "permissions": roles.get(role, []),
    }


def authenticate(identity: str, password: str) -> Optional[dict]:
    """鉴权：identity 可为 username 或 email。返回会话用户信息或 None。
    明文密码匹配成功时惰性升级为哈希（需 werkzeug）。
    """
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return None
    if not u.get("enabled", True):
        return None
    stored = u.get("password") or ""
    if not _verify_password(stored, password):
        return None
    # 明文 → 哈希（登录时迁移，不打断演示账号）
    if not _is_hashed(stored) and generate_password_hash is not None:
        u["password"] = _hash_password(password)
        u["password_algo"] = "werkzeug"
        _save(data)
    roles = data.get("roles", {})
    return _public_user(u, roles)


def touch_login(identity: str) -> None:
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return
    u["last_login_at"] = _now()
    u.setdefault("usage", _empty_usage())
    u["usage"]["logins"] = int(u["usage"].get("logins", 0)) + 1
    _save(data)


def check_permission(user: dict, action: str) -> bool:
    if not user:
        return False
    perms = user.get("permissions", [])
    return "*" in perms or action in perms


def can_view_all_campaigns(user: dict) -> bool:
    if not user:
        return False
    if check_permission(user, "*") or check_permission(user, "view_all_campaigns"):
        return True
    return user.get("role") in ("super_admin", "operator")


def is_super_admin(user: dict) -> bool:
    return bool(user) and (
        user.get("role") == "super_admin" or check_permission(user, "*")
    )


def list_users(include_usage: bool = True) -> list:
    data = _load()
    out = []
    for u in data["users"]:
        item = {
            "username": u["username"],
            "email": u.get("email") or "",
            "display_name": u.get("display_name") or u["username"],
            "role": ROLE_ALIASES.get(u.get("role"), u.get("role")),
            "enabled": u.get("enabled", True),
            "created_at": u.get("created_at"),
            "last_login_at": u.get("last_login_at"),
            "profile": u.get("profile") or _empty_profile(),
            "password_hashed": _is_hashed(u.get("password") or ""),
        }
        if include_usage:
            item["usage"] = u.get("usage") or _empty_usage()
        out.append(item)
    return out


def get_user(identity: str) -> Optional[dict]:
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return None
    return _public_user(u, data.get("roles", {}))


def list_roles() -> dict:
    return _load().get("roles", {})


def register_user(
    email: str, password: str, display_name: str = "", username: Optional[str] = None
) -> dict:
    """终端用户自助注册，role=user。成功返回公开用户信息，失败抛 ValueError。"""
    email = (email or "").strip().lower()
    password = password or ""
    display_name = (display_name or "").strip() or email.split("@")[0]
    if not email or "@" not in email:
        raise ValueError("请输入有效邮箱")
    if len(password) < 8:
        raise ValueError("密码至少 8 位")
    data = _load()
    if _find_user(data, email):
        raise ValueError("该邮箱已注册")
    uname = (username or "").strip() or email.split("@")[0]
    # 避免 username 冲突
    base = uname
    n = 1
    while any(x.get("username") == uname for x in data["users"]):
        n += 1
        uname = f"{base}{n}"
    user = {
        "username": uname,
        "email": email,
        "password": _hash_password(password),
        "password_algo": "werkzeug" if generate_password_hash else "plain",
        "display_name": display_name,
        "role": "user",
        "enabled": True,
        "created_at": _now(),
        "last_login_at": None,
        "profile": _empty_profile(),
        "usage": _empty_usage(),
    }
    data["users"].append(user)
    _save(data)
    return _public_user(user, data.get("roles", {}))


def add_user(
    username: str, password: str, role: str, email: str = "", display_name: str = ""
) -> bool:
    data = _load()
    if any(u["username"] == username for u in data["users"]):
        return False
    email = (email or "").strip().lower()
    if email and _find_user(data, email):
        return False
    role = ROLE_ALIASES.get(role, role)
    if role not in data.get("roles", DEFAULT_ROLES):
        role = "user"
    data["users"].append(
        {
            "username": username,
            "email": email,
            "password": _hash_password(password),
            "password_algo": "werkzeug" if generate_password_hash else "plain",
            "display_name": display_name or username,
            "role": role,
            "enabled": True,
            "created_at": _now(),
            "last_login_at": None,
            "profile": _empty_profile(),
            "usage": _empty_usage(),
        }
    )
    _save(data)
    return True


def set_user_enabled(identity: str, enabled: bool) -> bool:
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return False
    u["enabled"] = bool(enabled)
    _save(data)
    return True


def disable_user(username: str) -> bool:
    return set_user_enabled(username, False)


def set_user_role(identity: str, role: str) -> bool:
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return False
    role = ROLE_ALIASES.get(role, role)
    if role not in data.get("roles", DEFAULT_ROLES) and role not in DEFAULT_ROLES:
        return False
    u["role"] = role
    _save(data)
    return True


def update_profile(
    identity: str,
    notes: Optional[str] = None,
    tags: Optional[list] = None,
    segment: Optional[str] = None,
) -> Optional[dict]:
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return None
    prof = u.setdefault("profile", _empty_profile())
    if notes is not None:
        prof["notes"] = notes
    if tags is not None:
        prof["tags"] = list(tags)
    if segment is not None:
        prof["segment"] = segment
    _save(data)
    return _public_user(u, data.get("roles", {}))


def bump_usage(identity: str, key: str, delta: int = 1) -> None:
    data = _load()
    u = _find_user(data, identity)
    if not u:
        return
    u.setdefault("usage", _empty_usage())
    u["usage"][key] = int(u["usage"].get(key, 0)) + delta
    _save(data)


def change_password(username: str, new_password: str) -> bool:
    data = _load()
    u = _find_user(data, username)
    if not u:
        return False
    u["password"] = _hash_password(new_password)
    u["password_algo"] = "werkzeug" if generate_password_hash else "plain"
    _save(data)
    return True


def default_password_risk() -> dict:
    """检测演示弱口令是否仍以明文/未改密存在（不返回口令本身）。"""
    weak_users = []
    data = _load()
    # 仅检查常见演示账号是否仍启用；不泄露口令
    demo_names = {"admin", "operator", "judge"}
    for u in data.get("users", []):
        name = u.get("username") or ""
        if name not in demo_names:
            continue
        if not u.get("enabled", True):
            continue
        weak_users.append(
            {
                "username": name,
                "hashed": _is_hashed(u.get("password") or ""),
            }
        )
    return {
        "demo_accounts_enabled": weak_users,
        "recommend_change": bool(weak_users),
    }
