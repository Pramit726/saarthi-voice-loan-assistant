from __future__ import annotations

import asyncio
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from saarthi.domain.contracts import ProductFact, RetrievedFact


class KnowledgeProvider(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        product_id: str,
        product_version: str,
        fact_set_version: str,
        limit: int,
    ) -> list[RetrievedFact]: ...

    async def get_fact(self, fact_id: str) -> ProductFact | None: ...


def load_product_facts(path: Path) -> list[ProductFact]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ProductFact.model_validate(item) for item in payload["facts"]]


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "can",
    "do",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "when",
    "which",
    "will",
    "with",
    "you",
}


def _tokens(text: str) -> list[str]:
    return [
        token for token in TOKEN_RE.findall(text.casefold()) if token not in STOPWORDS
    ]


class LocalKnowledgeProvider:
    """Deterministic offline fallback and test double for approved facts."""

    def __init__(self, facts: list[ProductFact]) -> None:
        self._facts = {fact.fact_id: fact for fact in facts}
        self._documents = {
            fact.fact_id: _tokens(" ".join([fact.topic, fact.text, *fact.aliases]))
            for fact in facts
        }

    async def get_fact(self, fact_id: str) -> ProductFact | None:
        return self._facts.get(fact_id)

    async def retrieve(
        self,
        query: str,
        *,
        product_id: str,
        product_version: str,
        fact_set_version: str,
        limit: int,
    ) -> list[RetrievedFact]:
        query_counts = Counter(_tokens(query))
        if not query_counts:
            return []
        ranked: list[RetrievedFact] = []
        for fact_id, document_tokens in self._documents.items():
            fact = self._facts[fact_id]
            if (
                fact.product_id != product_id
                or fact.product_version != product_version
                or fact.fact_set_version != fact_set_version
                or fact.status != "approved"
            ):
                continue
            document_counts = Counter(document_tokens)
            overlap = sum(
                min(count, document_counts[token])
                for token, count in query_counts.items()
            )
            alias_bonus = max(
                (1.5 for alias in fact.aliases if alias.casefold() in query.casefold()),
                default=0.0,
            )
            score = (overlap + alias_bonus) / math.sqrt(max(1, len(document_tokens)))
            if score > 0:
                ranked.append(RetrievedFact(fact=fact, score=float(score)))
        return sorted(ranked, key=lambda item: (-item.score, item.fact.fact_id))[:limit]


class QdrantKnowledgeProvider:
    """Version-scoped vector retrieval using local embeddings and Qdrant Cloud storage."""

    vector_name = "content"
    keyword_payload_fields = (
        "fact_id",
        "product_id",
        "product_version",
        "fact_set_version",
        "status",
    )

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        collection: str,
        embedding_model: str,
        score_threshold: float,
    ) -> None:
        self.collection = collection
        self.score_threshold = score_threshold
        self.client = QdrantClient(url=url, api_key=api_key, timeout=10)
        self.embedding_model = embedding_model
        self._embedder: TextEmbedding | None = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embedder is None:
            self._embedder = TextEmbedding(model_name=self.embedding_model)
        return [embedding.tolist() for embedding in self._embedder.embed(texts)]

    async def ensure_collection(self) -> None:
        def operation() -> None:
            if not self.client.collection_exists(self.collection):
                dimension = len(self._embed(["dimension probe"])[0])
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config={
                        self.vector_name: models.VectorParams(
                            size=dimension, distance=models.Distance.COSINE
                        )
                    },
                )
            for field_name in self.keyword_payload_fields:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )

        await asyncio.to_thread(operation)

    async def ingest(self, facts: list[ProductFact]) -> int:
        await self.ensure_collection()

        def operation() -> int:
            texts = [" ".join([fact.topic, fact.text, *fact.aliases]) for fact in facts]
            embeddings = self._embed(texts)
            points = [
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, fact.fact_id)),
                    vector={self.vector_name: vector},
                    payload=fact.model_dump(mode="json"),
                )
                for fact, vector in zip(facts, embeddings, strict=True)
            ]
            self.client.upsert(
                collection_name=self.collection, points=points, wait=True
            )
            return len(points)

        return await asyncio.to_thread(operation)

    async def get_fact(self, fact_id: str) -> ProductFact | None:
        def operation() -> ProductFact | None:
            result = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="fact_id", match=models.MatchValue(value=fact_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            points = result[0]
            return ProductFact.model_validate(points[0].payload) if points else None

        return await asyncio.to_thread(operation)

    async def retrieve(
        self,
        query: str,
        *,
        product_id: str,
        product_version: str,
        fact_set_version: str,
        limit: int,
    ) -> list[RetrievedFact]:
        query_vector = (await asyncio.to_thread(self._embed, [query]))[0]

        def operation() -> list[RetrievedFact]:
            result = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                using=self.vector_name,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="product_id", match=models.MatchValue(value=product_id)
                        ),
                        models.FieldCondition(
                            key="product_version",
                            match=models.MatchValue(value=product_version),
                        ),
                        models.FieldCondition(
                            key="fact_set_version",
                            match=models.MatchValue(value=fact_set_version),
                        ),
                        models.FieldCondition(
                            key="status", match=models.MatchValue(value="approved")
                        ),
                    ]
                ),
                limit=limit,
                score_threshold=self.score_threshold,
                with_payload=True,
                with_vectors=False,
            )
            return [
                RetrievedFact(
                    fact=ProductFact.model_validate(point.payload),
                    score=float(point.score),
                )
                for point in result.points
            ]

        return await asyncio.to_thread(operation)
