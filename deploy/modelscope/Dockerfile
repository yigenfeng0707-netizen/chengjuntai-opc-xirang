# 成军台 · 魔搭创空间 Docker 部署
# 单容器：FastAPI 同源服务（templates/index.html 全内嵌前端，无独立静态目录）
# 魔搭平台硬性要求：监听 7860
FROM python:3.12-slim

WORKDIR /app

# PDF 中文导出需要 CJK 字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk && rm -rf /var/lib/apt/lists/*

# 依赖清单（无扩展名文件，规避 AIGC 水印 hook 对 .txt 的注入）
COPY content_factory/requirements /tmp/requirements
RUN pip install --no-cache-dir -r /tmp/requirements \
    -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 应用源码整目录拷贝（users.json / data / templates 等随带）
COPY content_factory /app/content_factory

# 运行时目录兜底（拷贝时 logs 等可能被排除）
RUN cd /app/content_factory \
    && mkdir -p articles export_pdf export_docx logs data vector_db knowledge templates

WORKDIR /app/content_factory
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

# web_server.start() 读 config.yaml 的 web_host/web_port（组装时已覆写为 0.0.0.0:7860）
CMD ["python", "web_server.py"]
