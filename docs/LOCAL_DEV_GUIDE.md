# 本地开发指南

> 本地化部署 + 企业微信集成 + 金蝶 ERP 集成

> ⚠️ **安全警告：当前版本为 MVP 阶段，生产环境需额外加固。详见 [安全警告](#安全警告) 章节。**

---

## 架构说明

本项目支持两种使用场景：

### 场景一：企业微信 + 金蝶 ERP 集成

| 组件 | 端口 | 说明 |
|------|------|------|
| Hermes Bridge | 8000 | Agent 调度 API |
| WeChat Gateway | 8001 | 企微消息接收 |
| MCP Server | 8080 | 金蝶 ERP 工具服务 |
| Hermes Agent | 8645 | LLM Agent 核心（内部调用） |
| Prometheus | 9090 | 监控面板 |

**数据流**：
```
企微消息 → WeChat Gateway (8001) → Hermes Bridge (8000) → MCP Server (8080) → 金蝶 ERP API
                                                                          │
                                                                          ▼
企微用户 ← 消息回复 ←────────────────────────────────────────────────── 业务结果
```

### 场景二：本地文件处理

| 组件 | 端口 | 说明 |
|------|------|------|
| **Web UI** | **8501** | Streamlit 前端界面（推荐） |
| Hermes Bridge | 8646 | 任务提交 API |
| Hermes Agent | 8645 | LLM Agent 核心（内部调用） |
| Prometheus | 9090 | 监控面板 |

**数据流**：
```
用户 → Web UI (8501) → Hermes Bridge (8646) → docker exec → Hermes Agent
                                                          │
                                                          ▼
                                                   LLM 推理 + 工具调用
                                                          │
                                                          ▼
用户 ← 结果文件 ← 本地文件系统 ← data/sessions/{session_id}/outputs/
```

**实时反馈流**：
```
Hermes Agent → stdout/stderr → Bridge 解析 → SSE 流式响应 → Web UI 显示
                                    │
                                    ├─ [thinking] 思考过程
                                    ├─ [tool] 工具准备
                                    ├─ [api_call] API 调用
                                    └─ [response] 响应内容
```

---

## 快速启动

### 1. 环境配置

```bash
cp .env.example .env
```

**必填配置**：

```env
# LLM API（必填，三选一）

# 方式 1: OpenRouter（推荐，200+ 模型可选）
HERMES_PROVIDER=openrouter
HERMES_MODEL=anthropic/claude-3-sonnet
OPENROUTER_API_KEY=sk-or-xxx

# 方式 2: OpenAI 兼容自定义端点（类 OpenAI 协议）
# 适用于：本地 VLLM/SGLang、自建服务、第三方兼容 API
# HERMES_PROVIDER=openai
# OPENAI_API_KEY=your-api-key
# OPENAI_BASE_URL=https://your-custom-url/v1
# HERMES_MODEL=your-model-name

# 方式 3: 其他提供商
# DEEPSEEK_API_KEY=xxx
# GLM_API_KEY=xxx
# KIMI_API_KEY=xxx
```

**金蝶 ERP 配置（可选，用于 ERP 集成）**：

```env
# 金蝶云 ERP（账号密码登录）
KINGDEE_API_URL=http://your-kingdee-server/K3Cloud
KINGDEE_ACCT_ID=your_acct_id
KINGDEE_USERNAME=your_username
KINGDEE_PASSWORD=your_password
KINGDEE_LCID=2052
```

**企业微信配置（可选，用于企微 Bot）**：

```env
# 企业微信 Bot
WECHAT_CORP_ID=your_corp_id
WECHAT_AGENT_ID=your_agent_id
WECHAT_SECRET=your_secret
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_aes_key
```

> 详细配置步骤请参考 [企业微信配置指南](./wecom_setup_guide.md)

---

### 2. 启动服务

```bash
# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f hermes-bridge
docker compose logs -f hermes-agent
```

---

### 3. 验证服务

```bash
# 健康检查
curl -s http://localhost:8000/health      # Hermes Bridge
curl -s http://localhost:8001/health      # WeChat Gateway
curl -s http://localhost:8080/metrics     # MCP Server
curl -s http://localhost:8501/_stcore/health  # Web UI

# 预期响应
# {"status":"healthy","service":"hermes-bridge","hermes_available":true}
# {"status":"ok"}
# # Prometheus 指标输出
# ok
```

---

## API 使用

### Hermes Bridge API

#### 提交文本任务

```bash
curl -X POST http://localhost:8646/api/task/submit \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，请介绍一下你自己"}'
```

#### 处理 Excel 文件（流式响应，推荐）

```bash
# 流式 API，实时显示 Agent 思考过程
curl -N -X POST http://localhost:8646/api/excel/stream \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/sessions/test/uploads/input.xlsx",
    "task": "将第一列数据按升序排序",
    "session_id": "test"
  }'
```

#### 直接对话（无需文件）

```bash
# 不上传文件，直接向 Agent 提问
curl -N -X POST http://localhost:8646/api/excel/stream \
  -H "Content-Type: application/json" \
  -d '{
    "task": "在 Excel 中如何快速求和？",
    "session_id": "chat_test"
  }'
```

**响应格式**（Server-Sent Events）：
```
data: {"type":"thinking","content":"💭 让我先检查一下这个Excel文件..."}
data: {"type":"tool","content":"🔧 准备工具: terminal"}
data: {"type":"api_call","content":"🌐 API 调用 #1: glm-5"}
data: {"type":"tool_result","content":"✅ 工具 1 完成 (0.46s)"}
data: {"type":"response","content":"🤖 已完成排序..."}
data: {"type":"done","content":"🎉 任务完成","output_file":"result.xlsx"}
```

#### 处理 Excel 文件（非流式）

```bash
# 非流式 API，等待完成后返回结果
curl -X POST http://localhost:8646/api/task/excel \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/sessions/test/uploads/input.xlsx",
    "task": "将第一列数据按升序排序",
    "session_id": "test"
  }'
```

#### 检查 Agent 状态

```bash
curl http://localhost:8646/api/status

# 响应示例：
# {"available":true,"container":"hermes-agent"}
```

---

## Swagger UI

访问 API 文档：

- Hermes Bridge: http://localhost:8646/docs

---

## 会话数据目录

```
data/sessions/
├── {session_id}/              # 会话目录
│   ├── workspace.db           # SQLite 数据库
│   ├── uploads/               # 上传文件
│   │   └── input.xlsx
│   └── outputs/               # 输出文件
│       └── result.xlsx
```

---

## 全链路测试

```bash
# 本地模式（模拟处理，无需 LLM API Key）
python tests/test_full_chain.py --mode local

# 完整模式（需要 Hermes Agent + LLM API Key）
python tests/test_full_chain.py --mode full
```

---

## 单元测试

```bash
cd services/file-upload

# 运行所有测试
python -m pytest app/tests/ -v

# 运行特定测试文件
python -m pytest app/tests/test_models.py -v
python -m pytest app/tests/test_minio_client.py -v
python -m pytest app/tests/test_upload.py -v

# 带覆盖率
pip install pytest-cov
python -m pytest app/tests/ -v --cov=app
```

---

## 常见问题

### Q: Hermes Agent 状态显示不可用？

```bash
# 检查容器状态
docker ps -a --filter "name=hermes-agent"

# 查看日志
docker logs hermes-agent --tail 50

# 重启服务
docker compose restart hermes-agent
```

### Q: LLM API 调用失败？

```bash
# 检查配置（注意：Hermes 配置目录是 /opt/data/ 而非 /root/.hermes/）
docker exec hermes-agent /opt/hermes/.venv/bin/hermes config show

# 查看 Agent 日志
docker logs hermes-agent --tail 100 | grep -i error

# 查看错误日志
docker exec hermes-agent tail -50 /opt/data/logs/errors.log
```

### Q: 端口被占用？

```bash
# 查看端口占用
lsof -i :8646
lsof -i :8501

# 修改 docker-compose.yml 中的端口映射
```

### Q: Web UI 无法访问？

```bash
# 检查容器状态
docker compose ps web-ui

# 查看日志
docker compose logs web-ui --tail 50

# 重启服务
docker compose restart web-ui
```

---

## 开发调试

### 本地开发 Hermes Bridge

```bash
cd services/hermes-bridge

# 安装依赖
pip install -r requirements.txt

# 本地运行（需要 Docker 访问 Hermes Agent 容器）
uvicorn app.main:app --reload --port 8646
```

### 查看 Hermes Agent 可用命令

```bash
docker exec hermes-agent /opt/hermes/.venv/bin/hermes --help
```

---

## 相关文档

- [README.md](../README.md) - 项目总览
- [部署指南](./ops/deployment-guide.md) - 生产环境部署
- [故障排除指南](./ops/troubleshooting-guide.md) - 常见问题
- [企业微信配置](./wecom_setup_guide.md) - 企微 Bot 配置
- [Skills 使用说明](../config/skills/README.md) - 技能模板定义
- [API 文档](http://localhost:8646/docs) - Swagger UI
- [评审报告](./workitems/规划评审分析/) - 双视角评审分析

---

## 故障排除记录

> 记录配置过程中遇到的问题及解决方案

### 问题 1: Hermes 配置目录误解

**现象**: 修改 `config/config.yaml` 不生效，Hermes 仍使用默认配置。

**原因**: Hermes Agent 镜像的配置目录是 `/opt/data/`，而非 `/root/.hermes/`。

**解决**: 创建 `config/hermes-config.yaml` 挂载到 `/opt/data/config.yaml`：
```yaml
# docker-compose.yml
volumes:
  - ./config/hermes-config.yaml:/opt/data/config.yaml:ro
```

---

### 问题 2: 腾讯云 GLM-5 配置

**现象**: 使用 `HERMES_PROVIDER=openai` + `OPENAI_BASE_URL` 调用腾讯云 GLM-5 失败，报 401 错误。

**原因**: 
1. Hermes 内置的 `zai` provider 连接智谱官方 API，不适用于腾讯云托管端点
2. 需要使用 `custom` provider 指定自定义端点

**解决**: 
```yaml
# config/hermes-config.yaml
model:
  default: "glm-5"
  provider: "custom"
  base_url: "https://api.lkeap.cloud.tencent.com/coding/v3"
```

```env
# .env
HERMES_PROVIDER=custom
HERMES_MODEL=glm-5
OPENAI_API_KEY=sk-sp-xxx  # custom provider 使用 OPENAI_API_KEY
```

---

### 问题 3: Docker 终端后端兼容性

**现象**: 终端工具执行失败，报错 `exit status 125`。

**原因**: Hermes Docker 终端使用大量安全参数（`--cap-drop`, `--security-opt`, `--pids-limit` 等），在 Docker Desktop 环境下不兼容。

**解决**: 改用 `local` 终端后端：
```yaml
# config/hermes-config.yaml
terminal:
  backend: local
  timeout: 300
```

> ⚠️ 生产环境应使用 Docker 后端以获得更好隔离性。

---

### 问题 4: 环境变量命名

**现象**: 设置 `HERMES_PROVIDER` 不生效。

**原因**: Hermes 内部使用 `HERMES_INFERENCE_PROVIDER`，但 `hermes config set` 命令会正确处理。

**解决**: 通过挂载配置文件直接覆盖，而非依赖环境变量：
```yaml
# config/hermes-config.yaml
model:
  provider: "custom"
```

---

### 问题 5: 从容器提取文件

**现象**: Excel 文件生成在容器内，本地无法访问。

**解决**: 使用 `docker cp` 提取：
```bash
docker cp hermes-agent:/tmp/sales.xlsx ./data/sales.xlsx
```

---

## 安全警告

> ⚠️ **当前版本为 MVP 阶段，生产环境不可部署**

### 已知安全限制

| 限制项 | 说明 | 风险等级 |
|--------|------|----------|
| local 终端无沙箱 | Agent 执行的代码无进程隔离 | 🔴 Critical |
| 无认证机制 | API 无身份验证 | 🟡 Medium |
| SQLite 数据隔离仅逻辑隔离 | 路径白名单可被绕过 | 🟡 Medium |

### 已实施的安全措施

| 措施 | 说明 |
|------|------|
| Docker Socket 移除 | Agent 容器无 Docker 权限 |
| Prompt 转义 | 使用 `shlex.quote()` 防止命令注入 |
| 执行超时 | 300s 强制终止 |

### 生产部署前必须解决

- [ ] 实现 Docker 终端后端或 gVisor 沙箱
- [ ] 添加 API 认证机制
- [ ] 实现路径白名单强制校验