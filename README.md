# Hermes Assistant

> 基于 Hermes Agent 的企业级智能助手

## 项目简介

利用 Hermes Agent 的自主代理能力，为企业提供智能化工作助手。支持两种使用场景：

### 场景一：企业微信 Bot + 金蝶 ERP 集成

用户在企业微信中向 Bot 发送自然语言指令，系统自动调用金蝶云 ERP API 完成业务操作。

**典型用例**：
- 查询物料库存："查询物料 M001 的库存"
- 创建销售订单："给客户 C001 创建销售订单，产品 P001，数量 100"
- 查询客户信息："查询客户 C001 的基本信息"

### 场景二：本地文件处理

用户通过 **Web UI** 或 API 上传文件并发送自然语言指令，系统自动完成数据清洗、汇总、分析或内容提取。

**支持文件格式**: Excel (.xlsx/.xls)、Word (.docx/.doc)、PPT (.pptx/.ppt)、PDF、CSV、JSON、TXT、图片等

### 核心价值

| 价值维度 | 说明 | 预期收益 |
|----------|------|----------|
| 效率提升 | 自动化处理替代手工 | 节省 60%+ 时间 |
| 技能门槛降低 | 自然语言交互 | 人人可用 |
| 错误减少 | Agent 标准化处理 | 减少 80% 人为失误 |
| 隐私安全 | 本地化部署，数据不出本机 | 零泄露风险 |

---

## 项目状态

### 阶段划分

| 阶段 | 状态 | 说明 |
|------|------|------|
| **Phase 1: PoC 验证** | ✅ 完成 | 技术可行性验证 |
| **Phase 2: 产品化 MVP** | ✅ 完成 | Web UI + 安全加固 + 本地存储 |
| **Phase 3: 功能增强** | ✅ 完成 | 批量处理 + 模板系统 + 结果预览 |
| **Phase 4: 生产就绪** | ✅ 完成 | 企微集成 + 金蝶 ERP + 运维体系 |

### Phase 2 完成内容

- ✅ **安全止血**: Agent 容器移除 Docker Socket，Prompt 参数转义
- ✅ **会话隔离**: 每会话独立目录 + SQLite 数据库
- ✅ **路径白名单**: `validate_path()` 防止目录穿越
- ✅ **命令黑名单**: `validate_prompt()` 拦截危险命令
- ✅ **本地文件存储**: 移除 MinIO，改用本地文件系统
- ✅ **Web UI**: Streamlit 前端，非技术用户可用
- ✅ **思考过程实时显示**: Agent 推理过程可视化
- ✅ **E2E 测试**: Playwright 自动化流程测试

### Phase 3 完成内容

- ✅ **CORS 配置**: 支持跨域请求，便于前端集成
- ✅ **文件大小限制**: 可配置的文件上传大小限制（默认 50MB）
- ✅ **批量处理**: 多文件并行处理，进度追踪，结果打包下载
- ✅ **处理模板**: 8 个预设模板（数据清洗、格式转换、内容提取等）
- ✅ **结果预览**: Excel/CSV 表格预览、图片预览、文本预览
- ✅ **批量结果打包**: ZIP 格式一键下载所有处理结果

### Phase 4 完成内容

- ✅ **企业微信集成**: WeChat Gateway 消息接收入口
- ✅ **金蝶 ERP 集成**: MCP Server 封装金蝶云 API
- ✅ **Skills 模板系统**: 可复用的业务技能模板（查询物料、创建订单等）
- ✅ **缓存机制**: LRU 缓存 + TTL 过期，提升查询性能
- ✅ **连接池管理**: 连接复用 + 健康检查
- ✅ **审计日志**: 完整操作审计追踪
- ✅ **运维体系**: 部署指南 + 故障排除 + 监控告警
- ✅ **多租户设计**: 租户隔离架构设计
- ✅ **高可用设计**: 主备部署 + 故障转移方案

### 路线选择

