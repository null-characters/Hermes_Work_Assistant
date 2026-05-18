# WeChat Gateway Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy source code first
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN pip install --no-cache-dir .

# Environment
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8001

# Run server
CMD ["python", "-m", "wechat_gateway.main"]