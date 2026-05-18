"""Tests for Query Cache"""

import pytest
import time
from unittest.mock import patch, MagicMock

from kingdee_mcp_server.cache import QueryCache, get_query_cache


class TestQueryCache:
    """Tests for QueryCache class"""
    
    def test_cache_set_and_get(self):
        """Test basic set and get operations"""
        cache = QueryCache(ttl=60, max_size=100)
        
        # Set a value
        cache.set("BD_MATERIAL", "FNumber,FName", {"data": "test"})
        
        # Get the value
        result = cache.get("BD_MATERIAL", "FNumber,FName")
        assert result is not None
        assert result["data"] == "test"
    
    def test_cache_miss(self):
        """Test cache miss"""
        cache = QueryCache(ttl=60, max_size=100)
        
        result = cache.get("NON_EXISTENT", "FNumber")
        assert result is None
    
    def test_cache_expiration(self):
        """Test cache TTL expiration"""
        cache = QueryCache(ttl=1, max_size=100)  # 1 second TTL
        
        # Set a value
        cache.set("BD_MATERIAL", "FNumber", {"data": "test"})
        
        # Should exist immediately
        result = cache.get("BD_MATERIAL", "FNumber")
        assert result is not None
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        result = cache.get("BD_MATERIAL", "FNumber")
        assert result is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when max_size reached"""
        cache = QueryCache(ttl=60, max_size=3)
        
        # Add 3 entries
        cache.set("FORM1", "F1", {"data": 1})
        cache.set("FORM2", "F2", {"data": 2})
        cache.set("FORM3", "F3", {"data": 3})
        
        # All should exist
        assert cache.get("FORM1", "F1") is not None
        assert cache.get("FORM2", "F2") is not None
        assert cache.get("FORM3", "F3") is not None
        
        # Add 4th entry - should evict FORM1 (oldest)
        cache.set("FORM4", "F4", {"data": 4})
        
        # FORM1 should be evicted
        assert cache.get("FORM1", "F1") is None
        assert cache.get("FORM4", "F4") is not None
    
    def test_cache_lru_access_order(self):
        """Test that access updates LRU order"""
        cache = QueryCache(ttl=60, max_size=3)
        
        # Add 3 entries
        cache.set("FORM1", "F1", {"data": 1})
        cache.set("FORM2", "F2", {"data": 2})
        cache.set("FORM3", "F3", {"data": 3})
        
        # Access FORM1 to make it most recently used
        cache.get("FORM1", "F1")
        
        # Add 4th entry - should evict FORM2 (now oldest)
        cache.set("FORM4", "F4", {"data": 4})
        
        # FORM1 should still exist (was accessed recently)
        assert cache.get("FORM1", "F1") is not None
        # FORM2 should be evicted
        assert cache.get("FORM2", "F2") is None
    
    def test_cache_stats(self):
        """Test cache statistics"""
        cache = QueryCache(ttl=60, max_size=100)
        
        # Set and get (hit)
        cache.set("FORM1", "F1", {"data": 1})
        cache.get("FORM1", "F1")
        
        # Miss
        cache.get("FORM2", "F2")
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 1
    
    def test_cache_clear(self):
        """Test cache clear"""
        cache = QueryCache(ttl=60, max_size=100)
        
        cache.set("FORM1", "F1", {"data": 1})
        cache.set("FORM2", "F2", {"data": 2})
        
        cache.clear()
        
        assert cache.get("FORM1", "F1") is None
        assert cache.get("FORM2", "F2") is None
        assert cache.get_stats()["size"] == 0
    
    def test_cache_key_generation(self):
        """Test that different params generate different keys"""
        cache = QueryCache(ttl=60, max_size=100)
        
        # Set with different params
        cache.set("BD_MATERIAL", "FNumber", {"data": 1})
        cache.set("BD_MATERIAL", "FNumber,FName", {"data": 2})
        cache.set("BD_CUSTOMER", "FNumber", {"data": 3})
        
        # Should get different values
        result1 = cache.get("BD_MATERIAL", "FNumber")
        result2 = cache.get("BD_MATERIAL", "FNumber,FName")
        result3 = cache.get("BD_CUSTOMER", "FNumber")
        
        assert result1["data"] == 1
        assert result2["data"] == 2
        assert result3["data"] == 3
    
    def test_cache_with_filter_string(self):
        """Test cache with filter string parameter"""
        cache = QueryCache(ttl=60, max_size=100)
        
        # Set with filter
        cache.set("BD_MATERIAL", "FNumber", {"data": 1}, filter_string="FNumber='M001'")
        
        # Get with same filter
        result = cache.get("BD_MATERIAL", "FNumber", filter_string="FNumber='M001'")
        assert result is not None
        
        # Get with different filter - should miss
        result = cache.get("BD_MATERIAL", "FNumber", filter_string="FNumber='M002'")
        assert result is None
    
    def test_cache_cleanup_expired(self):
        """Test manual cleanup of expired entries"""
        cache = QueryCache(ttl=1, max_size=100)
        
        # Add entries
        cache.set("FORM1", "F1", {"data": 1})
        cache.set("FORM2", "F2", {"data": 2})
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Manual cleanup
        removed = cache.cleanup_expired()
        
        assert removed == 2
        assert cache.get_stats()["size"] == 0
    
    def test_get_query_cache_singleton(self):
        """Test global cache instance"""
        cache1 = get_query_cache()
        cache2 = get_query_cache()
        
        # Should be the same instance
        assert cache1 is cache2
    
    @patch("kingdee_mcp_server.cache._query_cache", None)
    def test_get_query_cache_with_env(self):
        """Test cache initialization from environment"""
        with patch.dict("os.environ", {"CACHE_TTL": "600", "CACHE_MAX_SIZE": "500"}):
            cache = get_query_cache()
            assert cache.ttl == 600
            assert cache.max_size == 500