> **决策日期**: 2026-05-15

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 技术路线 | ✅ 本地化部署 | 无需企微权限，降低验证门槛 |
| 文件存储 | ✅ 本地文件系统 | 简化架构，放弃 MinIO |
| 沙箱方案 | ✅ local + SQLite 隔离 | 会话级数据隔离，路径白名单 |
| LLM 配置 | ✅ 用户自定义 | 用户自行配置 API Key 和 Provider |
| 用户界面 | ✅ Streamlit Web UI | 非技术用户友好 |

---

## 架构概览

### 企业微信 + 金蝶 ERP 集成架构

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
                                                │  金蝶云 ERP      │
                                                │  (业务系统)      │
                                                └─────────────────┘
```

### 本地文件处理架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户交互层                              │
│   ┌──────────────┐        ┌────────────────────────────┐    │
│   │  Streamlit   │        │     REST API / Swagger     │    │
│   │   Web UI     │        │      调试与测试界面         │    │
│   │  (port 8501) │        │                            │    │
│   └──────────────┘        └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                        服务层                                │
│   ┌──────────────────┐  ┌─────────────────┐                 │
│   │  Hermes Bridge   │  │ Session Manager │                 │
│   │  - 任务接收 API  │  │  - 会话创建/删除│                 │
│   │  - Agent 通信    │  │  - 路径白名单   │                 │
│   │  - 结果返回      │  │  - 命令黑名单   │                 │
│   └────────┬─────────┘  └─────────────────┘                 │
│            │                                                 │
│            ▼                                                 │
│   ┌──────────────────┐                                      │
│   │  Hermes Agent    │                                      │
│   │  - LLM 推理      │                                      │
│   │  - local 终端    │                                      │
│   │  - Skills & 内存 │                                      │
│   └──────────────────┘                                      │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                      基础设施层                              │
│   ┌──────────┐    ┌──────────────────┐    ┌──────────────┐   │
│   │  Docker  │    │  本地文件系统     │    │  Prometheus  │   │
│   │  Engine  │    │  data/sessions/  │    │   监控告警   │   │
│   └──────────┘    └──────────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

**企业微信 + 金蝶 ERP 场景**：

```
企微消息 → WeChat Gateway (8001) → Hermes Bridge (8000) → MCP Server (8080) → 金蝶 ERP API
                                                                          │
                                                                          ▼
企微用户 ← 消息回复 ←────────────────────────────────────────────────── 业务结果
```

**本地文件处理场景**：

```
用户 → Web UI (8501) → Hermes Bridge (8646) → docker exec → Hermes Agent
                                                          │
                                                          ▼
                                                   LLM 推理 + 工具调用
                                                          │
                                                          ▼
用户 ← 结果文件 ← 本地文件系统 ← data/sessions/{session_id}/outputs/
```

### 会话隔离架构

```
data/sessions/
├── sess_abc123/              # 会话目录
│   ├── workspace.db          # SQLite 数据库
│   ├── uploads/              # 上传文件
│   │   └── input.xlsx
│   └── outputs/              # 输出文件
│       └── result.xlsx
└── sess_def456/
    ├── workspace.db
    ├── uploads/
    └── outputs/
```

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | Hermes Agent | NousResearch/hermes-agent |
| 任务桥接 | Hermes Bridge | FastAPI 本地 REST API |
| Web UI | Streamlit | Python 前端框架 |
| 会话管理 | Session Manager | 会话隔离 + 安全验证 |
| 文件存储 | 本地文件系统 | data/sessions/ 目录 |
| 容器化 | Docker Compose | 服务编排 |
| 监控 | Prometheus | 指标采集告警 |

---

## 快速开始

### 前置条件

- Docker & Docker Compose
- LLM API Key（OpenRouter / OpenAI / 自定义兼容端点）
- 金蝶云 ERP 账号（用于 ERP 集成）
- 企业微信管理员权限（用于 Bot 配置，可选）

### 1. 克隆项目

```bash
git clone https://github.com/null-characters/Hermes_Work_Assistant.git
cd Hermes_Work_Assistant
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，配置必要参数
vim .env
```

#### 必填配置

**LLM API（三选一）**：

```env
# 方式 1: OpenRouter
HERMES_PROVIDER=openrouter
HERMES_MODEL=anthropic/claude-3-sonnet
OPENROUTER_API_KEY=sk-or-xxx

