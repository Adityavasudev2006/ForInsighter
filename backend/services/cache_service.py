from __future__ import annotations

import os

import redis.asyncio as redis


class CacheService:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis | None:
        if self._client is not None:
            return self._client
        try:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            await self._client.ping()
            return self._client
        except Exception:
            self._client = None
            return None

    async def get(self, key: str) -> str | None:
        client = await self._get_client()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl_seconds: int = 86400):
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.set(key, value, ex=ttl_seconds)
        except Exception:
            return

    async def delete(self, key: str):
        client = await self._get_client()
        if client is None:
            return

    async def sadd(self, key: str, member: str):
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.sadd(key, member)
        except Exception:
            return

    async def smembers(self, key: str) -> set[str]:
        client = await self._get_client()
        if client is None:
            return set()
        try:
            res = await client.smembers(key)
            return set(res or [])
        except Exception:
            return set()

    async def delete_many(self, keys: list[str]):
        client = await self._get_client()
        if client is None:
            return
        try:
            if keys:
                await client.delete(*keys)
        except Exception:
            return
        try:
            await client.delete(key)
        except Exception:
            return

    def make_key(self, prefix: str, content_hash: str) -> str:
        return f"{prefix}:{content_hash}"
