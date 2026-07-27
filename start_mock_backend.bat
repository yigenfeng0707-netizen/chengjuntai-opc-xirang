@echo off
cd /d %~dp0
pip install flask --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
python znws_query_mock.py
pause
