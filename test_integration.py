"""测试钉钉网关与 Hermes Agent 集成"""

import asyncio
import httpx

DINGTALK_WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=f56060dd203be5b4c392f41caac92a7fbb239e691f1261bfb4b75a73c5dc33e9"
DINGTALK_SECRET = "SEC19ccddce58dc4458ea7d62447ff3aeea9ba17260fc34d87f17dffd303f7dbb00"
HERMES_AGENT_URL = "http://localhost:8646"


async def test_chat():
    """测试对话功能"""
    print("=" * 50)
    print("测试 Hermes Agent 对话集成")
    print("=" * 50)
    
    # 测试消息
    test_message = "你好，请简单介绍一下你自己"
    
    print(f"\n发送消息: {test_message}")
    print("-" * 50)
    
    # 调用 Hermes Agent
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{HERMES_AGENT_URL}/api/task",
                json={
                    "task": test_message,
                    "session_id": "dingtalk_test",
                    "stream": False
                }
            )
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"成功: {result.get('success')}")
                print(f"输出: {result.get('output', '')[:500]}")
            else:
                print(f"错误: {response.text}")
                
        except Exception as e:
            print(f"异常: {e}")


async def test_dingtalk_gateway():
    """测试钉钉网关服务"""
    print("\n" + "=" * 50)
    print("测试钉钉网关服务")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 健康检查
        try:
            response = await client.get("http://localhost:8002/health")
            print(f"健康检查: {response.json()}")
        except Exception as e:
            print(f"网关服务未启动: {e}")
            return
        
        # 测试发送消息
        print("\n发送测试消息到钉钉群...")
        response = await client.post(
            "http://localhost:8002/send/text",
            json={"content": "Hermes Agent 集成测试成功！"}
        )
        print(f"发送结果: {response.json()}")


if __name__ == "__main__":
    print("选择测试:")
    print("1. 测试 Hermes Agent 对话")
    print("2. 测试钉钉网关服务")
    print("3. 全部测试")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    if choice == "1":
        asyncio.run(test_chat())
    elif choice == "2":
        asyncio.run(test_dingtalk_gateway())
    else:
        asyncio.run(test_chat())
        asyncio.run(test_dingtalk_gateway())
