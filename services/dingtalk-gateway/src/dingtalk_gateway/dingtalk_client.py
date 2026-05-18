"""
钉钉群机器人客户端

支持通过 Webhook 发送消息到钉钉群
"""

import hmac
import hashlib
import base64
import time
import urllib.parse
from typing import Optional
import httpx
from pydantic import BaseModel


class DingTalkConfig(BaseModel):
    """钉钉机器人配置"""
    webhook_url: str
    secret: Optional[str] = None


class DingTalkClient:
    """钉钉群机器人客户端"""
    
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret
    
    def _generate_sign(self, timestamp: int) -> str:
        """生成加签签名"""
        if not self.secret:
            return ""
        
        # 签名算法: 把timestamp+"\n"+secret当做签名字符串
        string_to_sign = f"{timestamp}\n{self.secret}"
        
        # 使用HmacSHA256算法计算签名
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # Base64编码
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign
    
    async def send_text(self, content: str, at_all: bool = False, at_mobiles: Optional[list] = None) -> dict:
        """
        发送文本消息
        
        Args:
            content: 文本内容
            at_all: 是否@所有人
            at_mobiles: 被@人的手机号列表
        
        Returns:
            钉钉API响应
        """
        timestamp = int(time.time() * 1000)
        
        # 构建请求URL
        url = self.webhook_url
        if self.secret:
            sign = self._generate_sign(timestamp)
            url = f"{url}&timestamp={timestamp}&sign={sign}"
        
        # 构建消息体
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            },
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            return response.json()
    
    async def send_markdown(self, title: str, content: str, at_all: bool = False) -> dict:
        """
        发送Markdown消息
        
        Args:
            title: 标题
            content: Markdown内容
            at_all: 是否@所有人
        
        Returns:
            钉钉API响应
        """
        timestamp = int(time.time() * 1000)
        
        url = self.webhook_url
        if self.secret:
            sign = self._generate_sign(timestamp)
            url = f"{url}&timestamp={timestamp}&sign={sign}"
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            },
            "at": {
                "isAtAll": at_all
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            return response.json()
    
    async def send_link(self, title: str, text: str, url: str, pic_url: Optional[str] = None) -> dict:
        """
        发送链接消息
        
        Args:
            title: 标题
            text: 描述文本
            url: 链接地址
            pic_url: 图片地址
        
        Returns:
            钉钉API响应
        """
        timestamp = int(time.time() * 1000)
        
        webhook_url = self.webhook_url
        if self.secret:
            sign = self._generate_sign(timestamp)
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        
        data = {
            "msgtype": "link",
            "link": {
                "title": title,
                "text": text,
                "picUrl": pic_url or "",
                "messageUrl": url
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=data)
            return response.json()
