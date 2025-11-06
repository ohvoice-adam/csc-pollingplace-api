"""
Redis Cache Implementation for API Performance

Provides Redis-based caching with fallback to in-memory cache
for environments where Redis is not available.
"""

import os
import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCacheManager:
    """Redis-based cache manager with fallback to in-memory cache"""
    
    def __init__(self):
        self.redis_client = None
        self.fallback_cache = {}
        self.fallback_cache_times = {}
        self.default_ttl = 300  # 5 minutes
        self.use_redis = False
        
        # Try to initialize Redis
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection if available and configured"""
        if not REDIS_AVAILABLE:
            logging.info("Redis not available, using in-memory cache")
            return
        
        try:
            # Get Redis configuration from environment
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))
            redis_password = os.getenv('REDIS_PASSWORD')
            
            # Create Redis client
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            logging.info(f"Redis cache initialized: {redis_host}:{redis_port}/{redis_db}")
            
        except Exception as e:
            logging.warning(f"Redis connection failed, using in-memory cache: {e}")
            self.redis_client = None
            self.use_redis = False
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate a unique cache key based on request parameters"""
        from flask import request
        
        key_data = {
            'endpoint': request.endpoint,
            'args': dict(request.args),
            'json': request.get_json(silent=True) or {},
            **kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        hash_key = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{hash_key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if self.use_redis and self.redis_client:
            try:
                cached_data = self.redis_client.get(key)
                if cached_data:
                    # Parse JSON data
                    return json.loads(cached_data)
            except Exception as e:
                logging.warning(f"Redis get failed, falling back to memory cache: {e}")
                self.use_redis = False
        
        # Fallback to in-memory cache
        if key in self.fallback_cache and key in self.fallback_cache_times:
            if time.time() - self.fallback_cache_times[key] < self.default_ttl:
                return self.fallback_cache[key]
            else:
                # Expired, remove from cache
                del self.fallback_cache[key]
                del self.fallback_cache_times[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL"""
        ttl = ttl or self.default_ttl
        
        if self.use_redis and self.redis_client:
            try:
                # Store in Redis with TTL
                serialized_value = json.dumps(value, default=str)
                self.redis_client.setex(key, ttl, serialized_value)
                return
            except Exception as e:
                logging.warning(f"Redis set failed, falling back to memory cache: {e}")
                self.use_redis = False
        
        # Fallback to in-memory cache
        self.fallback_cache[key] = value
        self.fallback_cache_times[key] = time.time()
    
    def delete(self, key: str) -> None:
        """Delete specific cache entry"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.delete(key)
                return
            except Exception as e:
                logging.warning(f"Redis delete failed: {e}")
        
        # Fallback cleanup
        if key in self.fallback_cache:
            del self.fallback_cache[key]
        if key in self.fallback_cache_times:
            del self.fallback_cache_times[key]
    
    def clear(self) -> None:
        """Clear all cache entries"""
        if self.use_redis and self.redis_client:
            try:
                # Clear all keys with our app prefix
                keys = self.redis_client.keys("api:*")
                if keys:
                    self.redis_client.delete(*keys)
                return
            except Exception as e:
                logging.warning(f"Redis clear failed: {e}")
        
        # Fallback cleanup
        self.fallback_cache.clear()
        self.fallback_cache_times.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed items"""
        if self.use_redis and self.redis_client:
            # Redis handles TTL automatically
            return 0
        
        # Fallback cleanup for in-memory cache
        current_time = time.time()
        expired_keys = []
        
        for key, cache_time in self.fallback_cache_times.items():
            if current_time - cache_time >= self.default_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            if key in self.fallback_cache:
                del self.fallback_cache[key]
            if key in self.fallback_cache_times:
                del self.fallback_cache_times[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'use_redis': self.use_redis,
            'redis_connected': self.redis_client is not None
        }
        
        if self.use_redis and self.redis_client:
            try:
                info = self.redis_client.info()
                stats.update({
                    'redis_version': info.get('redis_version'),
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                })
                
                # Count our application keys
                app_keys = self.redis_client.keys("api:*")
                stats['app_keys_count'] = len(app_keys)
                
            except Exception as e:
                stats['redis_error'] = str(e)
        else:
            stats['memory_cache_size'] = len(self.fallback_cache)
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Check cache health"""
        health = {
            'status': 'healthy',
            'cache_type': 'redis' if self.use_redis else 'memory',
            'message': 'Cache operating normally'
        }
        
        if self.use_redis and self.redis_client:
            try:
                # Test Redis connection
                start_time = time.time()
                self.redis_client.ping()
                response_time = (time.time() - start_time) * 1000
                
                health['redis_response_time_ms'] = round(response_time, 2)
                
                if response_time > 1000:  # > 1 second is slow
                    health['status'] = 'degraded'
                    health['message'] = f'Redis response time is slow: {response_time:.2f}ms'
                
            except Exception as e:
                health['status'] = 'unhealthy'
                health['message'] = f'Redis connection failed: {e}'
                health['error'] = str(e)
        
        return health


# Global Redis cache instance
redis_cache_manager = RedisCacheManager()


def redis_cache_response(ttl: int = 300, key_prefix: str = "api"):
    """
    Decorator to cache API responses using Redis
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key
    """
    def decorator(f):
        def decorated_function(*args, **kwargs):
            from flask import request
            
            # Skip caching for non-GET requests
            if request.method != 'GET':
                return f(*args, **kwargs)
            
            # Generate cache key
            cache_key = redis_cache_manager._generate_cache_key(key_prefix, **kwargs)
            
            # Try to get from cache
            cached_response = redis_cache_manager.get(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Execute function and cache result
            response = f(*args, **kwargs)
            
            # Only cache successful responses
            if hasattr(response, 'status_code') and response.status_code == 200:
                redis_cache_manager.set(cache_key, response, ttl)
            elif isinstance(response, tuple) and len(response) >= 2 and response[1] == 200:
                redis_cache_manager.set(cache_key, response, ttl)
            
            return response
        
        return decorated_function
    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern
    Args:
        pattern: Pattern to match (e.g., "api:polling_places:*")
    Returns:
        Number of keys invalidated
    """
    if redis_cache_manager.use_redis and redis_cache_manager.redis_client:
        try:
            keys = redis_cache_manager.redis_client.keys(pattern)
            if keys:
                redis_cache_manager.redis_client.delete(*keys)
                return len(keys)
        except Exception as e:
            logging.warning(f"Redis pattern deletion failed: {e}")
    
    # For memory cache, clear all (simplified approach)
    redis_cache_manager.clear()
    return 0


# Cache warming functions
def warm_cache_for_state(state: str):
    """Warm up cache for a specific state's polling places"""
    cache_key = f"api:polling_places:{state.lower()}"
    # This would be called after data updates to pre-warm the cache
    pass


def get_cache_config() -> Dict[str, Any]:
    """Get cache configuration for monitoring"""
    return {
        'redis_available': REDIS_AVAILABLE,
        'redis_configured': redis_cache_manager.use_redis,
        'default_ttl': redis_cache_manager.default_ttl,
        'environment_vars': {
            'REDIS_HOST': os.getenv('REDIS_HOST', 'not set'),
            'REDIS_PORT': os.getenv('REDIS_PORT', 'not set'),
            'REDIS_DB': os.getenv('REDIS_DB', 'not set'),
            'REDIS_PASSWORD': '***' if os.getenv('REDIS_PASSWORD') else 'not set'
        }
    }