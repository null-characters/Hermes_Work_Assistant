# 生产环境部署检查清单

## 部署前检查

### 1. 配置检查

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 环境变量完整性 | `cat .env \| grep -E "KINGDEE|HERMES|WECHAT"` | 所有必需变量已设置 |
| 配置文件语法 | `python -c "import yaml; yaml.safe_load(open('config/mcp_servers.yaml'))"` | 无错误 |
| Secrets 配置 | `echo $KINGDEE_APP_SECRET \| wc -c` | 长度 > 16 |
| 端口配置 | `grep -E "PORT|8000|8001|8080" .env` | 无冲突 |

### 2. 安全检查

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| TLS 证书 | `openssl x509 -in ssl/cert.pem -noout -dates` | 有效期内 |
| 凭证加密 | `grep -r "password" config/` | 无明文密码 |
| 网络隔离 | `docker network inspect hermes-internal` | internal=true |
| 文件权限 | `ls -la data/ audit/` | 600/700 |

### 3. 资源检查

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| Docker 版本 | `docker --version` | >= 20.10 |
| 内存可用 | `free -h` | >= 4GB |
| 磁盘可用 | `df -h /app/data` | >= 10GB |
| CPU 核心 | `nproc` | >= 4 |

## 部署执行

### 自动化部署脚本

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

echo "=== Hermes 部署脚本 ==="

# 1. 配置检查
echo "[1/6] 配置检查..."
python scripts/check_config.py

# 2. 安全检查
echo "[2/6] 安全检查..."
python scripts/check_security.py

# 3. 构建镜像
echo "[3/6] 构建镜像..."
docker-compose build --no-cache

# 4. 启动服务
echo "[4/6] 启动服务..."
docker-compose up -d

# 5. 健康检查
echo "[5/6] 健康检查..."
sleep 30
python scripts/check_health.py

# 6. 验证功能
echo "[6/6] 功能验证..."
python scripts/smoke_test.py

echo "=== 部署完成 ==="
```

### 手动部署步骤

```bash
# 1. 拉取代码
git pull origin main

# 2. 配置环境
cp .env.example .env
vim .env

# 3. 构建镜像
docker-compose build

# 4. 启动服务
docker-compose up -d

# 5. 检查状态
docker-compose ps
docker-compose logs -f --tail=50
```

## 部署后验证

### 1. 功能验证

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 服务健康 | `curl -s http://localhost:8000/health` | {"status": "healthy"} |
| MCP 可访问 | `curl -s http://localhost:8080/metrics` | Prometheus 指标 |
| 网关响应 | `curl -s http://localhost:8001/health` | {"status": "ok"} |
| Web UI | `curl -s http://localhost:8501/_stcore/health` | {"status": "ok"} |

### 2. 性能验证

```bash
# 性能测试脚本
python scripts/performance_test.py --duration 60 --concurrency 10

# 预期结果
# - P95 延迟 < 5s
# - 错误率 < 1%
# - 缓存命中率 > 50%
```

### 3. 日志验证

```bash
# 检查错误日志
docker-compose logs | grep -i "error\|exception\|failed" | tail -20

# 检查审计日志
ls -la data/audit/
cat data/audit/*.jsonl | head -5
```

### 4. 监控验证

```bash
# Prometheus 指标
curl -s http://localhost:8080/metrics | grep -E "erp_query_count|cache_hit_rate"

# Grafana Dashboard
curl -s http://localhost:3000/api/dashboards/home
```

## 自动化检查脚本

```python
#!/usr/bin/env python
# scripts/check_health.py

import requests
import sys

SERVICES = {
    "hermes-bridge": "http://localhost:8000/health",
    "wechat-gateway": "http://localhost:8001/health",
    "mcp-server": "http://localhost:8080/metrics",
    "web-ui": "http://localhost:8501/_stcore/health",
}

def check_service(name: str, url: str) -> bool:
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print(f"✅ {name}: healthy")
            return True
        else:
            print(f"❌ {name}: status {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def main():
    results = []
    for name, url in SERVICES.items():
        results.append(check_service(name, url))
    
    if all(results):
        print("\n=== 所有服务健康 ===")
        sys.exit(0)
    else:
        print("\n=== 服务检查失败 ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## 回滚流程

```bash
# 1. 停止当前版本
docker-compose down

# 2. 恢复上一版本镜像
docker tag hermes-mcp-server:previous hermes-mcp-server:latest

# 3. 重新启动
docker-compose up -d

# 4. 验证回滚
python scripts/check_health.py
```

## 验收清单

### 部署前

- [ ] 环境变量完整
- [ ] 配置文件正确
- [ ] 安全检查通过
- [ ] 资源充足

### 部署后

- [ ] 所有服务健康
- [ ] 功能测试通过
- [ ] 性能达标
- [ ] 日志正常
- [ ] 监控正常

### 运维准备

- [ ] 告警规则配置
- [ ] 备份脚本部署
- [ ] 回滚流程验证
- [ ] 运维手册更新