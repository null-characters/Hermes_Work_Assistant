# Kingdee MCP Server Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/

# Create data directory
RUN mkdir -p /app/data/audit

# Environment
ENV PYTHONUNBUFFERED=1
ENV AUDIT_LOG_DIR=/app/data/audit

# Expose metrics port
EXPOSE 8080

# Run server
CMD ["python", "-m", "kingdee_mcp_server.server"]