# 方式 2: OpenAI 兼容自定义端点
# HERMES_PROVIDER=openai
# OPENAI_API_KEY=your-api-key
# OPENAI_BASE_URL=https://your-custom-url/v1
# HERMES_MODEL=your-model-name

# 方式 3: 其他提供商
# DEEPSEEK_API_KEY / GLM_API_KEY / KIMI_API_KEY 等
```

**金蝶 ERP 配置**：

```env
# 金蝶云 ERP（账号密码登录）
KINGDEE_API_URL=http://your-kingdee-server/K3Cloud
KINGDEE_ACCT_ID=your_acct_id
KINGDEE_USERNAME=your_username
KINGDEE_PASSWORD=your_password
KINGDEE_LCID=2052
```

**企业微信配置（可选）**：

```env
# 企业微信 Bot
WECHAT_CORP_ID=your_corp_id
WECHAT_AGENT_ID=your_agent_id
WECHAT_SECRET=your_secret
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_aes_key
```

### 3. 启动服务

```bash
# 启动所有服务
docker compose up -d

# 查看状态
docker compose ps
```

### 4. 验证服务

```bash
# 健康检查
curl -s http://localhost:8000/health      # Hermes Bridge
curl -s http://localhost:8001/health      # WeChat Gateway
curl -s http://localhost:8080/metrics     # MCP Server
curl -s http://localhost:8501/_stcore/health  # Web UI
```

### 5. 企业微信 Bot 配置（可选）

在企业微信管理后台：

1. **创建应用**：应用管理 → 自建应用 → 创建
2. **获取凭证**：记录 `AgentId` 和 `Secret`
3. **设置回调**：
   - 回调 URL：`https://your-domain/wechat/callback`
   - 设置 `Token` 和 `EncodingAESKey`
4. **配置可信域名**：添加你的服务器域名

### 6. 使用方式

#### 方式一：企业微信 Bot（推荐）

在企业微信中向 Bot 发送自然语言指令：

```
查询物料 M001 的库存
```

```
给客户 C001 创建销售订单，产品 P001，数量 100
```

```
查询客户 C001 的基本信息
```

#### 方式二：Web UI

打开浏览器访问: **http://localhost:8501**

**两种使用模式**：

1. **文件处理模式**：
   - 上传文件（支持 Excel/Word/PPT/PDF/CSV/JSON/TXT/图片等）
   - 输入自然语言指令（如：将第一列数据按升序排序）
   - 点击"执行"按钮
   - 等待处理完成，查看 Agent 响应
   - 下载结果文件

2. **直接对话模式**（无需上传文件）：
   - 直接在指令框输入问题（如：在 Excel 中如何快速求和？）
   - 点击"执行"按钮
   - 查看 Agent 响应内容

### 6. API 方式（可选）

```bash
# 健康检查
curl http://localhost:8646/health

# 提交文本任务
curl -X POST http://localhost:8646/api/task/submit \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，请介绍一下你自己"}'

# 处理文件（流式响应，实时显示思考过程）
curl -N -X POST http://localhost:8646/api/excel/stream \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/sessions/sess_xxx/uploads/input.xlsx",
    "task": "将第一列数据按升序排序",
    "session_id": "sess_xxx"
  }'

# 直接对话（无需文件）
curl -N -X POST http://localhost:8646/api/excel/stream \
  -H "Content-Type: application/json" \
  -d '{
    "task": "在 Excel 中如何快速将二维数据表转换为柱状图？",
    "session_id": "sess_xxx"
  }'

# 非流式 API（等待完成后返回结果）
curl -X POST http://localhost:8646/api/task/excel \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/sessions/sess_xxx/uploads/input.xlsx",
    "task": "将第一列数据按升序排序",
    "session_id": "sess_xxx"
  }'
```

### 流式 API 事件类型

| 事件类型 | 说明 | 示例 |
|----------|------|------|
| `thinking` | Agent 思考过程 | `💭 让我先检查一下这个Excel文件...` |
| `tool` | 工具准备/执行 | `🔧 准备工具: terminal` |
| `tool_result` | 工具执行结果 | `✅ 工具 1 完成 (0.46s)` |
| `api_call` | API 调用信息 | `🌐 API 调用 #1: glm-5` |
| `response` | Agent 响应内容 | `🤖 已完成排序...` |
| `done` | 任务完成 | `🎉 任务完成` |

