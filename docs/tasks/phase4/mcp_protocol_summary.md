# MCP 协议要点总结

> 来源：Model Context Protocol 官方文档
> 调研日期：2026-05-18
> 用途：ST-001 验收文档

---

## 1. 核心架构

### Server-Client 模型

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  MCP Host   │ ───▶ │ MCP Client  │ ───▶ │ MCP Server  │
│ (AI 应用)   │      │ (连接管理)   │      │ (数据提供者) │
└─────────────┘      └─────────────┘      └─────────────┘
```

| 角色 | 职责 |
|------|------|
| **Host** | AI 应用程序（Claude Desktop、VS Code），协调 Client |
| **Client** | 维护与 Server 的连接，获取上下文 |
| **Server** | 提供 context 数据，可运行在本地或远程 |

---

## 2. 传输层协议

| 传输方式 | 适用场景 | 特点 |
|----------|----------|------|
| **Stdio** | 本地进程通信 | 无网络开销，性能最优 |
| **Streamable HTTP** | 远程服务器 | 支持 OAuth 认证、SSE 流式 |

**本项目选择**: Stdio（本地部署，性能优先）

---

## 3. 核心原语

### 服务器端原语

| 原语 | 用途 | 方法 |
|------|------|------|
| **Tools** | AI 可调用的可执行函数 | `tools/list`, `tools/call` |
| **Resources** | 提供上下文的数据源 | `resources/list`, `resources/read` |
| **Prompts** | 可复用的交互模板 | `prompts/list`, `prompts/get` |

### 本项目使用的原语

- **Tools**: `query_erp_data`, `create_erp_bill`, `upload_erp_attachment`
- **Resources**: 暂不使用（简化实现）
- **Prompts**: 暂不使用（简化实现）

---

## 4. Tool 定义规范

### Schema 结构

```json
{
  "name": "query_erp_data",
  "title": "Query ERP Data",
  "description": "查询金蝶 ERP 数据",
  "inputSchema": {
    "type": "object",
    "properties": {
      "form_id": { "type": "string" },
      "filter_string": { "type": "string" },
      "field_keys": { "type": "array", "items": { "type": "string" } },
      "limit": { "type": "integer", "default": 100 }
    },
    "required": ["form_id"]
  }
}
```

### 调用流程

```
1. tools/list → 发现可用工具
2. tools/call → 执行指定工具
3. 返回结果（JSON 格式）
```

---

## 5. 生命周期管理

```
初始化握手
    │
    ▼
客户端: initialize 请求（协议版本、能力声明）
    │
    ▼
服务器: 返回能力协商结果
    │
    ▼
客户端: notifications/initialized
    │
    ▼
正常通信（发现原语、执行操作）
    │
    ▼
连接终止
```

---

## 6. Python SDK 信息

| 项目 | 详情 |
|------|------|
| **稳定版本** | v1.27.1 |
| **发布日期** | 2026-05-08 |
| **安装命令** | `pip install "mcp[cli]"` 或 `uv add "mcp[cli]"` |
| **API 稳定性** | ✅ v1.x 稳定，推荐生产使用 |

### 基本使用

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Kingdee ERP MCP Server")

@mcp.tool()
def query_erp_data(form_id: str, filter_string: str = "", limit: int = 100) -> dict:
    """查询金蝶 ERP 数据"""
    # 实现逻辑
    return {"data": [...]}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## 7. 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 传输方式 | Stdio | 本地部署，性能优先 |
| 原语类型 | Tools only | 简化实现，满足需求 |
| SDK 版本 | v1.27.1 | 稳定版，生产就绪 |
| 运行模式 | CLI 启动 | 便于调试和集成 |

---

## 8. 参考资源

- 官方文档: https://modelcontextprotocol.io/
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- API 文档: https://modelcontextprotocol.github.io/python-sdk/api/
