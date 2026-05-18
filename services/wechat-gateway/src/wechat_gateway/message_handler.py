"""Message Handler - 处理企业微信消息并转发到 Hermes Agent"""

import logging
import os
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理器 - 转发消息到 Hermes Agent"""
    
    def __init__(self, wechat_client):
        self.wechat_client = wechat_client
        self.hermes_url = os.getenv("HERMES_AGENT_URL", "http://localhost:8000")
    
    async def handle(self, message: dict) -> None:
        """处理接收到的消息"""
        msg_type = message.get("msg_type")
        from_user = message.get("from_user")
        
        if msg_type == "text":
            await self._handle_text(message)
        elif msg_type == "image":
            await self._handle_image(message)
        elif msg_type == "file":
            await self._handle_file(message)
        else:
            logger.warning(f"Unsupported message type: {msg_type}")
    
    async def _handle_text(self, message: dict) -> None:
        """处理文本消息"""
        content = message.get("content")
        from_user = message.get("from_user")
        
        logger.info(f"Processing text message from {from_user}: {content[:50]}...")
        
        # 转发到 Hermes Agent
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.hermes_url}/process",
                    json={
                        "user_id": from_user,
                        "message": content,
                        "source": "wechat",
                    },
                    timeout=30.0,
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    # 发送响应到企业微信
                    await self._send_response(from_user, result)
                else:
                    logger.error(f"Hermes Agent error: {resp.status_code}")
                    await self.wechat_client.send_message(
                        user_id=from_user,
                        message="处理失败，请稍后重试",
                    )
        
        except Exception as e:
            logger.error(f"Forward to Hermes failed: {e}")
            await self.wechat_client.send_message(
                user_id=from_user,
                message="系统繁忙，请稍后重试",
            )
    
    async def _handle_image(self, message: dict) -> None:
        """处理图片消息"""
        from_user = message.get("from_user")
        media_id = message.get("MediaId")
        
        logger.info(f"Processing image from {from_user}")
        
        # 转发到 Hermes Agent（带图片信息）
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.hermes_url}/process",
                    json={
                        "user_id": from_user,
                        "message": "[图片]",
                        "media_id": media_id,
                        "msg_type": "image",
                        "source": "wechat",
                    },
                    timeout=30.0,
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    await self._send_response(from_user, result)
        
        except Exception as e:
            logger.error(f"Handle image failed: {e}")
    
    async def _handle_file(self, message: dict) -> None:
        """处理文件消息"""
        from_user = message.get("from_user")
        media_id = message.get("MediaId")
        file_name = message.get("FileName", "unknown")
        
        logger.info(f"Processing file from {from_user}: {file_name}")
        
        # 转发到 Hermes Agent
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.hermes_url}/process",
                    json={
                        "user_id": from_user,
                        "message": f"[文件: {file_name}]",
                        "media_id": media_id,
                        "msg_type": "file",
                        "source": "wechat",
                    },
                    timeout=30.0,
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    await self._send_response(from_user, result)
        
        except Exception as e:
            logger.error(f"Handle file failed: {e}")
    
    async def _send_response(self, user_id: str, result: dict) -> None:
        """发送响应到企业微信"""
        response_text = result.get("response", "")
        
        if response_text:
            await self.wechat_client.send_message(
                user_id=user_id,
                message=response_text,
            )
        
        # 如果有文件输出
        output_file = result.get("output_file")
        if output_file:
            await self.wechat_client.send_file(
                user_id=user_id,
                file_path=output_file,
            )