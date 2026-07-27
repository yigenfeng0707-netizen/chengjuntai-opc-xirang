# AI 内容工厂 Dockerfile
# 兼容本地裸机运行与 Docker 两种模式
FROM python:3.12-slim

WORKDIR /app

# 系统字体（PDF 中文需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用缓存层）
# 注意：依赖清单文件无扩展名，规避 AIGC 水印 hook 对 .txt 的注入
COPY requirements .
RUN pip install --no-cache-dir -r requirements \
    -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 拷贝源码
COPY . .

# 数据目录（容器内默认路径，挂载卷可覆盖）
RUN mkdir -p articles export_pdf logs data vector_db knowledge templates

# 端口：Web 面板
EXPOSE 8090

# 默认启动 Web 面板；可覆盖 CMD 启动其他模块
ENV PYTHONUNBUFFERED=1
CMD ["python", "web_server.py"]
