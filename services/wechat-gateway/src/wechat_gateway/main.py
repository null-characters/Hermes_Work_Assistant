"""WeChat Work Gateway - 企业微信消息网关"""

import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os

from .wechat_client import WeChatClient
from .message_handler import MessageHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="WeChat Work Gateway",
    description="企业微信消息网关，转发消息到 Hermes Agent",
    version="0.1.0",
)

# Initialize clients
wechat_client = WeChatClient()
message_handler = MessageHandler(wechat_client)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "wechat-gateway"}


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {
        "status": "healthy",
        "wechat_connected": wechat_client.is_configured(),
    }


@app.api_route("/callback", methods=["GET", "POST"])
async def wechat_callback(request: Request):
    """企业微信回调接口 - 接收消息
    
    GET: 验证回调 URL
    POST: 接收消息推送
    """
    if request.method == "GET":
        # URL 验证
        params = dict(request.query_params)
        return await wechat_client.verify_callback(params)
    
    # POST: 接收消息
    body = await request.body()
    params = dict(request.query_params)
    
    try:
        # 解密消息
        message = await wechat_client.parse_message(body, params)
        
        if message:
            # 处理消息
            await message_handler.handle(message)
        
        return Response(content="success", media_type="text/plain")
    
    except Exception as e:
        logger.error(f"Message handling failed: {e}")
        return Response(content="error", media_type="text/plain")


@app.post("/send")
async def send_message(request: Request):
    """发送消息到企业微信
    
    Body:
        {
            "user_id": "user123",
            "message": "Hello",
            "type": "text"
        }
    """
    data = await request.json()
    
    try:
        result = await wechat_client.send_message(
            user_id=data.get("user_id"),
            message=data.get("message"),
            msg_type=data.get("type", "text"),
        )
        return JSONResponse(content={"success": True, "result": result})
    
    except Exception as e:
        logger.error(f"Send message failed: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


def run():
    """Run the gateway server."""
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()