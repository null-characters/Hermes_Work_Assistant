"""Query result cache for MCP Server"""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)


class QueryCache:
    """LRU cache for ERP query results
    
    Features:
    - TTL-based expiration (5 minutes default)
    - LRU eviction when max_size reached
    - Thread-safe operations
    - Cache hit/miss metrics
    """
    
    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """Initialize cache
        
        Args:
            ttl: Time-to-live in seconds (default: 5 minutes)
            max_size: Maximum number of cached entries
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
        
        # Metrics
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, form_id: str, field_keys: str, 
                      filter_string: str = "", limit: int = 100) -> str:
        """Generate cache key from query parameters"""
        params = {
            "form_id": form_id,
            "field_keys": field_keys,
            "filter_string": filter_string,
            "limit": limit
        }
        params_json = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_json.encode()).hexdigest()[:16]
    
    def get(self, form_id: str, field_keys: str,
            filter_string: str = "", limit: int = 100) -> Optional[Any]:
        """Get cached result if exists and not expired
        
        Returns:
            Cached result or None if not found/expired
        """
        key = self._generate_key(form_id, field_keys, filter_string, limit)
        
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                
                # Check expiration
                if time.time() - timestamp > self.ttl:
                    del self._cache[key]
                    self._misses += 1
                    logger.debug(f"Cache expired: {key}")
                    return None
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                logger.debug(f"Cache hit: {key}")
                return result
            
            self._misses += 1
            logger.debug(f"Cache miss: {key}")
            return None
    
    def set(self, form_id: str, field_keys: str, result: Any,
            filter_string: str = "", limit: int = 100) -> None:
        """Cache query result"""
        key = self._generate_key(form_id, field_keys, filter_string, limit)
        
        with self._lock:
            # Evict oldest if at max size
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache evicted (LRU): {oldest_key}")
            
            self._cache[key] = (result, time.time())
            logger.debug(f"Cache set: {key}")
    
    def clear(self) -> None:
        """Clear all cached entries"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "ttl": self.ttl
            }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries
        
        Returns:
            Number of entries removed
        """
        removed = 0
        current_time = time.time()
        
        with self._lock:
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp > self.ttl
            ]
            
            for key in expired_keys:
                del self._cache[key]
                removed += 1
            
            logger.info(f"Cleaned up {removed} expired cache entries")
        
        return removed


# Global cache instance
_query_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """Get global query cache instance"""
    global _query_cache
    if _query_cache is None:
        import os
        ttl = int(os.getenv("CACHE_TTL", "300"))
        max_size = int(os.getenv("CACHE_MAX_SIZE", "1000"))
        _query_cache = QueryCache(ttl=ttl, max_size=max_size)
    return _query_cache