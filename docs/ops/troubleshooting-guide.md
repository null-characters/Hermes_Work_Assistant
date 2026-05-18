# Hermes Work Assistant 故障排查指南

## 快速诊断流程

```
1. 检查服务状态 → docker-compose ps
2. 检查健康端点 → curl /health
3. 检查日志 → docker logs <container>
4. 检查网络 → docker network inspect
5. 检查资源 → docker stats
```

## 常见故障场景

### 1. 服务无法启动

#### 症状
```bash
docker-compose ps
# 显示服务状态为 Exited 或 Restarting
```

#### 诊断步骤

**Step 1: 查看容器日志**
```bash
docker logs hermes-bridge --tail 50
docker logs hermes-mcp-server --tail 50
docker logs hermes-wechat-gateway --tail 50
```

**Step 2: 检查配置文件**
```bash
# 验证 .env 文件存在且配置正确
cat .env | grep -E "HERMES|KINGDEE|WECHAT"

# 验证配置文件语法
python -c "import yaml; yaml.safe_load(open('config/mcp_servers.yaml'))"
```

**Step 3: 检查端口占用**
```bash
# 检查端口是否被占用
lsof -i :8000
lsof -i :8001
lsof -i :8080
```

#### 解决方案

| 错误信息 | 解决方案 |
|----------|----------|
| `Port 8000 already in use` | 停止占用端口的服务或修改 docker-compose.yml 端口映射 |
| `Environment variable not set` | 检查 .env 文件，确保所有必需变量已设置 |
| `Module not found` | 重新构建镜像：`docker-compose build --no-cache` |

---

### 2. ERP 连接失败

#### 症状
```json
{
  "success": false,
  "error": "Kingdee API connection failed"
}
```

#### 诊断步骤

**Step 1: 验证金蝶 API 可访问**
```bash
curl -v $KINGDEE_API_URL/K3Cloud/K3CloudApi/Login \
  -H "Content-Type: application/json" \
  -d '{"dbId": "$KINGDEE_DB_ID", "user": "$KINGDEE_USER", "pwd": "$KINGDEE_PASSWORD"}'
```

**Step 2: 检查网络连通性**
```bash
# 从容器内部测试
docker exec hermes-mcp-server curl -s $KINGDEE_API_URL
```

**Step 3: 检查凭证有效性**
```bash
# 查看审计日志中的错误详情
cat data/audit/*.jsonl | grep -i "error" | tail -10
```

#### 解决方案

| 错误类型 | 解决方案 |
|----------|----------|
| `Connection timeout` | 检查防火墙规则，确保金蝶 API 端口可访问 |
| `Authentication failed` | 验证用户名/密码正确，检查账号是否被锁定 |
| `Database not found` | 验证 DB_ID 正确，检查数据库是否在线 |

---

### 3. 企业微信消息接收失败

#### 症状
- 用户发送消息后无响应
- 网关日志显示回调验证失败

#### 诊断步骤

**Step 1: 检查回调 URL 配置**
```bash
# 查看企微网关日志
docker logs hermes-wechat-gateway --tail 50 | grep -i "callback"
```

**Step 2: 手动测试回调验证**
```bash
curl "http://localhost:8001/callback?msg_signature=xxx&timestamp=xxx&nonce=xxx"
```

**Step 3: 检查企业微信后台配置**
- 登录企业微信管理后台
- 检查应用设置的回调 URL
- 验证 Token 和 EncodingAESKey 配置

#### 解决方案

| 错误类型 | 解决方案 |
|----------|----------|
| `Signature verification failed` | 检查 Token 配置是否与企微后台一致 |
| `AES decryption failed` | 检查 EncodingAESKey 配置正确 |
| `Callback URL unreachable` | 检查公网可访问，配置 HTTPS |

---

### 4. Agent 响应超时

#### 症状
```json
{
  "error": "Agent timeout after 30s"
}
```

#### 诊断步骤

**Step 1: 检查 Hermes API 状态**
```bash
curl -s $HERMES_API_URL/health
curl -s $HERMES_API_URL/status
```

