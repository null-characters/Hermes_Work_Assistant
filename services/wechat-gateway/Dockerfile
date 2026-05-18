# WeChat Gateway Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/

# Environment
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8001

# Run server
CMD ["python", "-m", "wechat_gateway.main"]