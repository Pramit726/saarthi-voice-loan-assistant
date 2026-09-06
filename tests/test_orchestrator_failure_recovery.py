import asyncio

from saarthi.domain.contracts import GroundedAnswer
from saarthi.domain.enums import (
    ControlCommand,
    FieldId,
    SessionStatus,
    SupportStatus,
    TurnAct,
    TurnRoute,
)
from saarthi.domain.state import ConversationStateMachine
from saarthi.services.orchestrator import TurnOrchestrator
from saarthi.services.planner import ResponsePlanner
from saarthi.services.renderer import ListenerRenderer
from saarthi.storage.repository import InMemoryStateRepository


class FailingGrounding:
    async def answer(self, *args, **kwargs):
        raise TimeoutError("simulated provider timeout")


class BlockingGrounding:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def answer(self, question, *, route, draft):
        self.started.set()
        await self.release.wait()
        return GroundedAnswer(
            product_id=draft.product_id,
            product_version=draft.product_version,
            fact_set_version=draft.product_version,
            question_route=route,
            support_status=SupportStatus.SUPPORTED,
            completeness_passed=True,
            calculation_ids=["calculation-stale"],
        )


def _orchestrator(repository, interpreter, grounding) -> TurnOrchestrator:
    return TurnOrchestrator(
        repository=repository,
        interpreter=interpreter,
        grounding=grounding,
        planner=ResponsePlanner(),
        renderer=ListenerRenderer(),
    )


async def test_grounding_timeout_fails_closed_and_preserves_checkpoint(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter

    text = "What is the processing fee?"
    interpreter = ScriptedInterpreter(
        {
            text: proposal_factory(
                route=TurnRoute.PRODUCT_QUESTION,
                acts=[TurnAct.DOUBT],
                rationale="product_question",
            )
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)

    result = await _orchestrator(
        repository, interpreter, FailingGrounding()
    ).process_final_transcript(transcript_factory(text))

    assert result.draft.revision == 0
    assert result.state.pending_field is FieldId.REQUESTED_AMOUNT
    assert result.state.failure_component == "grounding"
    assert result.response_plan.fallback_code == "provider_failure"
    assert result.speech_segments


async def test_slow_grounding_result_is_blocked_after_new_generation(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter

    text = "What is the processing fee?"
    interpreter = ScriptedInterpreter(
        {
            text: proposal_factory(
                route=TurnRoute.PRODUCT_QUESTION,
                acts=[TurnAct.DOUBT],
                rationale="product_question",
            )
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    grounding = BlockingGrounding()
    orchestrator = _orchestrator(repository, interpreter, grounding)

    old_turn = asyncio.create_task(
        orchestrator.process_final_transcript(transcript_factory(text))
    )
    await grounding.started.wait()
    state_during_lookup = await repository.get_state(conversation.session_id)
    newer = ConversationStateMachine().begin_final_turn(
        state_during_lookup, "turn-newer"
    )
    await repository.save_state(newer)
    grounding.release.set()
    result = await old_turn

    assert result.speech_segments == []
    assert result.response_plan.purpose == "stale_result_discarded"
    persisted = await repository.get_state(conversation.session_id)
    assert persisted.current_turn_id == "turn-newer"
    events = await repository.list_events(conversation.session_id)
    assert any(event.event_type == "stale_result_blocked" for event in events)


async def test_non_control_turn_is_ignored_while_session_is_paused(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter

    text = "Eighty thousand rupees"
    conversation = ConversationStateMachine().apply_control(
        conversation, command=ControlCommand.PAUSE
    )
    assert conversation.status is SessionStatus.PAUSED
    interpreter = ScriptedInterpreter(
        {
            text: proposal_factory(
                route=TurnRoute.FIELD_ANSWER,
                acts=[TurnAct.ANSWER],
                target=FieldId.REQUESTED_AMOUNT,
                value=80000,
                explicit_write=True,
                rationale="plain_answer",
            )
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)

    result = await _orchestrator(
        repository, interpreter, FailingGrounding()
    ).process_final_transcript(transcript_factory(text))

    assert result.commit_result is None
    assert result.draft.revision == 0
    assert result.state.status is SessionStatus.PAUSED
    assert result.response_plan.purpose == "session_paused"