**Step 2: 检查 MCP Server 响应时间**
```bash
# 查看 Prometheus 指标
curl -s http://localhost:8080/metrics | grep -E "erp_query|erp_create"
```

**Step 3: 检查网络延迟**
```bash
# 从网关容器测试 Hermes 连接
docker exec hermes-wechat-gateway curl -s -w "%{time_total}" $HERMES_AGENT_URL/health
```

#### 解决方案

| 错误类型 | 解决方案 |
|----------|----------|
| `Hermes API unreachable` | 检查 HERMES_API_URL 配置，验证网络连通 |
| `MCP Server slow response` | 启用缓存（ST-030），检查金蝶 API 性能 |
| `Network latency high` | 检查网络配置，考虑部署在同一区域 |

---

### 5. 缓存命中率低

#### 症状
```
# Prometheus 指标显示缓存命中率 < 50%
cache_hit_rate: 0.3
```

#### 诊断步骤

**Step 1: 检查缓存配置**
```bash
# 查看 Redis 状态
docker exec hermes-redis redis-cli INFO stats
```

**Step 2: 检查缓存键分布**
```bash
docker exec hermes-redis redis-cli KEYS "erp_query:*"
```

**Step 3: 分析查询模式**
```bash
# 查看审计日志中的查询参数分布
cat data/audit/*.jsonl | jq '.params.form_id' | sort | uniq -c
```

#### 解决方案

| 问题 | 解决方案 |
|------|----------|
| 缓存键过于分散 | 统一查询参数格式，减少参数变体 |
| 缓存过期时间太短 | 增加 TTL 到 5 分钟或更长 |
| Redis 内存不足 | 增加 Redis 内存限制 |

---

### 6. 内存占用过高

#### 症状
```bash
docker stats
# 显示容器内存使用 > 80%
```

#### 诊断步骤

**Step 1: 检查容器资源使用**
```bash
docker stats --no-stream
```

**Step 2: 检查进程内存**
```bash
docker exec hermes-bridge ps aux --sort=-%mem
```

**Step 3: 检查日志文件大小**
```bash
du -sh data/audit/
du -sh data/logs/
```

#### 解决方案

| 问题 | 解决方案 |
|------|----------|
| 日志文件过大 | 配置日志轮转，定期清理旧日志 |
| 内存泄漏 | 重启服务，检查代码中的循环引用 |
| 容器内存限制过低 | 增加 docker-compose.yml 中的 mem_limit |

---

## 日志分析技巧

### 搜索错误日志
```bash
# 搜索所有服务的错误
docker-compose logs | grep -i "error\|exception\|failed"

# 搜索特定时间段
docker-compose logs --since 1h | grep -i "error"

# 搜索特定服务
docker logs hermes-mcp-server 2>&1 | grep -i "error"
```

### 分析审计日志
```bash
# 统计错误类型分布
cat data/audit/*.jsonl | jq 'select(.success == false)' | jq '.error' | sort | uniq -c

# 统计操作频率
cat data/audit/*.jsonl | jq '.operation' | sort | uniq -c

# 查找特定用户的操作
cat data/audit/*.jsonl | jq 'select(.user_id == "user123")'
```

## 性能调优

### 连接池配置
```yaml
# config/mcp_servers.yaml
connection_pool:
  max_connections: 10
  connection_timeout: 30
  idle_timeout: 60
```

### 缓存配置
```yaml
# config/mcp_servers.yaml
cache:
  enabled: true
  ttl: 300  # 5 分钟
  max_size: 1000
```

### 并发限制
```yaml
# config/mcp_servers.yaml
rate_limit:
  max_requests_per_minute: 60
  burst: 10
```

## 紧急恢复流程

```bash
# 1. 停止所有服务
docker-compose down

# 2. 清理异常状态
docker system prune -f

# 3. 重新启动
docker-compose up -d

# 4. 验证服务状态
docker-compose ps
curl -s http://localhost:8000/health
```

## 联系支持

如遇无法解决的问题，请提供以下信息：

1. 错误日志（最近 50 行）
2. 容器状态输出
3. 配置文件（脱敏后）
4. 复现步骤