"""Kingdee SDK client wrapper for MCP Server."""

import os
import logging
import time
from typing import Optional
from dataclasses import dataclass

# Add kingdee_webapi_sdk to path
import sys
sys.path.insert(0, os.path.expanduser("~/git_prj/kingdee_webapi_sdk"))

from kingdee_sdk.client import KingdeeClient
from kingdee_sdk.auth import AuthType

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """Connection pool configuration"""
    max_connections: int = 10
    connection_timeout: int = 30  # seconds
    idle_timeout: int = 60  # seconds
    health_check_interval: int = 30  # seconds


# Global client instance (lazy initialization)
_client: Optional[KingdeeClient] = None
_pool_config: Optional[ConnectionPoolConfig] = None
_last_health_check: float = 0


def get_pool_config() -> ConnectionPoolConfig:
    """Get connection pool configuration from environment"""
    global _pool_config
    if _pool_config is None:
        _pool_config = ConnectionPoolConfig(
            max_connections=int(os.getenv("KINGDEE_MAX_CONNECTIONS", "10")),
            connection_timeout=int(os.getenv("KINGDEE_CONNECTION_TIMEOUT", "30")),
            idle_timeout=int(os.getenv("KINGDEE_IDLE_TIMEOUT", "60")),
            health_check_interval=int(os.getenv("KINGDEE_HEALTH_CHECK_INTERVAL", "30")),
        )
    return _pool_config


def get_client() -> KingdeeClient:
    """Get or create Kingdee client instance with connection pool."""
    global _client, _last_health_check
    
    if _client is None:
        config = get_pool_config()
        
        # Load configuration from environment
        server_url = os.getenv("KINGDEE_API_URL")
        acct_id = os.getenv("KINGDEE_ACCOUNT_ID")
        username = os.getenv("KINGDEE_USERNAME", "administrator")
        app_id = os.getenv("KINGDEE_APP_ID")
        app_secret = os.getenv("KINGDEE_APP_SECRET")
        
        if not all([server_url, acct_id, app_id, app_secret]):
            raise ValueError(
                "Missing Kingdee configuration. "
                "Please set KINGDEE_API_URL, KINGDEE_ACCOUNT_ID, "
                "KINGDEE_APP_ID, and KINGDEE_APP_SECRET in .env"
            )
        
        _client = KingdeeClient(
            server_url=server_url,
            acct_id=acct_id,
            username=username,
            app_id=app_id,
            app_secret=app_secret,
            auth_type=AuthType.SIGN_SHA256,
            auto_login=True,
        )
        _last_health_check = time.time()
        logger.info(f"Kingdee client initialized with pool config: {config}")
    
    return _client


def check_connection_health() -> dict:
    """Check connection health status."""
    global _last_health_check
    
    client = get_client()
    config = get_pool_config()
    current_time = time.time()
    
    result = {
        "healthy": True,
        "last_check": _last_health_check,
        "time_since_check": current_time - _last_health_check,
    }
    
    # Perform health check if interval exceeded
    if current_time - _last_health_check > config.health_check_interval:
        try:
            # Simple query to verify connection
            client.execute_bill_query(
                form_id="BD_MATERIAL",
                field_keys="FNumber",
                limit=1,
            )
            _last_health_check = current_time
            result["healthy"] = True
            logger.debug("Connection health check passed")
        except Exception as e:
            result["healthy"] = False
            result["error"] = str(e)
            logger.warning(f"Connection health check failed: {e}")
    
    return result


def reset_client():
    """Reset client instance (for testing)."""
    global _client, _last_health_check
    _client = None
    _last_health_check = 0