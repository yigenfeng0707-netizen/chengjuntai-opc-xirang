# -*- coding: utf-8 -*-
"""一键健康检查：Web / LLM 配置 / NL2SQL / 战役目录

退出码：
  0 — 本地结构可用（config/users/战役目录 OK；Web 可选在线）
  1 — 严重缺失（无 config 或无战役目录等）

LLM 未配置时仍返回 0，但会在控制台打印明确的下一步提示。
"""
import os
import sys
import json
import socket
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "content_factory")
sys.path.insert(0, CF)

def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False


def http_json(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    os.chdir(CF)
    from config_loader import load_config
    import llm_client

    cfg = load_config()
    report = {
        "product": cfg.get("product_name"),
        "checks": [],
        "ok": True,
        "demo_ready": False,
        "hints": [],
    }

    def add(name, passed, detail="", required=False):
        report["checks"].append({"name": name, "pass": passed, "detail": detail, "required": required})
        if not passed and required:
            report["ok"] = False

    add("config.yaml", os.path.exists(os.path.join(CF, "config.yaml")), "配置文件", required=True)
    add("users.json", os.path.exists(os.path.join(CF, "users.json")), "用户文件", required=True)

    llm = llm_client.provider_status()
    if llm.get("providers"):
        add("llm_providers", True, json.dumps(llm.get("providers"), ensure_ascii=False))
    else:
        add(
            "llm_providers",
            False,
            "无可用 Key — Path B: XIRANG_API_KEY；Interim: config.yaml 或 TOKEN_PLAN_API_KEY/SENSENOVA_API_KEY",
        )
        report["hints"].append(
            "Interim: 在 gitignore 的 content_factory/config.yaml 填 Token Plan/SenseNova；或设环境变量后重启 Web"
        )
        report["hints"].append(
            "公网可先走天翼云试用（不必等 Token）：docs/CTYUN_TRIAL.md + DEPLOY天翼云.md"
        )

    host = cfg.get("web_host", "127.0.0.1")
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    port = int(cfg.get("web_port", 8090))
    web_up = port_open(host, port)
    web_health = None
    add("web_port", web_up, f"{host}:{port} — 未启动则运行 scripts\\start_local_demo.bat")
    if web_up:
        try:
            web_health = http_json(f"http://{host}:{port}/api/health")
            hint = (web_health.get("llm") or {}).get("hint") or web_health.get("slogan") or ""
            add("web_health", bool(web_health.get("ok")), hint)
        except Exception as ex:
            add("web_health", False, str(ex))
    else:
        report["hints"].append("Web 未在线：先运行 scripts\\start_local_demo.bat")

    nl_port = int(cfg.get("nl2sql_backend", {}).get("mcp_port", 8765))
    add("nl2sql_mcp_port", port_open("127.0.0.1", nl_port), f"127.0.0.1:{nl_port}（可选，数据参谋）")
    add("backend_8082", port_open("127.0.0.1", 8082), "问数后端（可选）")

    camp_mcp = os.path.join(CF, "mcp_campaign_server.py")
    factory_mcp = os.path.join(CF, "mcp_server.py")
    root_mcp_json = os.path.join(ROOT, "mcp.json")
    add(
        "mcp_campaign_server",
        os.path.isfile(camp_mcp),
        "stdio：start_campaign/list_tasks/approve_gate/export_report",
    )
    add("mcp_content_factory", os.path.isfile(factory_mcp), "stdio：内容工厂工具（含公众号草稿）")
    add("mcp_json", os.path.isfile(root_mcp_json), "仓库根 mcp.json（Cursor 挂载）")

    try:
        import wechat_publisher
        wst = wechat_publisher.status_summary()
        add(
            "wechat_draft",
            True,
            wst.get("hint") or ("configured" if wst.get("configured") else "未配置"),
        )
        if not wst.get("configured"):
            report["hints"].append(
                "公众号草稿可选：本机配置 WECHAT_APP_ID/SECRET 或 config.wechat.local.yaml（见 docs/WECHAT_PUBLISH.md）"
            )
    except Exception as ex:
        add("wechat_draft", False, str(ex))

    camp_dir = os.path.join(CF, "data", "campaigns")
    add("campaigns_dir", os.path.isdir(camp_dir), camp_dir, required=True)

    llm_ok = bool(llm.get("providers"))
    web_llm_ok = True
    if web_up and web_health is not None:
        web_llm_ok = bool((web_health.get("llm") or {}).get("enabled"))
    report["demo_ready"] = bool(report["ok"] and web_up and llm_ok and web_llm_ok)

    if llm_ok and web_up and web_health is not None and not web_llm_ok:
        report["hints"].append(
            "config 已有 interim Key，但 :8090 仍是旧进程 — 重启 scripts\\start_local_demo.bat 后 demo_ready=true"
        )
    elif web_up and web_health is not None and not web_llm_ok and not llm_ok:
        report["hints"].append(
            "Web 已启动但无 LLM：看板可浏览，发起战役会明确报错（禁止静默 mock）"
        )

    if report["demo_ready"]:
        report["hints"].append("评委路径就绪：登录 → 成军看板 → 发起成军 → 人审 → 导出周报")
    elif report["ok"] and not llm_ok:
        report["hints"].append(
            "本地结构 OK；向主办方要星辰/息壤 Token，或 interim 用 Token Plan/SenseNova。见 docs/CTYUN_TRIAL.md"
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["hints"]:
        print("\n--- 下一步 ---")
        for h in report["hints"]:
            print(f"* {h}")

    return 0 if report["ok"] else 1

if __name__ == "__main__":
    try:
        code = main()
    except Exception as ex:
        print(json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False))
        code = 1
    sys.exit(code)
