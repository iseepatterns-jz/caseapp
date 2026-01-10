"""
Redis configuration for caching and real-time features
"""

import redis.asyncio as redis
import structlog
from typing import Optional, Any
import json
from datetime import timedelta

from core.config import settings

logger = structlog.get_logger()

class RedisService:
    """Redis service for caching and real-time features"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize Redis connection"""
        try:
            # Create Redis connection
            self.redis_client = redis.from_url(
                "redis://localhost:6379",
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            
            self._initialized = True
            logger.info("Redis service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Redis", error=str(e))
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self._initialized:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in Redis"""
        if not self._initialized:
            return False
        
        try:
            json_value = json.dumps(value, default=str)
            await self.redis_client.set(key, json_value, ex=expire)
            return True
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self._initialized:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False

# Global Redis service instance
redis_service = RedisService()