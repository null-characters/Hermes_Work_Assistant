#!/usr/bin/env python3
"""
测试 ERP 查询流程
1. 调用 Hermes Agent 查询金蝶 ERP 中的 UM 项目
2. 将结果发送到钉钉群
"""

import asyncio
import httpx
import os
import sys
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()


async def query_hermes(prompt: str, timeout: int = 120) -> dict:
    """调用 Hermes Bridge API"""
    bridge_url = os.getenv("BRIDGE_API_URL", "http://localhost:8646")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{bridge_url}/api/submit",
            json={
                "message": prompt,
                "timeout": timeout
            }
        )
        return response.json()


async def send_to_dingtalk(content: str, title: str = "ERP查询结果") -> dict:
    """发送消息到钉钉群"""
    webhook_url = os.getenv("DINGTALK_WEBHOOK_URL")
    secret = os.getenv("DINGTALK_SECRET")
    
    if not webhook_url:
        raise ValueError("DINGTALK_WEBHOOK_URL 未配置")
    
    # 导入钉钉客户端
    sys.path.insert(0, str(Path(__file__).parent / "services/dingtalk-gateway/src"))
    from dingtalk_gateway.dingtalk_client import DingTalkClient
    
    client = DingTalkClient(webhook_url, secret)
    
    # 发送 Markdown 消息
    return await client.send_markdown(
        title=title,
        content=content,
        at_all=False
    )


async def main():
    print("=" * 60)
    print("测试流程: Hermes Agent -> 金蝶 ERP -> 钉钉")
    print("=" * 60)
    
    # 1. 查询物料（自然语言）
    prompt = "查询物料编号包含 1.LA 的物料"
    print(f"\n[1] 发送查询请求: {prompt}")
    
    try:
        result = await query_hermes(prompt)
        
        if result.get("success"):
            output = result.get("output", "")
            print(f"\n[2] 查询成功!")
            print("-" * 40)
            print(output[:500] + "..." if len(output) > 500 else output)
            print("-" * 40)
            
            # 2. 发送到钉钉
            print("\n[3] 发送结果到钉钉...")
            
            # 构建钉钉消息
            dingtalk_content = f"""## {prompt}

**查询结果:**

{output[:2000]}

---
*来自 Hermes Work Assistant*
"""
            
            dingtalk_result = await send_to_dingtalk(dingtalk_content)
            
            if dingtalk_result.get("errcode") == 0:
                print("\n✅ 钉钉消息发送成功!")
            else:
                print(f"\n❌ 钉钉消息发送失败: {dingtalk_result}")
                
        else:
            error = result.get("error") or result.get("message")
            print(f"\n❌ 查询失败: {error}")
            
            # 发送错误通知到钉钉
            error_content = f"""## ERP查询失败

**错误信息:** {error}

---
*来自 Hermes Work Assistant*
"""
            await send_to_dingtalk(error_content, title="ERP查询失败")
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