---

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| **Web UI** | **8501** | Streamlit 前端界面 |
| Hermes Bridge | 8000 | Agent 调度 API |
| WeChat Gateway | 8001 | 企微消息接收 |
| MCP Server | 8080 | 金蝶 ERP 工具服务 |
| Prometheus | 9090 | 监控面板 |

---

## 项目结构

```
Hermes_Work_Assistant/
├── docker-compose.yml          # 服务编排
├── .env.example                # 环境变量模板
├── README.md                   # 项目说明
├── config/
│   ├── hermes-config.yaml      # Hermes 配置
│   ├── USER.md                 # Agent 角色设定
│   ├── mcp_servers.yaml        # MCP Server 配置
│   └── skills/                 # 技能定义
│       ├── README.md           # Skills 使用说明
│       └── erp_operations.yaml # ERP 操作技能模板
├── services/
│   ├── web-ui/                 # Streamlit Web UI
│   │   ├── Dockerfile
│   │   ├── app.py              # 主入口
│   │   ├── components/
│   │   │   ├── task_runner.py  # 任务执行
│   │   │   └── downloader.py   # 文件下载
│   │   ├── pages/
│   │   │   ├── config.py       # LLM 配置
│   │   │   └── history.py      # 历史记录
│   │   └── requirements.txt
│   ├── hermes-bridge/          # Agent 桥接服务
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── routers/task.py
│   │   │   └── services/hermes_client.py
│   │   └── requirements.txt
│   ├── wechat-gateway/         # 企业微信网关 (Phase 4)
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   └── routers/callback.py
│   │   └── requirements.txt
│   ├── kingdee-mcp-server/     # 金蝶 MCP Server (Phase 4)
│   │   ├── Dockerfile
│   │   ├── src/kingdee_mcp_server/
│   │   │   ├── server.py       # MCP 服务入口
│   │   │   ├── kingdee_client.py # 金蝶 API 客户端
│   │   │   ├── skills.py       # Skills 注册执行
│   │   │   ├── cache.py         # LRU 缓存
│   │   │   └── audit_logger.py  # 审计日志
│   │   ├── tests/              # 单元测试
│   │   └── pyproject.toml
│   └── session_manager/       # 会话管理模块
│       ├── manager.py          # 会话创建/删除
│       ├── validators.py       # 路径/命令验证
│       ├── storage.py          # 文件存储
│       └── schema.sql          # SQLite Schema
├── tests/
│   ├── e2e/                    # E2E 测试
│   │   └── test_web_ui.py      # Playwright 测试
│   ├── session_manager/        # 会话管理测试
│   │   └── test_validators.py
│   └── test_storage_chain.py   # 存储链路测试
├── data/
│   ├── sessions/               # 会话数据目录
│   │   └── sess_xxx/
│   │       ├── workspace.db
│   │       ├── uploads/
│   │       └── outputs/
│   └── audit/                  # 审计日志目录
│       └── audit-*.jsonl
├── nginx/                      # 反向代理配置
├── prometheus/                 # 监控配置
└── docs/
    ├── LOCAL_DEV_GUIDE.md      # 本地开发指南
    ├── ops/                    # 运维文档 (Phase 4)
    │   ├── deployment-guide.md
    │   └── troubleshooting-guide.md
    ├── design/                 # 设计文档
    ├── plan/                   # 规划文档
    └── tasks/                  # 任务清单
```

---

## API 参考

### Hermes Bridge API (`:8646`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/task/submit` | POST | 提交文本任务 |
| `/api/task/excel` | POST | 处理文件（向后兼容） |
| `/api/task/status` | GET | Agent 状态 |

### 文件处理 API 请求格式

```json
{
  "file_path": "/app/data/sessions/{session_id}/uploads/{filename}",
  "task": "自然语言处理指令",
  "session_id": "sess_xxx",
  "output_dir": "/app/data/sessions/{session_id}/outputs"
}
```

