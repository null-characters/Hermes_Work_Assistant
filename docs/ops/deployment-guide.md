# Hermes Work Assistant 部署指南

## 环境准备

### 1. 系统要求

| 组件 | 版本要求 |
|------|----------|
| Python | 3.10+ |
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Redis | 6.0+ (可选，用于缓存) |

### 2. 环境变量配置

创建 `.env` 文件：

```bash
# Hermes Agent 配置
HERMES_API_URL=https://your-hermes-instance.com
HERMES_API_KEY=your_api_key

# 金蝶 ERP 配置
KINGDEE_API_URL=https://your-kingdee-server.com
KINGDEE_DB_ID=your_database_id
KINGDEE_USER=your_username
KINGDEE_PASSWORD=your_password

# 企业微信配置
WECHAT_CORP_ID=your_corp_id
WECHAT_AGENT_ID=your_agent_id
WECHAT_SECRET=your_secret
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_aes_key

# MCP Server 配置
MCP_SERVER_PORT=8080
AUDIT_LOG_DIR=/app/data/audit

# Skills 配置
SKILLS_PATH=./config/skills
```

## 部署步骤

### 方式一：Docker Compose 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/your-org/Hermes_Work_Assistant.git
cd Hermes_Work_Assistant

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际配置

# 3. 启动所有服务
docker-compose up -d

# 4. 检查服务状态
docker-compose ps
```

### 方式二：本地开发部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MCP Server
cd services/kingdee-mcp-server
pip install -e .
python -m kingdee_mcp_server.server

# 3. 启动企微网关
cd services/wechat-gateway
pip install -e .
python -m wechat_gateway.main

# 4. 启动 Hermes Bridge
cd services/hermes-bridge
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 服务架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  企业微信        │────▶│  WeChat Gateway   │────▶│  Hermes Bridge   │
│  (用户消息)      │     │  (消息转换)       │     │  (Agent 调度)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────┐
                                                │  MCP Server      │
                                                │  (ERP 工具)       │
                                                └─────────────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────┐
                                                │  金蝶 ERP        │
                                                │  (业务系统)      │
                                                └─────────────────┘
```

## 健康检查

### 服务端点

| 服务 | 健康检查端点 | 端口 |
|------|-------------|------|
| Hermes Bridge | `/health` | 8000 |
| WeChat Gateway | `/health` | 8001 |
| MCP Server | `/metrics` | 8080 |
| Web UI | `/_stcore/health` | 8501 |

### 检查命令

```bash
# 检查所有服务健康状态
curl -s http://localhost:8000/health
curl -s http://localhost:8001/health
curl -s http://localhost:8080/metrics

# Docker 健康检查
docker-compose ps
docker inspect --format='{{.State.Health.Status}}' hermes-bridge
```

## 监控配置

### Prometheus

1. 配置 Prometheus 采集目标：

```yaml
# prometheus/prometheus.yml
scrape_configs:
  - job_name: 'hermes-mcp'
    static_configs:
      - targets: ['kingdee-mcp-server:8080']
  - job_name: 'hermes-wechat'
    static_configs:
      - targets: ['wechat-gateway:8001']
```

2. 启动 Prometheus：

```bash
docker-compose up -d prometheus
```

### Grafana Dashboard

导入预置 Dashboard（`config/grafana-dashboard.json`）查看：
- ERP 查询/创建操作计数
- 错误率趋势
- P95 延迟分布

## 日志管理

### 日志路径

| 服务 | 日志路径 |
|------|----------|
| MCP Server | `/app/data/audit/*.jsonl` |
| Hermes Bridge | `/app/data/logs/*.log` |
| WeChat Gateway | `/app/data/logs/*.log` |

### 日志轮转

Docker 容器日志自动轮转：

```yaml
# docker-compose.yml
services:
  kingdee-mcp-server:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 安全配置

### 1. 网络隔离

```yaml
# docker-compose.yml
networks:
  hermes-internal:
    internal: true  # 内部网络，不暴露外部
  hermes-external:
    # 外部网络，用于 Web UI 和企微网关
```

### 2. 凭证管理

- 使用 Docker Secrets 或环境变量
- 不要在代码中硬编码凭证
- 定期轮换 API 密钥

### 3. HTTPS 配置

```nginx
# nginx/nginx.conf
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
}
```

## 常见问题

### Q1: MCP Server 启动失败

检查金蝶 ERP 配置：
```bash
# 验证金蝶 API 可访问
curl -s $KINGDEE_API_URL/K3Cloud/K3CloudApi/Login
```

### Q2: 企业微信消息接收失败

检查回调 URL 配置：
1. 登录企业微信管理后台
2. 设置应用回调 URL 为 `https://your-domain/callback`
3. 验证 Token 和 AES Key 配置正确

### Q3: Agent 响应超时

检查 Hermes API 连接：
```bash
curl -s $HERMES_API_URL/health
```

## 升级指南

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建镜像
docker-compose build

# 3. 重启服务
docker-compose up -d

# 4. 验证服务状态
docker-compose ps
curl -s http://localhost:8000/health
```

## 备份与恢复

### 数据备份

```bash
# 备份审计日志和会话数据
tar -czf hermes-backup-$(date +%Y%m%d).tar.gz data/
```

### 数据恢复

```bash
# 恢复数据
tar -xzf hermes-backup-20240101.tar.gz
docker-compose restart
```