#!/usr/bin/env python3
"""
直接测试金蝶 SDK 查询功能
"""
import sys
import os

# 添加 SDK 路径
sys.path.insert(0, os.path.expanduser("~/git_prj/kingdee_webapi_sdk"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from kingdee_sdk.client import KingdeeClient
from kingdee_sdk.auth import AuthType

# 配置
config = {
    "server_url": "http://192.168.0.200/K3Cloud",
    "acct_id": "668f7c152248a3",
    "username": "冯冰",
    "password": "888888",
    "lcid": 2052
}

print("=" * 60)
print("直接测试金蝶 SDK 查询")
print("=" * 60)

# 创建客户端
client = KingdeeClient(
    server_url=config["server_url"],
    acct_id=config["acct_id"],
    username=config["username"],
    password=config["password"],
    lcid=config["lcid"],
    auth_type=AuthType.PASSWORD,
    auto_login=True,
)

print("\n[1] 测试登录...")
print(f"    服务器: {config['server_url']}")
print(f"    账套: {config['acct_id']}")
print(f"    用户: {config['username']}")

# 查询物料
print("\n[2] 查询物料 (BD_MATERIAL)...")
print("    过滤条件: FNumber like '%1.LA%'")

result = client.execute_bill_query(
    form_id="BD_MATERIAL",
    field_keys="FNumber,FName,FSpecification,FMaterialId",  # 使用 FMaterialId 而非 FId
    filter_string="FNumber like '%1.LA%'",
    limit=10,
)

print(f"\n[3] 查询结果:")
if result:
    print(f"    找到 {len(result)} 条记录:")
    for i, row in enumerate(result[:5], 1):
        print(f"    {i}. {row}")
else:
    print("    未找到数据")

# 再试试不带过滤条件
print("\n[4] 查询物料 (前10条，无过滤)...")
result2 = client.execute_bill_query(
    form_id="BD_MATERIAL",
    field_keys="FNumber,FName,FMaterialId",
    limit=10,
)

if result2:
    print(f"    找到 {len(result2)} 条记录:")
    for i, row in enumerate(result2[:5], 1):
        print(f"    {i}. {row}")
else:
    print("    未找到数据")

print("\n" + "=" * 60)
print("测试完成")
