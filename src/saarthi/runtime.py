from __future__ import annotations

from dataclasses import dataclass

from saarthi.config import Settings
from saarthi.providers.cache import CachedKnowledgeProvider, ResilientKnowledgeProvider
from saarthi.providers.gemini import GeminiStructuredClient
from saarthi.providers.groq import GroqStructuredClient
from saarthi.providers.knowledge import (
    LocalKnowledgeProvider,
    QdrantKnowledgeProvider,
    load_product_facts,
)
from saarthi.providers.livekit import LiveKitTokenProvider
from saarthi.services.acceptance import AcceptanceService
from saarthi.services.calculator import FinancialCalculator
from saarthi.services.grounding import GroundedAnswerService
from saarthi.services.interpreter import RetrievedFewShotInterpreter
from saarthi.services.orchestrator import TurnOrchestrator
from saarthi.services.planner import ResponsePlanner
from saarthi.services.renderer import ListenerRenderer
from saarthi.services.session import SessionService
from saarthi.storage.sqlite import SqliteStateRepository


@dataclass
class Runtime:
    settings: Settings
    repository: SqliteStateRepository
    gemini: GeminiStructuredClient
    groq: GroqStructuredClient
    qdrant: QdrantKnowledgeProvider
    knowledge: CachedKnowledgeProvider
    sessions: SessionService
    orchestrator: TurnOrchestrator
    acceptance: AcceptanceService
    livekit_tokens: LiveKitTokenProvider

    async def initialize(self) -> None:
        await self.repository.initialize()

    async def close(self) -> None:
        await self.knowledge.close()
        await self.gemini.close()
        await self.groq.close()
        await self.repository.close()


def build_runtime(settings: Settings) -> Runtime:
    facts = load_product_facts(settings.product_facts_path)
    local = LocalKnowledgeProvider(facts)
    qdrant = QdrantKnowledgeProvider(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value(),
        collection=settings.qdrant_collection,
        embedding_model=settings.embedding_model,
        score_threshold=settings.retrieval_score_threshold,
    )
    resilient = ResilientKnowledgeProvider(qdrant, local)
    knowledge = CachedKnowledgeProvider(resilient, redis_url=settings.redis_url)
    groq = GroqStructuredClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        temperature=settings.groq_temperature,
    )
    gemini = GeminiStructuredClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
    repository = SqliteStateRepository(settings.database_url)
    calculator = FinancialCalculator.from_product_facts(facts)
    renderer = ListenerRenderer()
    planner = ResponsePlanner()
    grounding = GroundedAnswerService(
        knowledge,
        calculator=calculator,
        writer=groq,
        retrieval_limit=settings.retrieval_limit,
    )
    interpreter = RetrievedFewShotInterpreter(gemini)
    orchestrator = TurnOrchestrator(
        repository=repository,
        interpreter=interpreter,
        grounding=grounding,
        planner=planner,
        renderer=renderer,
    )
    livekit_tokens = LiveKitTokenProvider(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key.get_secret_value(),
        api_secret=settings.livekit_api_secret.get_secret_value(),
        ttl_seconds=settings.livekit_token_ttl_seconds,
    )
    return Runtime(
        settings=settings,
        repository=repository,
        gemini=gemini,
        groq=groq,
        qdrant=qdrant,
        knowledge=knowledge,
        sessions=SessionService(repository),
        orchestrator=orchestrator,
        acceptance=AcceptanceService(),
        livekit_tokens=livekit_tokens,
    )
