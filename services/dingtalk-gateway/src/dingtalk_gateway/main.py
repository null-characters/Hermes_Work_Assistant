"""
钉钉群机器人网关服务

提供 HTTP API 发送消息到钉钉群，集成 Hermes Agent 处理对话
"""

import os
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dingtalk_gateway.dingtalk_client import DingTalkClient


# 从环境变量获取配置
DINGTALK_WEBHOOK_URL = os.getenv("DINGTALK_WEBHOOK_URL", "")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "")
HERMES_AGENT_URL = os.getenv("HERMES_AGENT_URL", "http://hermes-bridge:8000")

# 全局客户端
dingtalk_client: DingTalkClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global dingtalk_client
    
    if not DINGTALK_WEBHOOK_URL:
        print("警告: DINGTALK_WEBHOOK_URL 未配置")
    else:
        dingtalk_client = DingTalkClient(DINGTALK_WEBHOOK_URL, DINGTALK_SECRET)
        print(f"钉钉机器人已初始化")
    
    print(f"Hermes Agent URL: {HERMES_AGENT_URL}")
    
    yield
    
    # 清理
    dingtalk_client = None


app = FastAPI(
    title="DingTalk Bot Gateway",
    description="钉钉群机器人消息发送服务，集成 Hermes Agent",
    version="1.0.0",
    lifespan=lifespan
)


class TextMessage(BaseModel):
    """文本消息请求"""
    content: str
    at_all: bool = False
    at_mobiles: list[str] = []


class MarkdownMessage(BaseModel):
    """Markdown消息请求"""
    title: str
    content: str
    at_all: bool = False


class LinkMessage(BaseModel):
    """链接消息请求"""
    title: str
    text: str
    url: str
    pic_url: str = ""


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    user_id: str = "dingtalk_user"


class ChatResponse(BaseModel):
    """对话响应"""
    success: bool
    response: str
    error: str = ""


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "dingtalk_configured": dingtalk_client is not None,
        "hermes_agent_url": HERMES_AGENT_URL
    }


@app.post("/send/text")
async def send_text(message: TextMessage):
    """发送文本消息"""
    if not dingtalk_client:
        raise HTTPException(status_code=500, detail="钉钉机器人未配置")
    
    result = await dingtalk_client.send_text(
        content=message.content,
        at_all=message.at_all,
        at_mobiles=message.at_mobiles
    )
    
    if result.get("errcode", 0) != 0:
        raise HTTPException(status_code=500, detail=result.get("errmsg", "发送失败"))
    
    return {"success": True, "message": "发送成功"}


@app.post("/send/markdown")
async def send_markdown(message: MarkdownMessage):
    """发送Markdown消息"""
    if not dingtalk_client:
        raise HTTPException(status_code=500, detail="钉钉机器人未配置")
    
    result = await dingtalk_client.send_markdown(
        title=message.title,
        content=message.content,
        at_all=message.at_all
    )
    
    if result.get("errcode", 0) != 0:
        raise HTTPException(status_code=500, detail=result.get("errmsg", "发送失败"))
    
    return {"success": True, "message": "发送成功"}


@app.post("/send/link")
async def send_link(message: LinkMessage):
    """发送链接消息"""
    if not dingtalk_client:
        raise HTTPException(status_code=500, detail="钉钉机器人未配置")
    
    result = await dingtalk_client.send_link(
        title=message.title,
        text=message.text,
        url=message.url,
        pic_url=message.pic_url
    )
    
    if result.get("errcode", 0) != 0:
        raise HTTPException(status_code=500, detail=result.get("errmsg", "发送失败"))
    
    return {"success": True, "message": "发送成功"}


async def call_hermes_agent(message: str, user_id: str = "dingtalk_user") -> str:
    """
    调用 Hermes Agent 处理消息
    
    Returns:
        Agent 响应内容
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 调用 Hermes Bridge API
        response = await client.post(
            f"{HERMES_AGENT_URL}/api/task",
            json={
                "task": message,
                "session_id": f"dingtalk_{user_id}",
                "stream": False
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Hermes Agent 调用失败: {response.text}"
            )
        
        result = response.json()
        
        if not result.get("success", False):
            return f"处理失败: {result.get('error', '未知错误')}"
        
        # 提取响应内容
        output = result.get("output", "")
        
        # 过滤 Hermes 日志，提取实际响应
        lines = output.split('\n')
        response_lines = []
        for line in lines:
            # 跳过日志行和边框行
            stripped = line.strip()
            if not stripped:
                continue
            if any(skip in stripped for skip in [
                'Query:', 'Initializing', 'API call', 'Token',
                'Conversation', 'Hermes', '─', '╭', '╰', '┊', '│',
                'Tool', 'preparing', 'thinking', 'Enabled', 'Duration',
                'Messages:', 'Session:', 'Resume'
            ]):
                continue
            # 跳过以时间戳开头的日志
            if len(stripped) > 8 and stripped[:8].replace(':', '').isdigit():
                continue
            response_lines.append(stripped)
        
        return '\n'.join(response_lines) if response_lines else output


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    与 Hermes Agent 对话并发送结果到钉钉群
    
    流程：
    1. 接收用户消息
    2. 调用 Hermes Agent 处理
    3. 将结果发送到钉钉群
    """
    if not dingtalk_client:
        raise HTTPException(status_code=500, detail="钉钉机器人未配置")
    
    try:
        # 发送处理中提示
        await dingtalk_client.send_text(f"🔄 正在处理: {request.message[:50]}...")
        
        # 调用 Hermes Agent
        response = await call_hermes_agent(request.message, request.user_id)
        
        # 发送响应到钉钉群
        # 如果响应较长，使用 Markdown 格式
        if len(response) > 200:
            # 截断过长的响应
            display_response = response[:2000] + "..." if len(response) > 2000 else response
            await dingtalk_client.send_markdown(
                title="Hermes 回复",
                content=f"## Hermes 回复\n\n{display_response}"
            )
        else:
            await dingtalk_client.send_text(f"🤖 {response}")
        
        return ChatResponse(success=True, response=response)
        
    except HTTPException:
        raise
    except Exception as e:
        # 发送错误提示
        await dingtalk_client.send_text(f"❌ 处理失败: {str(e)[:100]}")
        return ChatResponse(success=False, response="", error=str(e))


@app.post("/chat/silent")
async def chat_silent(request: ChatRequest) -> ChatResponse:
    """
    与 Hermes Agent 对话（不发送到钉钉群）
    
    仅返回 Agent 响应，不推送到钉钉群
    """
    try:
        response = await call_hermes_agent(request.message, request.user_id)
        return ChatResponse(success=True, response=response)
    except HTTPException:
        raise
    except Exception as e:
        return ChatResponse(success=False, response="", error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
