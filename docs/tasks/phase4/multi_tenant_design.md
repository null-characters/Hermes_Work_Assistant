# 多租户隔离设计方案

## 概述

本文档描述 Hermes Work Assistant 的多租户隔离设计，确保不同租户的数据和凭证安全隔离。

## 设计目标

1. **数据隔离**: 租户数据完全隔离，不可跨租户访问
2. **凭证隔离**: 每个租户使用独立的 ERP 凭证
3. **审计分离**: 审计日志按租户分离存储
4. **性能隔离**: 租户间资源使用互不影响

## 架构设计

### 1. 租户 ID 传递机制

```
用户消息 → WeChat Gateway → Hermes Agent → MCP Server → ERP API
    ↓           ↓                ↓              ↓
tenant_id   tenant_id        tenant_id      tenant_id
```

**传递路径**:
1. 企业微信消息携带 corp_id + user_id
2. WeChat Gateway 映射 corp_id → tenant_id
3. Hermes Agent 在 context 中传递 tenant_id
4. MCP Server 根据 tenant_id 选择凭证

### 2. 租户凭证隔离

```yaml
# config/tenants.yaml
tenants:
  tenant_001:
    name: "公司A"
    corp_id: "ww1234567890abcdef"
    erp_config:
      api_url: "https://erp.company-a.com"
      account_id: "A001"
      app_id: "APP_A_001"
      app_secret: "${TENANT_001_SECRET}"  # 从环境变量读取
    
  tenant_002:
    name: "公司B"
    corp_id: "ww0987654321fedcba"
    erp_config:
      api_url: "https://erp.company-b.com"
      account_id: "B001"
      app_id: "APP_B_001"
      app_secret: "${TENANT_002_SECRET}"
```

### 3. MCP Server 多租户支持

```python
# kingdee_mcp_server/tenant_client.py
class TenantClientManager:
    """多租户客户端管理器"""
    
    def __init__(self):
        self._clients: dict[str, KingdeeClient] = {}
        self._tenant_configs: dict[str, TenantConfig] = {}
    
    def get_client(self, tenant_id: str) -> KingdeeClient:
        """获取指定租户的 ERP 客户端"""
        if tenant_id not in self._clients:
            config = self._tenant_configs.get(tenant_id)
            if not config:
                raise ValueError(f"Unknown tenant: {tenant_id}")
            
            self._clients[tenant_id] = KingdeeClient(
                server_url=config.erp_config.api_url,
                acct_id=config.erp_config.account_id,
                app_id=config.erp_config.app_id,
                app_secret=os.getenv(config.erp_config.app_secret_env),
            )
        
        return self._clients[tenant_id]
```

### 4. 审计日志租户分离

```python
# audit_logger.py 多租户支持
class AuditLogger:
    def log_operation(self, tenant_id: str, ...):
        # 按租户分离日志文件
        log_file = self.log_dir / tenant_id / f"{date}.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

**目录结构**:
```
data/audit/
├── tenant_001/
│   ├── 2024-01-01.jsonl
│   └── 2024-01-02.jsonl
├── tenant_002/
│   ├── 2024-01-01.jsonl
│   └── 2024-01-02.jsonl
└── _system/
    └── system_events.jsonl
```

### 5. 缓存租户隔离

```python
# cache.py 多租户支持
class QueryCache:
    def _generate_key(self, tenant_id: str, form_id: str, ...):
        # 缓存键包含租户 ID
        params = {
            "tenant_id": tenant_id,  # 租户隔离
            "form_id": form_id,
            "field_keys": field_keys,
            "filter_string": filter_string,
        }
        return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
```

## 安全措施

### 1. 凭证安全存储

- 凭证不存储在代码中
- 使用环境变量或密钥管理服务（如 AWS Secrets Manager）
- 定期轮换凭证

### 2. 访问控制

```python
# 权限检查中间件
def check_tenant_access(tenant_id: str, user_id: str) -> bool:
    """检查用户是否有权访问租户数据"""
    # 从数据库或缓存获取用户-租户映射
    user_tenants = get_user_tenants(user_id)
    return tenant_id in user_tenants
```

### 3. 数据加密

- 传输层：TLS 1.3
- 存储层：敏感数据加密存储
- 审计日志：敏感字段脱敏

## 部署架构

### 单实例多租户

```
┌─────────────────────────────────────────┐
│           MCP Server Instance            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Tenant 1 │ │Tenant 2 │ │Tenant 3 │   │
│  │ Client  │ │ Client  │ │ Client  │   │
│  └────┬────┘ └────┬────┘ └────┬────┘   │
└───────┼──────────┼──────────┼──────────┘
        │          │          │
        ▼          ▼          ▼
    ┌───────┐  ┌───────┐  ┌───────┐
    │ ERP A │  │ ERP B │  │ ERP C │
    └───────┘  └───────┘  └───────┘
```

### 多实例负载均衡

```
                    ┌─────────────┐
                    │   LB / API  │
                    │   Gateway   │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌───────────┐    ┌───────────┐    ┌───────────┐
    │ Instance 1│    │ Instance 2│    │ Instance 3│
    │ (Stateless)│   │ (Stateless)│   │ (Stateless)│
    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │    Redis    │
                    │   (Cache)   │
                    └─────────────┘
```

## 实施步骤

### Phase 1: 基础隔离 (Week 1)
- [ ] 租户配置文件结构设计
- [ ] TenantClientManager 实现
- [ ] 审计日志租户分离

### Phase 2: 安全加固 (Week 2)
- [ ] 凭证安全存储方案
- [ ] 访问控制中间件
- [ ] 数据加密实现

### Phase 3: 性能优化 (Week 3)
- [ ] 缓存租户隔离
- [ ] 连接池租户隔离
- [ ] 负载测试

## 验收标准

| 标准 | 验证方法 |
|------|----------|
| 数据隔离 | 租户 A 无法访问租户 B 的数据 |
| 凭证隔离 | 租户使用各自的 ERP 凭证 |
| 审计分离 | 审计日志按租户目录存储 |
| 性能隔离 | 单租户负载不影响其他租户 |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 凭证泄露 | 高 | 使用密钥管理服务，定期轮换 |
| 跨租户访问 | 高 | 严格的访问控制检查 |
| 资源争用 | 中 | 租户级资源配额限制 |