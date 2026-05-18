# WeChat Work Gateway

企业微信消息网关，转发消息到 Hermes Agent。

## 功能

- 接收企业微信消息（文本、图片、文件）
- 转发消息到 Hermes Agent 处理
- 发送 Agent 响应到企业微信

## 配置

1. 在企业微信管理后台创建应用
2. 设置回调 URL：`https://your-domain/callback`
3. 配置环境变量：

```bash
cp .env.example .env
# 编辑 .env 填入企业微信配置
```

## 运行

```bash
# 安装依赖
pip install -e .

# 启动服务
python -m wechat_gateway.main
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | 服务状态 |
| `/callback` | GET/POST | 企业微信回调 |
| `/send` | POST | 发送消息 |

## 测试

```bash
pytest tests/
```