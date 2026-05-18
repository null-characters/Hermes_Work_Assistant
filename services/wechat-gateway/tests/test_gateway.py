"""Tests for WeChat Gateway"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


class TestWeChatGateway:
    """Test WeChat Gateway endpoints"""
    
    def test_health_check(self):
        """Test health endpoint."""
        from wechat_gateway.main import app
        
        client = TestClient(app)
        resp = client.get("/health")
        
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
    
    @patch("wechat_gateway.main.wechat_client")
    def test_callback_verification(self, mock_client):
        """Test WeChat callback URL verification."""
        from wechat_gateway.main import app
        
        mock_client.verify_callback = AsyncMock(return_value="echo_string")
        
        client = TestClient(app)
        resp = client.get("/callback?msg_signature=abc&timestamp=123&nonce=456&echostr=test")
        
        assert resp.status_code == 200
    
    @patch("wechat_gateway.main.message_handler")
    @patch("wechat_gateway.main.wechat_client")
    def test_receive_text_message(self, mock_client, mock_handler):
        """Test receiving text message from WeChat."""
        from wechat_gateway.main import app
        
        mock_client.parse_message = AsyncMock(return_value={
            "from_user": "user123",
            "msg_type": "text",
            "content": "Hello",
        })
        mock_client._verify_signature = MagicMock(return_value=True)
        mock_handler.handle = AsyncMock()
        
        client = TestClient(app)
        xml_body = """
        <xml>
            <ToUserName>agent</ToUserName>
            <FromUserName>user123</FromUserName>
            <MsgType>text</MsgType>
            <Content>Hello</Content>
            <MsgId>12345</MsgId>
            <AgentID>1</AgentID>
        </xml>
        """
        resp = client.post(
            "/callback?msg_signature=abc&timestamp=123&nonce=456",
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        
        assert resp.status_code == 200
        assert resp.text == "success"
    
    @patch("wechat_gateway.main.wechat_client")
    def test_send_message(self, mock_client):
        """Test sending message to WeChat."""
        from wechat_gateway.main import app
        
        mock_client.send_message = AsyncMock(return_value={"errcode": 0})
        
        client = TestClient(app)
        resp = client.post(
            "/send",
            json={
                "user_id": "user123",
                "message": "Hello from Hermes",
                "type": "text",
            },
        )
        
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestWeChatClient:
    """Test WeChat API client"""
    
    @patch("wechat_gateway.wechat_client.os.getenv")
    def test_is_configured(self, mock_getenv):
        """Test configuration check."""
        mock_getenv.side_effect = lambda k: {
            "WECHAT_CORP_ID": "corp123",
            "WECHAT_AGENT_ID": "agent123",
            "WECHAT_SECRET": "secret123",
        }.get(k)
        
        from wechat_gateway.wechat_client import WeChatClient
        
        client = WeChatClient()
        assert client.is_configured() is True
    
    def test_verify_signature(self):
        """Test signature verification."""
        from wechat_gateway.wechat_client import WeChatClient
        
        client = WeChatClient()
        client.token = "test_token"
        
        # 测试签名验证逻辑
        result = client._verify_signature("signature", "timestamp", "nonce")
        # 签名不匹配，应该返回 False
        assert result is False


class TestMessageHandler:
    """Test message handler"""
    
    @pytest.mark.asyncio
    @patch("wechat_gateway.message_handler.httpx.AsyncClient")
    async def test_handle_text_message(self, mock_client_class):
        """Test text message handling."""
        from wechat_gateway.message_handler import MessageHandler
        
        mock_wechat = MagicMock()
        mock_wechat.send_message = AsyncMock()
        
        handler = MessageHandler(mock_wechat)
        handler.hermes_url = "http://test"
        
        # Mock HTTP response
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={"response": "Hello back"})
        ))
        mock_client_class.return_value = mock_client
        
        await handler.handle({
            "msg_type": "text",
            "from_user": "user123",
            "content": "Hello",
        })
        
        # 验证消息被转发
        mock_client.post.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])