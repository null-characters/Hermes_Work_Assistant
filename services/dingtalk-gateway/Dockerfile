FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# 复制源码
COPY src/ ./src/

# 暴露端口
EXPOSE 8002

# 启动服务
CMD ["python", "-m", "uvicorn", "dingtalk_gateway.main:app", "--host", "0.0.0.0", "--port", "8002"]
