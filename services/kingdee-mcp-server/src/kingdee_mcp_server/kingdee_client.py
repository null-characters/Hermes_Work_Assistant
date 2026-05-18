"""Kingdee SDK client wrapper for MCP Server."""

import os
import logging
from typing import Optional

# Add kingdee_webapi_sdk to path
import sys
sys.path.insert(0, os.path.expanduser("~/git_prj/kingdee_webapi_sdk"))

from kingdee_sdk.client import KingdeeClient
from kingdee_sdk.auth import AuthType

logger = logging.getLogger(__name__)

# Global client instance (lazy initialization)
_client: Optional[KingdeeClient] = None


def get_client() -> KingdeeClient:
    """Get or create Kingdee client instance."""
    global _client
    
    if _client is None:
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
        logger.info("Kingdee client initialized")
    
    return _client


def reset_client():
    """Reset client instance (for testing)."""
    global _client
    _client = None