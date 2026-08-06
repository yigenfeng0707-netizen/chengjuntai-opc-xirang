import paramiko, time

# 多轮重试连接
client = None
for i in range(15):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            "171.111.219.204",
            username="root",
            password="Xirang2026@Cj",
            timeout=20,
            look_for_keys=False,
            allow_agent=False,
            banner_timeout=20,
            auth_timeout=20,
        )
        print(f"SSH connected (attempt {i + 1})")
        break
    except Exception as e:
        print(f"  attempt {i + 1}: {type(e).__name__}")
        time.sleep(15)

if not client:
    print("All attempts failed")
    exit(1)

print("\n=== 检查Werkzeug安装状态 ===")
stdin, stdout, stderr = client.exec_command(
    "/opt/nl2sql_teleagent_prod/venv/bin/python -c 'import werkzeug; print(werkzeug.__version__)' 2>&1"
)
print("version:", stdout.read().decode().strip())

stdin, stdout, stderr = client.exec_command(
    '/opt/nl2sql_teleagent_prod/venv/bin/python -c \'from werkzeug.security import check_password_hash; print(check_password_hash("scrypt:32768:8:1\\$RC9aUYCD8Bzszcc6\\$c10c587b54b574fc85c6db0cbf326667f3c6ac04226dc54928881ea61c9e9825d67f421916d426a8b5954c07f342b596296c363308285bc39ccef7e7241610a0", "chengjun2026"))\' 2>&1'
)
print("hash check:", stdout.read().decode().strip())

print("\n=== 强制重新安装Werkzeug 3.x ===")
stdin, stdout, stderr = client.exec_command(
    "/opt/nl2sql_teleagent_prod/venv/bin/pip install --force-reinstall 'werkzeug>=3.0' -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1"
)
print(
    "install output:",
    stdout.read().decode().strip()[-500:] or stderr.read().decode().strip()[-500:],
)

stdin, stdout, stderr = client.exec_command(
    "/opt/nl2sql_teleagent_prod/venv/bin/python -c 'import werkzeug; print(werkzeug.__version__)' 2>&1"
)
print("after install:", stdout.read().decode().strip())

print("\n=== 重启服务 ===")
client.exec_command("systemctl restart teleagent-web teleagent-backend teleagent-mcp")
time.sleep(5)

print("\n=== 验证登录 ===")
stdin, stdout, stderr = client.exec_command(
    'curl -s -X POST http://127.0.0.1:8090/api/login -H \'Content-Type: application/json\' -d \'{"u":"admin","p":"chengjun2026"}\''
)
login_res = stdout.read().decode().strip()
print("login:", login_res[:200])

if '"token"' in login_res:
    import json

    token = json.loads(login_res).get("token", "")
    print(f"Token: {token[:20]}...")

    stdin, stdout, stderr = client.exec_command(
        f"curl -s http://127.0.0.1:8090/api/campaigns -H 'Authorization: Bearer {token}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"Campaigns:\", len(d))'"
    )
    print("campaigns:", stdout.read().decode().strip())

    stdin, stdout, stderr = client.exec_command(
        f"curl -s http://127.0.0.1:8090/api/artifacts/center -H 'Authorization: Bearer {token}' | python3 -c 'import sys,json; d=json.load(sys.stdin); ca=d.get(\"campaign_artifacts\",[]); print(\"Artifacts:\", len(ca))'"
    )
    print("artifacts:", stdout.read().decode().strip())

    print("\n✅ 功能恢复！")
else:
    print("\n❌ 登录仍失败")

client.close()
