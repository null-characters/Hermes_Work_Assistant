"""WeChat Work API Client"""

import logging
import os
import hashlib
import xml.etree.ElementTree as ET
from typing import Optional
from fastapi import Response
import httpx

logger = logging.getLogger(__name__)


class WeChatClient:
    """企业微信 API 客户端"""
    
    def __init__(self):
        self.corp_id = os.getenv("WECHAT_CORP_ID")
        self.agent_id = os.getenv("WECHAT_AGENT_ID")
        self.secret = os.getenv("WECHAT_SECRET")
        self.token = os.getenv("WECHAT_TOKEN")
        self.encoding_aes_key = os.getenv("WECHAT_ENCODING_AES_KEY")
        
        self._access_token: Optional[str] = None
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return all([self.corp_id, self.agent_id, self.secret])
    
    async def get_access_token(self) -> str:
        """获取 access_token"""
        if self._access_token:
            return self._access_token
        
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.secret,
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            
            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                return self._access_token
            
            raise ValueError(f"Get token failed: {data.get('errmsg')}")
    
    async def verify_callback(self, params: dict) -> Response:
        """验证回调 URL
        
        企业微信会发送 GET 请求验证 URL
        """
        
        signature = params.get("msg_signature")
        timestamp = params.get("timestamp")
        nonce = params.get("nonce")
        echostr = params.get("echostr")
        
        # 验证签名
        if not self._verify_signature(signature, timestamp, nonce):
            logger.warning("Callback verification failed: invalid signature")
            return Response(content="invalid", media_type="text/plain")
        
        # 解密 echostr 并返回
        # 简化实现：直接返回 echostr（实际需要解密）
        logger.info("Callback URL verified")
        return Response(content=echostr, media_type="text/plain")
    
    def _verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """验证签名"""
        if not all([signature, timestamp, nonce, self.token]):
            return False
        
        # 排序并拼接
        items = [self.token, timestamp, nonce]
        items.sort()
        joined = "".join(items)
        
        # SHA1 计算
        calculated = hashlib.sha1(joined.encode()).hexdigest()
        
        return calculated == signature
    
    async def parse_message(self, body: bytes, params: dict) -> Optional[dict]:
        """解析消息"""
        try:
            # 验证签名
            signature = params.get("msg_signature")
            timestamp = params.get("timestamp")
            nonce = params.get("nonce")
            
            if not self._verify_signature(signature, timestamp, nonce):
                logger.warning("Message signature verification failed")
                return None
            
            # 解析 XML（简化实现，实际需要解密）
            xml_str = body.decode("utf-8")
            root = ET.fromstring(xml_str)
            
            message = {
                "from_user": root.findtext("FromUserName"),
                "to_user": root.findtext("ToUserName"),
                "msg_type": root.findtext("MsgType"),
                "content": root.findtext("Content"),
                "msg_id": root.findtext("MsgId"),
                "agent_id": root.findtext("AgentID"),
            }
            
            logger.info(f"Received message: {message['msg_type']} from {message['from_user']}")
            return message
        
        except Exception as e:
            logger.error(f"Parse message failed: {e}")
            return None
    
    async def send_message(
        self,
        user_id: str,
        message: str,
        msg_type: str = "text",
    ) -> dict:
        """发送消息"""
        access_token = await self.get_access_token()
        
        url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
        params = {"access_token": access_token}
        
        data = {
            "touser": user_id,
            "msgtype": msg_type,
            "agentid": self.agent_id,
            "text": {"content": message},
            "safe": 0,
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, json=data)
            result = resp.json()
            
            if result.get("errcode") == 0:
                logger.info(f"Message sent to {user_id}")
                return result
            
            raise ValueError(f"Send failed: {result.get('errmsg')}")
    
    async def send_file(self, user_id: str, file_path: str) -> dict:
        """发送文件"""
        # 上传素材获取 media_id
        access_token = await self.get_access_token()
        
        # 上传文件
        upload_url = "https://qyapi.weixin.qq.com/cgi-bin/media/upload"
        upload_params = {"access_token": access_token, "type": "file"}
        
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    upload_url,
                    params=upload_params,
                    files={"media": f},
                )
                upload_result = resp.json()
            
            if upload_result.get("errcode"):
                raise ValueError(f"Upload failed: {upload_result.get('errmsg')}")
            
            media_id = upload_result["media_id"]
            
            # 发送文件消息
            send_url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
            send_params = {"access_token": access_token}
            
            data = {
                "touser": user_id,
                "msgtype": "file",
                "agentid": self.agent_id,
                "file": {"media_id": media_id},
            }
            
            resp = await client.post(send_url, params=send_params, json=data)
            return resp.json()