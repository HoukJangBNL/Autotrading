"""Cache module for Redis client."""

import redis.asyncio as redis
from typing import Optional
from src.config import settings

_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get Redis client instance."""
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password if settings.redis.password else None,
            decode_responses=True
        )
    
    return _redis_client


async def close_redis_client():
    """Close Redis client connection."""
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None