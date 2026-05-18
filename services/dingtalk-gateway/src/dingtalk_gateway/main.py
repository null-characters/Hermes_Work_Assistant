"""
钉钉群机器人网关服务

提供 HTTP API 发送消息到钉钉群
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dingtalk_gateway.dingtalk_client import DingTalkClient


# 从环境变量获取配置
DINGTALK_WEBHOOK_URL = os.getenv("DINGTALK_WEBHOOK_URL", "")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "")

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
    
    yield
    
    # 清理
    dingtalk_client = None


app = FastAPI(
    title="DingTalk Bot Gateway",
    description="钉钉群机器人消息发送服务",
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


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "dingtalk_configured": dingtalk_client is not None
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
