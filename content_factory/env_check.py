# -*- coding: utf-8 -*-
"""
模块1：本地环境自动检测 & 自适应模块
部署优先执行，校验内容工厂全部运行条件，输出 environment_check.log 自检报告。
start.bat 启动流程优先执行环境检测，不满足条件阻断运行并提供修复方案。
"""
import os
import sys
import json
import shutil
import socket
import platform
import datetime
import subprocess

# 统一路径分隔适配
ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(ROOT, "logs", "environment_check.log")
RESERVED_PORTS = [8082, 8765]  # NL2SQL 已占用端口，规避冲突

os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)


def norm(p):
    """统一 Windows 路径格式"""
    return os.path.normpath(p)


def check_python_version():
    """1. 检测 Python 版本，推荐 3.11~3.13"""
    major, minor = sys.version_info[0], sys.version_info[1]
    ver_str = f"{major}.{minor}.{sys.version_info[2]}"
    ok = (major == 3 and 11 <= minor <= 13)
    fix = "" if ok else "请安装 Python 3.11~3.13，下载: https://www.python.org/downloads/"
    return {"item": "Python版本", "value": ver_str, "pass": ok, "fix": fix}


def check_disk_space():
    """2. 检测磁盘剩余空间（至少 500MB）"""
    usage = shutil.disk_usage(ROOT)
    free_mb = usage.free / (1024 * 1024)
    ok = free_mb > 500
    fix = "" if ok else f"磁盘剩余空间不足({free_mb:.0f}MB)，请清理 D 盘"
    return {"item": "磁盘剩余空间", "value": f"{free_mb:.0f}MB", "pass": ok, "fix": fix}


def check_pypi_mirror():
    """3. 测试国内 PyPI 镜像连通性（阿里云）"""
    import urllib.request
    url = "https://mirrors.aliyun.com/pypi/simple/"
    try:
        urllib.request.urlopen(url, timeout=5)
        ok = True
        fix = ""
    except Exception as e:
        ok = False
        fix = f"PyPI 镜像不可达: {e}；可换源: pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/"
    return {"item": "PyPI镜像连通", "value": "aliyun" if ok else "失败", "pass": ok, "fix": fix}


def check_venv():
    """4. 识别虚拟环境（可选，复用/重建）"""
    in_venv = hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    exe = sys.executable
    ok = True
    fix = "" if in_venv else "未使用虚拟环境(可选)；建议: python -m venv .venv && .venv\\Scripts\\activate"
    return {"item": "虚拟环境", "value": "已启用" if in_venv else f"全局({exe})", "pass": ok, "fix": fix}


def check_port_conflict():
    """5. 端口占用检测，规避 MCP 服务、Web 面板端口冲突"""
    web_port = 8090
    conflicts = []
    for p in [web_port] + RESERVED_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
        except OSError:
            conflicts.append(p)
    # 8090 冲突会阻断 web，保留端口占用属正常
    web_ok = web_port not in conflicts
    fix = "" if web_ok else f"Web面板端口 {web_port} 被占用，请修改 config.yaml 的 web_port"
    return {"item": "端口占用(Web:8090)", "value": f"冲突端口:{conflicts}" if conflicts else "无冲突",
            "pass": web_ok, "fix": fix}


def check_bid_pipeline():
    """6. 检测 BidAutoPipeline 目录是否存在，缺失告警"""
    try:
        import yaml
        cfg_path = os.path.join(ROOT, "config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        bid_root = cfg.get("bid_pipeline_root", "")
    except Exception:
        bid_root = "D:/work/BidAutoPipeline"
    exists = os.path.isdir(bid_root) if bid_root else False
    # 缺失只告警不阻断
    return {"item": "BidAutoPipeline目录", "value": bid_root,
            "pass": True, "fix": "" if exists else f"告警:标书系统目录不存在[{bid_root}]，双向联动功能将降级为本地模拟"}


def check_dependencies():
    """检测关键依赖是否已安装"""
    required = {"yaml": "pyyaml", "feedparser": "feedparser", "numpy": "numpy",
                "sklearn": "scikit-learn", "fastapi": "fastapi", "reportlab": "reportlab"}
    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    ok = len(missing) == 0
    fix = "" if ok else f"缺失依赖:{missing}；执行: pip install -r requirements -i https://mirrors.aliyun.com/pypi/simple/"
    return {"item": "Python依赖", "value": "齐全" if ok else f"缺{len(missing)}项", "pass": ok, "fix": fix}


def check_nl2sql_service():
    """检测 NL2SQL MCP 服务是否在运行（数据回流联动依赖）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 8765))
        s.close()
        ok = True
        fix = ""
    except OSError:
        ok = False
        fix = "NL2SQL MCP服务(8765)未运行，数据回流查询投标历史将降级；启动: 双击 ../start_mcp.bat"
    return {"item": "NL2SQL联动服务", "value": "在线" if ok else "离线", "pass": True, "fix": fix}


def run_all():
    checks = [
        check_python_version(),
        check_disk_space(),
        check_pypi_mirror(),
        check_venv(),
        check_port_conflict(),
        check_bid_pipeline(),
        check_dependencies(),
        check_nl2sql_service(),
    ]
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"========== 内容工厂环境自检报告 {ts} =========="]
    lines.append(f"平台: {platform.platform()}")
    lines.append(f"检测目录: {ROOT}")
    lines.append("")
    block = False
    for c in checks:
        flag = "PASS" if c["pass"] else "FAIL"
        lines.append(f"[{flag}] {c['item']}: {c['value']}")
        if c["fix"]:
            lines.append(f"       修复建议: {c['fix']}")
        if not c["pass"]:
            block = True
    lines.append("")
    lines.append("结论: " + ("环境满足全部运行条件 ✅" if not block else "存在阻断项 ❌，请按修复建议处理"))
    report = "\n".join(lines)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    return report, block


if __name__ == "__main__":
    report, blocked = run_all()
    print(report)
    print(f"\n自检报告已保存: {LOG_FILE}")
    sys.exit(1 if blocked else 0)