> `file_path` 为可选字段，不传时直接将 `task` 作为指令发送给 Agent，适用于纯对话场景。

### 流式响应格式

```json
{"type": "thinking", "content": "💭 让我分析一下这个文件..."}
{"type": "tool", "content": "🔧 准备工具: terminal"}
{"type": "api_call", "content": "🌐 API 调用 #1: glm-5"}
{"type": "tool_result", "content": "✅ 工具 1 完成 (0.46s)"}
{"type": "response", "content": "🤖 已完成处理..."}
{"type": "done", "content": "🎉 任务完成", "output_file": "result.xlsx"}
```

---

## 测试

### E2E 测试

```bash
# 安装 Playwright
pip install playwright pytest-playwright
playwright install chromium

# 运行 E2E 测试
python tests/e2e/test_web_ui.py
```

### 单元测试

```bash
# 会话管理测试
python -m pytest tests/session_manager/ -v

# 存储链路测试
python tests/test_storage_chain.py
```

---

## 安全设计

### 已实现安全措施

| 安全项 | 措施 | 状态 |
|--------|------|------|
| Docker 权限隔离 | Agent 容器移除 Docker Socket | ✅ |
| 命令注入防护 | `shlex.quote()` 转义 Prompt | ✅ |
| 路径穿越防护 | `validate_path()` 白名单校验 | ✅ |
| 危险命令拦截 | `validate_prompt()` 黑名单 | ✅ |
| 会话数据隔离 | 独立目录 + SQLite 数据库 | ✅ |
| 执行超时 | 300s 强制终止 | ✅ |
| 容器资源限制 | CPU 1核 / 内存 2GB | ✅ |

### 安全警告

> ⚠️ **当前版本为 MVP 阶段，生产环境需额外加固**

| 限制项 | 说明 | 风险等级 |
|--------|------|----------|
| local 终端无沙箱 | Agent 执行的代码无进程隔离 | 🟡 Medium |
| 无认证机制 | API 无身份验证 | 🟡 Medium |

### 生产部署前建议

- [ ] 实现 Docker 终端后端或 gVisor 沙箱
- [ ] 添加 API 认证机制
- [ ] 添加 HTTPS 支持

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [本地开发指南](./docs/LOCAL_DEV_GUIDE.md) | 快速启动、API 使用、故障排除 |
| [部署指南](./docs/ops/deployment-guide.md) | 生产环境部署步骤 |
| [故障排除指南](./docs/ops/troubleshooting-guide.md) | 常见问题与解决方案 |
| [企业微信配置](./docs/wecom_setup_guide.md) | 企微 Bot 配置步骤 |
| [会话隔离设计](./docs/design/session-isolation.md) | 架构设计文档 |
| [Skills 使用说明](./config/skills/README.md) | 技能模板定义与使用 |
| [总体规划](./docs/plan/Hermes_WeCom_Excel_Assistant_MVP.md) | MVP 规划方案 |
| [ERP 架构规划](./docs/plan/Hermes_ERP_Architecture_Plan.md) | 金蝶 ERP 集成架构 |
| [Phase 1 任务](./docs/tasks/phase1/) | PoC 阶段任务清单 |
| [Phase 2 任务](./docs/tasks/phase2/) | 产品化阶段任务清单 |
| [Phase 3 规划](./docs/workitems/Phase3规划/) | 功能增强阶段规划与任务清单 |
| [Phase 4 任务](./docs/tasks/phase4/) | 生产就绪阶段任务清单 |
| [多租户设计](./docs/tasks/phase4/multi_tenant_design.md) | 多租户隔离架构设计 |
| [高可用设计](./docs/tasks/phase4/high_availability_design.md) | 主备部署与故障转移 |
| [部署检查清单](./docs/tasks/phase4/deployment_checklist.md) | 生产部署验收清单 |
| [Phase 3 代码评审](./docs/workitems/Phase3规划/code-review-report.md) | 五轴代码评审报告 |
| [评审报告](./docs/workitems/规划评审分析/) | 双视角评审分析 |

---

## 许可证

MIT License

---

## 贡献

欢迎提交 Issue 和 Pull Request。
