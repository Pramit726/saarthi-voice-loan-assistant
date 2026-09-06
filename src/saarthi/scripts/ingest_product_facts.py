from __future__ import annotations

import asyncio

from saarthi.config import get_settings
from saarthi.providers.knowledge import QdrantKnowledgeProvider, load_product_facts


async def ingest() -> int:
    settings = get_settings()
    facts = load_product_facts(settings.product_facts_path)
    provider = QdrantKnowledgeProvider(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value(),
        collection=settings.qdrant_collection,
        embedding_model=settings.embedding_model,
        score_threshold=settings.retrieval_score_threshold,
    )
    return await provider.ingest(facts)


def main() -> None:
    count = asyncio.run(ingest())
    print(f"Ingested {count} approved product facts.")


if __name__ == "__main__":
    main()
