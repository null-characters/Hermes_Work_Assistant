# Kingdee MCP Server

MCP Server for Kingdee Cloud Galaxy ERP integration.

## Installation

```bash
cd services/kingdee-mcp-server
pip install -e ".[dev]"
```

## Configuration

1. Copy `.env.example` to `.env`
2. Fill in your Kingdee API credentials

## Running

```bash
python -m kingdee_mcp_server.server
```

## Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python -m kingdee_mcp_server.server
```

## Available Tools

| Tool | Description |
|------|-------------|
| `query_erp_data` | Query data from Kingdee ERP |
| `create_erp_bill` | Create and submit a bill |
| `upload_erp_attachment` | Upload attachment to a bill |

## Security

- Credentials are loaded from `.env` only
- No credentials in logs or responses
- `.env` is excluded from git