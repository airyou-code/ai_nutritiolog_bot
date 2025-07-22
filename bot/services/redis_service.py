import asyncio
import json
import logging
from typing import Any

import redis.asyncio as redis

from bot.config.settings import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Service for Redis caching and temporary data storage"""

    def __init__(self):
        self.redis_client: redis.Redis | None = None
        self._connection_pool: redis.ConnectionPool | None = None

    async def connect(self):
        """Initialize Redis connection"""
        try:
            self._connection_pool = redis.ConnectionPool.from_url(
                settings.redis_url, decode_responses=True, max_connections=20
            )
            self.redis_client = redis.Redis(connection_pool=self._connection_pool)

            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Continue without Redis if connection fails
            self.redis_client = None

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
        if self._connection_pool:
            await self._connection_pool.disconnect()
        logger.info("Redis connection closed")

    async def set_user_state(
        self,
        user_id: int,
        state: str,
        data: dict | None = None,
        expire_seconds: int = 3600,
    ) -> bool:
        """Set user state with optional data"""
        if not self.redis_client:
            return False

        try:
            key = f"user_state:{user_id}"
            value = {
                "state": state,
                "data": data or {},
                "timestamp": asyncio.get_event_loop().time(),
            }

            await self.redis_client.setex(key, expire_seconds, json.dumps(value))
            return True

        except Exception as e:
            logger.error(f"Error setting user state: {e}")
            return False

    async def get_user_state(self, user_id: int) -> dict | None:
        """Get user state and data"""
        if not self.redis_client:
            return None

        try:
            key = f"user_state:{user_id}"
            data = await self.redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error getting user state: {e}")
            return None

    async def clear_user_state(self, user_id: int) -> bool:
        """Clear user state"""
        if not self.redis_client:
            return False

        try:
            key = f"user_state:{user_id}"
            result = await self.redis_client.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"Error clearing user state: {e}")
            return False

    async def cache_food_analysis(
        self, cache_key: str, analysis_data: dict, expire_hours: int = 24
    ) -> bool:
        """Cache food analysis results"""
        if not self.redis_client:
            return False

        try:
            key = f"food_analysis:{cache_key}"
            expire_seconds = expire_hours * 3600

            await self.redis_client.setex(
                key, expire_seconds, json.dumps(analysis_data)
            )
            return True

        except Exception as e:
            logger.error(f"Error caching food analysis: {e}")
            return False

    async def get_cached_food_analysis(self, cache_key: str) -> dict | None:
        """Get cached food analysis"""
        if not self.redis_client:
            return None

        try:
            key = f"food_analysis:{cache_key}"
            data = await self.redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error getting cached food analysis: {e}")
            return None

    async def set_temp_data(
        self,
        user_id: int,
        data_key: str,
        data: Any,
        expire_seconds: int = 1800,  # 30 minutes
    ) -> bool:
        """Set temporary data for user"""
        if not self.redis_client:
            return False

        try:
            key = f"temp_data:{user_id}:{data_key}"

            await self.redis_client.setex(key, expire_seconds, json.dumps(data))
            return True

        except Exception as e:
            logger.error(f"Error setting temp data: {e}")
            return False

    async def get_temp_data(self, user_id: int, data_key: str) -> Any | None:
        """Get temporary data for user"""
        if not self.redis_client:
            return None

        try:
            key = f"temp_data:{user_id}:{data_key}"
            data = await self.redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error getting temp data: {e}")
            return None

    async def delete_temp_data(self, user_id: int, data_key: str) -> bool:
        """Delete temporary data for user"""
        if not self.redis_client:
            return False

        try:
            key = f"temp_data:{user_id}:{data_key}"
            result = await self.redis_client.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"Error deleting temp data: {e}")
            return False

    async def increment_daily_requests(self, user_id: int) -> int:
        """Increment daily request counter for user"""
        if not self.redis_client:
            return 0

        try:
            from datetime import date

            key = f"daily_requests:{user_id}:{date.today().isoformat()}"

            # Increment counter with expiration of 25 hours
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, 90000)  # 25 hours
            result = await pipe.execute()

            return result[0]

        except Exception as e:
            logger.error(f"Error incrementing daily requests: {e}")
            return 0

    async def get_daily_requests(self, user_id: int) -> int:
        """Get daily request count for user"""
        if not self.redis_client:
            return 0

        try:
            from datetime import date

            key = f"daily_requests:{user_id}:{date.today().isoformat()}"

            result = await self.redis_client.get(key)
            return int(result) if result else 0

        except Exception as e:
            logger.error(f"Error getting daily requests: {e}")
            return 0

    async def get_redis_client(self) -> redis.Redis | None:
        """Get Redis client for external use (e.g., LangGraph checkpointer)"""
        if not self.redis_client:
            # Try to connect if not connected
            await self.connect()

        return self.redis_client

    async def save_chat_session(
        self,
        user_id: int,
        thread_id: str,
        session_data: dict,
        expire_hours: int = 168,  # 7 days default
    ) -> bool:
        """Save chat session with automatic expiration"""
        if not self.redis_client:
            return False

        try:
            key = f"chat_session:{user_id}:{thread_id}"
            expire_seconds = expire_hours * 3600

            await self.redis_client.setex(key, expire_seconds, json.dumps(session_data))

            # Also update recent sessions list
            await self._update_recent_sessions_list(user_id, thread_id)

            return True

        except Exception as e:
            logger.error(f"Error saving chat session: {e}")
            return False

    async def get_chat_session(self, user_id: int, thread_id: str) -> dict | None:
        """Get chat session data"""
        if not self.redis_client:
            return None

        try:
            key = f"chat_session:{user_id}:{thread_id}"
            data = await self.redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error getting chat session: {e}")
            return None

    async def get_recent_chat_topics(self, user_id: int, limit: int = 10) -> list[str]:
        """Get recent chat topics for context"""
        if not self.redis_client:
            return []

        try:
            key = f"recent_topics:{user_id}"
            topics = await self.redis_client.lrange(key, 0, limit - 1)
            return topics or []

        except Exception as e:
            logger.error(f"Error getting recent topics: {e}")
            return []

    async def add_chat_topic(
        self, user_id: int, topic: str, max_topics: int = 20
    ) -> bool:
        """Add a new chat topic, maintaining a limited list"""
        if not self.redis_client:
            return False

        try:
            key = f"recent_topics:{user_id}"

            # Add topic to the beginning of the list
            await self.redis_client.lpush(key, topic)

            # Trim to max_topics
            await self.redis_client.ltrim(key, 0, max_topics - 1)

            # Set expiration
            await self.redis_client.expire(key, 86400 * 30)  # 30 days

            return True

        except Exception as e:
            logger.error(f"Error adding chat topic: {e}")
            return False

    async def _update_recent_sessions_list(self, user_id: int, thread_id: str):
        """Update list of recent chat sessions for user"""
        try:
            key = f"user_sessions:{user_id}"

            # Add session to the beginning
            await self.redis_client.lpush(key, thread_id)

            # Keep only last 10 sessions
            await self.redis_client.ltrim(key, 0, 9)

            # Set expiration
            await self.redis_client.expire(key, 86400 * 30)  # 30 days

        except Exception as e:
            logger.error(f"Error updating sessions list: {e}")

    async def cleanup_old_chat_data(self, days_old: int = 7) -> int:
        """Cleanup old chat data (manual cleanup for keys without TTL)"""
        if not self.redis_client:
            return 0

        try:
            # This is a basic implementation - in production you'd want more sophisticated cleanup
            pattern = "chat_session:*"
            keys = await self.redis_client.keys(pattern)

            cleaned = 0
            for key in keys:
                # Check if key has TTL, if not - set it
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No expiration set
                    await self.redis_client.expire(key, 86400 * 7)  # 7 days
                    cleaned += 1

            logger.info(f"Set expiration for {cleaned} chat session keys")
            return cleaned

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0


# Global service instance
redis_service = RedisService()
