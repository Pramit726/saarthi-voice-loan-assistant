import os

import pytest

from saarthi.config import get_settings
from saarthi.providers.gemini import GeminiStructuredClient
from saarthi.providers.groq import GroqStructuredClient
from saarthi.providers.knowledge import QdrantKnowledgeProvider, load_product_facts

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_TESTS") != "1", reason="live tests are opt-in"
    ),
]


async def test_qdrant_ingestion_and_version_scoped_retrieval():
    settings = get_settings()
    provider = QdrantKnowledgeProvider(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value(),
        collection=settings.qdrant_collection,
        embedding_model=settings.embedding_model,
        score_threshold=settings.retrieval_score_threshold,
    )
    facts = load_product_facts(settings.product_facts_path)
    await provider.ingest(facts)
    results = await provider.retrieve(
        "Is the processing fee included in EMI?",
        product_id="SPL-DEMO-01",
        product_version="1.1",
        fact_set_version="1.1",
        limit=3,
    )
    assert results
    assert all(item.fact.status == "approved" for item in results)
    assert all(item.fact.product_version == "1.1" for item in results)


async def test_groq_structured_interpretation_schema():
    settings = get_settings()
    client = GroqStructuredClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        temperature=0,
    )
    result = await client.interpret(
        system="Classify the turn. Return the required schema.",
        user="Pending field requested_amount. User said: one lakh rupees.",
    )
    assert result.route
    assert 0 <= result.uncertainty <= 1


async def test_gemini_structured_interpretation_schema():
    settings = get_settings()
    client = GeminiStructuredClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
    try:
        result = await client.interpret(
            system="Classify the turn. Return the required schema.",
            user="Pending field requested_amount. User said: one lakh rupees.",
        )
    finally:
        await client.close()
    assert result.route
    assert 0 <= result.uncertainty <= 1
