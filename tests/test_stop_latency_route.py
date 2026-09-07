from types import SimpleNamespace

import pytest

from saarthi.api.routes import record_stop_latency
from saarthi.api.schemas import StopLatencyRequest
from saarthi.domain.contracts import ConversationState


class RecordingRepository:
    def __init__(self, state: ConversationState) -> None:
        self.state = state
        self.events = []

    async def get_state(self, session_id: str):
        return self.state if session_id == self.state.session_id else None

    async def append_event(self, event) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_record_stop_latency_appends_browser_measurement():
    state = ConversationState(
        session_id="session-stop-test",
        application_id="application-stop-test",
        participant_id="borrower-stop-test",
    )
    repository = RecordingRepository(state)
    runtime = SimpleNamespace(repository=repository)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runtime=runtime))
    )

    result = await record_stop_latency(
        state.session_id,
        StopLatencyRequest(latency_ms=245.5),
        request,
    )

    assert result == {"recorded": True, "latency_ms": 245.5}
    assert len(repository.events) == 1
    event = repository.events[0]
    assert event.event_type == "user_facing_stop_latency_recorded"
    assert event.latency_ms == 245.5
    assert event.payload["source"] == "stop_button"


@pytest.mark.asyncio
async def test_record_stop_latency_rejects_unknown_session():
    state = ConversationState(
        session_id="session-stop-test",
        application_id="application-stop-test",
        participant_id="borrower-stop-test",
    )
    repository = RecordingRepository(state)
    runtime = SimpleNamespace(repository=repository)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runtime=runtime))
    )

    with pytest.raises(Exception) as error:
        await record_stop_latency(
            "missing-session",
            StopLatencyRequest(latency_ms=245.5),
            request,
        )

    assert getattr(error.value, "status_code", None) == 404
