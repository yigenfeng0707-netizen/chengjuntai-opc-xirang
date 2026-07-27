@echo off
cd /d %~dp0
pip install aiohttp requests cachetools flask --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
python mcp_http_nl2sql_v3.py
pause
