# 企业微信集成配置指南

## 1. 创建自建应用

### 1.1 登录企业微信管理后台

访问 https://work.weixin.qq.com/ 并使用管理员账号登录。

### 1.2 创建应用

1. 进入「应用管理」→「自建应用」
2. 点击「创建应用」
3. 填写应用信息：
   - 应用名称：Excel 助手
   - 应用Logo：上传图标
   - 可见范围：选择部门/人员

### 1.3 获取应用凭证

创建完成后，记录以下信息：

```
AgentId: 1000002
Secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 2. 配置回调 URL

### 2.1 个人测试方案（内网穿透）

> ⚠️ **注意**：此方案仅适用于个人开发测试，生产环境请使用正式域名和公网服务器。

如果你没有公网服务器和域名，可以使用内网穿透工具将本地服务暴露到公网。

#### 使用 ngrok

```bash
# 1. 安装 ngrok
brew install ngrok

# 2. 启动 Hermes 服务
docker compose up -d

# 3. 穿透 WeChat Gateway 端口（8001）
ngrok http 8001

# 4. 获得公网地址（类似）
# Session Status                online
# Forwarding                    https://a1b2c3d4.ngrok-free.app -> http://localhost:8001
```

#### 填写回调 URL

将 ngrok 提供的地址填写到企微后台：

```
https://a1b2c3d4.ngrok-free.app/wechat/callback
```

#### ngrok 注意事项

| 项目 | 说明 |
|------|------|
| URL 变化 | 免费版每次重启 ngrok 会生成新 URL，需重新配置企微回调 |
| 速率限制 | 免费版有连接数和速率限制 |
| HTTPS | ngrok 自动提供 HTTPS，无需额外配置证书 |
| 稳定性 | 长时间运行可能断开，建议配合 `--session` 参数 |

#### 其他穿透工具

| 工具 | 特点 | 地址 |
|------|------|------|
| ngrok | 免费、稳定、易用 | ngrok.com |
| frp | 自建服务器、开源、无限制 | github.com/fatedier/frp |
| cloudflare tunnel | 免费、无需注册、稳定 | developers.cloudflare.com |
| cpolar | 国内服务、速度快 | cpolar.com |

#### 使用企微调试工具（推荐测试用）

如果穿透工具不稳定，可以使用企微官方调试工具：

1. 访问：https://open.work.weixin.qq.com/wwopen/devTool
2. 使用「接口调试工具」模拟消息发送和回调验证
3. 无需公网服务器，可验证消息加解密逻辑

**优点**：
- 无需公网服务器
- 无需配置回调 URL
- 可快速验证消息处理逻辑

**限制**：
- 仅用于开发调试
- 无法测试完整端到端流程

### 2.2 生产环境配置回调域名

在应用详情页 → 「企业可信IP」中添加服务器 IP。

### 2.3 配置接收消息

1. 进入「接收消息」→ 「设置 API 接收」
2. 填写回调 URL：
   - **生产环境**：`https://your-domain.com/wechat/callback`
   - **个人测试**：使用 ngrok 地址 + `/wechat/callback`
3. 设置 Token 和 EncodingAESKey（随机生成）
4. 记录以下信息：
   ```
   Token: your-token
   EncodingAESKey: your-43-char-encoding-aes-key
   ```

### 2.4 验证回调

点击保存时，企业微信会发送 GET 请求验证 URL 有效性。

- **生产环境**：确保域名解析正确、HTTPS 证书有效
- **个人测试**：确保 ngrok 正在运行、WeChat Gateway 服务已启动

## 3. 配置企业 ID

在「我的企业」页面获取：

```
CorpID: wwxxxxxxxxxxxxxxxx
```

## 4. 环境变量配置

将以上信息填入 `.env` 文件：

```bash
# 企业微信 Bot 配置
WECHAT_CORP_ID=wwxxxxxxxxxxxxxxxx
WECHAT_AGENT_ID=1000002
WECHAT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_TOKEN=your-token
WECHAT_ENCODING_AES_KEY=your-43-char-encoding-aes-key
```

> **说明**：只需要配置自建应用的 Secret，无需「通讯录同步 Secret」。未认证企业也可正常使用 Bot 功能。

## 5. H5 应用配置（可选）

### 5.1 配置应用首页

在应用详情页 → 「应用主页」设置：

```
https://your-domain.com/static/upload.html
```

### 5.2 配置可信域名

在「网页授权及JS-SDK」中添加：

```
your-domain.com
```

## 6. 测试验证

### 6.1 验证服务状态

```bash
# 检查服务
docker compose ps

# 查看日志
docker compose logs -f hermes
```

### 6.2 发送测试消息

在企业微信应用中发送：

```
你好
```

检查 Hermes 日志是否收到消息。

## 7. 常见问题

### Q: 回调 URL 验证失败

检查：
1. 域名是否正确解析
2. HTTPS 证书是否有效
3. 防火墙是否开放 443 端口

### Q: 消息发送失败

检查：
1. CorpID/Secret 是否正确
2. AgentId 是否匹配
3. 用户是否在可见范围内

### Q: 文件上传失败

检查：
1. MinIO 服务是否正常
2. 环境变量配置是否正确
3. 网络连接是否正常

## 版本
v1.1.0 - 新增个人测试方案（内网穿透）