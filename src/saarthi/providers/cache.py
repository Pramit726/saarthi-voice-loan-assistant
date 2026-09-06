from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict

from redis.asyncio import Redis

from saarthi.domain.contracts import ProductFact, RetrievedFact
from saarthi.providers.knowledge import KnowledgeProvider

logger = logging.getLogger(__name__)


class CachedKnowledgeProvider:
    """Cache-aside retrieval. Cached facts are replaceable and never authoritative."""

    def __init__(
        self,
        inner: KnowledgeProvider,
        *,
        redis_url: str = "",
        ttl_seconds: int = 300,
        local_capacity: int = 128,
    ) -> None:
        self.inner = inner
        self.ttl_seconds = ttl_seconds
        self.local_capacity = local_capacity
        self.local: OrderedDict[str, list[RetrievedFact]] = OrderedDict()
        self.redis = (
            Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        )

    @staticmethod
    def _key(
        query: str,
        product_id: str,
        product_version: str,
        fact_set_version: str,
        limit: int,
    ) -> str:
        material = "|".join(
            [
                query.casefold().strip(),
                product_id,
                product_version,
                fact_set_version,
                str(limit),
            ]
        )
        return "saarthi:retrieval:" + hashlib.sha256(material.encode()).hexdigest()

    async def get_fact(self, fact_id: str) -> ProductFact | None:
        return await self.inner.get_fact(fact_id)

    async def retrieve(
        self,
        query: str,
        *,
        product_id: str,
        product_version: str,
        fact_set_version: str,
        limit: int,
    ) -> list[RetrievedFact]:
        key = self._key(query, product_id, product_version, fact_set_version, limit)
        if key in self.local:
            self.local.move_to_end(key)
            return [item.model_copy(deep=True) for item in self.local[key]]
        if self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    results = [
                        RetrievedFact.model_validate(item)
                        for item in json.loads(cached)
                    ]
                    self._remember(key, results)
                    return results
            except Exception as exc:  # noqa: BLE001 - cache failure must not fail retrieval
                logger.warning("Redis cache read failed: %s", type(exc).__name__)

        results = await self.inner.retrieve(
            query,
            product_id=product_id,
            product_version=product_version,
            fact_set_version=fact_set_version,
            limit=limit,
        )
        self._remember(key, results)
        if self.redis:
            try:
                await self.redis.set(
                    key,
                    json.dumps([item.model_dump(mode="json") for item in results]),
                    ex=self.ttl_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - cache failure must not fail retrieval
                logger.warning("Redis cache write failed: %s", type(exc).__name__)
        return results

    def _remember(self, key: str, results: list[RetrievedFact]) -> None:
        self.local[key] = [item.model_copy(deep=True) for item in results]
        self.local.move_to_end(key)
        while len(self.local) > self.local_capacity:
            self.local.popitem(last=False)

    async def close(self) -> None:
        if self.redis:
            await self.redis.aclose()


class ResilientKnowledgeProvider:
    """Uses the approved local artifact only when Qdrant is unavailable."""

    def __init__(self, primary: KnowledgeProvider, fallback: KnowledgeProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def get_fact(self, fact_id: str) -> ProductFact | None:
        try:
            return await self.primary.get_fact(fact_id)
        except Exception as exc:  # noqa: BLE001 - provider boundary has heterogeneous errors
            logger.warning(
                "Primary fact lookup failed; using approved fallback: %s",
                type(exc).__name__,
            )
            return await self.fallback.get_fact(fact_id)

    async def retrieve(self, query: str, **scope) -> list[RetrievedFact]:
        try:
            return await self.primary.retrieve(query, **scope)
        except Exception as exc:  # noqa: BLE001 - provider boundary has heterogeneous errors
            logger.warning(
                "Primary retrieval failed; using approved fallback: %s",
                type(exc).__name__,
            )
            return await self.fallback.retrieve(query, **scope)
