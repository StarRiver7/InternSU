import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logger import get_logger
logger = get_logger(__name__)

class RedisClient:
    _instance = None

    def __init__(self):
        self._redis = None
        self._fallback = {}

    async def connect(self):
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    password=settings.redis_password or None,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                )
                await self._redis.ping()
                logger.info("Redis 已连接")
            except Exception as e:
                logger.warning(f"Redis 不可用，使用回退存储: {e}")
                self._redis = None
        return self._redis

    async def get(self, key):
        r = await self.connect()
        if r:
            return await r.get(key)
        return self._fallback.get(key)

    async def set(self, key, value, ttl=None):
        r = await self.connect()
        if r:
            if ttl:
                await r.setex(key, ttl, value)
            else:
                await r.set(key, value)
        else:
            self._fallback[key] = value

    async def delete(self, *keys):
        r = await self.connect()
        if r:
            await r.delete(*keys)
        for k in keys:
            self._fallback.pop(k, None)

    async def exists(self, key):
        r = await self.connect()
        if r:
            return await r.exists(key)
        return key in self._fallback

    async def expire(self, key, ttl):
        r = await self.connect()
        if r:
            await r.expire(key, ttl)

    async def hget(self, key, field):
        r = await self.connect()
        if r:
            return await r.hget(key, field)
        return None

    async def hset(self, key, field, value):
        r = await self.connect()
        if r:
            await r.hset(key, field, value)
        else:
            if key not in self._fallback:
                self._fallback[key] = {}
            self._fallback[key][field] = value

    @property
    def is_connected(self):
        return self._redis is not None

redis_client = RedisClient()
