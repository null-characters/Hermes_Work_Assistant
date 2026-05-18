# Kingdee MCP Server Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy SDK first
COPY lib/ /app/lib/

# Copy source code and dependencies
COPY services/kingdee-mcp-server/pyproject.toml services/kingdee-mcp-server/README.md ./
COPY services/kingdee-mcp-server/src/ src/

# Set SDK path
ENV KINGDEE_SDK_PATH=/app/lib

# Install dependencies
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /app/data/audit

# Environment
ENV PYTHONUNBUFFERED=1
ENV AUDIT_LOG_DIR=/app/data/audit
ENV TRANSPORT=sse
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose SSE port (MCP over HTTP)
EXPOSE 8080

# Run server with SSE transport
CMD ["python", "-m", "kingdee_mcp_server.server", "sse"]