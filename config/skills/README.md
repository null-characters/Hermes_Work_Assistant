# ERP Operations Skills 使用指南

## 概述

Skills 是可复用的 ERP 操作模板，用于简化常见业务流程的执行。

## Skills 列表

| Skill | 描述 | 触发示例 |
|-------|------|----------|
| `query_material_stock` | 查询物料库存 | "查询物料 M001 的库存" |
| `create_sales_order` | 创建销售订单 | "创建销售订单给客户 C001" |
| `query_customer_info` | 查询客户信息 | "查询客户 C001 的信息" |

## 调用方式

### 1. 自然语言触发

```
用户: 查询物料 M001 的库存
Agent: [自动匹配 query_material_stock Skill]
       物料 M001 库存信息：
       - 仓库: 原材料仓
         数量: 100 个
```

### 2. 显式调用

```python
from skills import SkillRegistry

registry = SkillRegistry()
result = registry.execute("query_material_stock", {
    "material_number": "M001"
})
```

## 参数映射

Skills 支持从以下来源提取参数：

1. **对话上下文**: 从之前的对话中提取
2. **用户输入**: 从当前用户消息中提取
3. **默认值**: 从配置中获取默认值

## 学习机制

当同一操作执行 3 次以上时，系统会自动建议创建新 Skill：

```
检测到您多次执行"查询供应商价格"操作，
是否创建 Skill 以便复用？
```

## 扩展 Skills

在 `config/skills/erp_operations.yaml` 中添加新 Skill：

```yaml
skills:
  my_new_skill:
    name: "我的新技能"
    description: "技能描述"
    trigger:
      patterns:
        - "触发模式1"
        - "触发模式2"
      entities:
        - param1
        - param2
    steps:
      - action: "query_erp_data"
        params:
          form_id: "YOUR_FORM_ID"
          # ...
    output_template: |
      输出模板
```
