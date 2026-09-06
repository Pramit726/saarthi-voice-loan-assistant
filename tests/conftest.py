from __future__ import annotations

from datetime import timedelta

import pytest

from saarthi.domain.contracts import (
    ApplicationDraft,
    ConversationState,
    FinalTranscript,
    TurnProposal,
    new_id,
    utc_now,
)
from saarthi.domain.enums import FieldId, TurnAct, TurnRoute
from saarthi.providers.knowledge import LocalKnowledgeProvider, load_product_facts
from saarthi.services.calculator import FinancialCalculator
from saarthi.services.grounding import GroundedAnswerService
from saarthi.services.orchestrator import TurnOrchestrator
from saarthi.services.planner import ResponsePlanner
from saarthi.services.renderer import ListenerRenderer
from saarthi.storage.repository import InMemoryStateRepository


class ScriptedInterpreter:
    def __init__(self, proposals: dict[str, TurnProposal]) -> None:
        self.proposals = proposals

    async def interpret(self, transcript: FinalTranscript, state: ConversationState) -> TurnProposal:
        proposal = self.proposals[transcript.text]
        return proposal.model_copy(update={"source_transcript_id": transcript.transcript_id})


@pytest.fixture
def application() -> ApplicationDraft:
    return ApplicationDraft(application_id="application-test", owner_session_id="session-test")


@pytest.fixture
def conversation(application: ApplicationDraft) -> ConversationState:
    return ConversationState(
        session_id="session-test",
        application_id=application.application_id,
        participant_id="borrower-test",
        last_safe_prompt="What loan amount would you like?",
    )


@pytest.fixture
def transcript_factory():
    def factory(text: str, *, session_id: str = "session-test", confidence: float = 1.0) -> FinalTranscript:
        now = utc_now()
        return FinalTranscript(
            session_id=session_id,
            participant_id="borrower-test",
            turn_id=new_id("turn"),
            generation_id=1,
            text=text,
            confidence=confidence,
            started_at=now - timedelta(milliseconds=200),
            ended_at=now,
        )

    return factory


@pytest.fixture
def proposal_factory():
    def factory(
        *,
        route: TurnRoute,
        acts: list[TurnAct],
        target: FieldId | None = None,
        value=None,
        explicit_write: bool = False,
        rationale: str = "fixture",
    ) -> TurnProposal:
        return TurnProposal(
            source_transcript_id="replaced-at-runtime",
            acts=acts,
            route=route,
            target_field=target,
            candidate_value=value,
            source_span=str(value) if value is not None else None,
            uncertainty=0,
            rationale_code=rationale,
            explicit_write=explicit_write,
        )

    return factory


def build_test_orchestrator(
    repository: InMemoryStateRepository,
    interpreter: ScriptedInterpreter,
) -> TurnOrchestrator:
    from saarthi.config import REPOSITORY_ROOT

    facts = load_product_facts(REPOSITORY_ROOT / "data" / "product" / "saarthi_product_facts_v1.json")
    grounding = GroundedAnswerService(
        LocalKnowledgeProvider(facts),
        calculator=FinancialCalculator(),
        writer=None,
    )
    return TurnOrchestrator(
        repository=repository,
        interpreter=interpreter,
        grounding=grounding,
        planner=ResponsePlanner(),
        renderer=ListenerRenderer(),
    )
