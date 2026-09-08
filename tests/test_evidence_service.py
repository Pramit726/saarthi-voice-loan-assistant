from saarthi.domain.contracts import ConversationState, TraceEvent
from saarthi.services.acceptance import AcceptanceService
from saarthi.services.evidence import EvidenceService


def trace(
    session_id: str,
    event_type: str,
    *,
    turn_id: str | None = None,
    outcome: str = "observed",
    latency_ms: float | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_type=event_type,
        session_id=session_id,
        application_id=f"application-{session_id}",
        trace_id=f"trace-{session_id}",
        component="test",
        outcome=outcome,
        turn_id=turn_id,
        generation_id=1,
        application_revision=1,
        state_version=1,
        latency_ms=latency_ms,
    )


def service() -> EvidenceService:
    return EvidenceService(
        AcceptanceService(),
        normal_latency_target_ms=3000,
        grounded_latency_target_ms=5000,
    )


def test_aggregate_evidence_reports_cross_session_latency_and_safety():
    states = [
        ConversationState(session_id="s1", application_id="a1", participant_id="p1"),
        ConversationState(session_id="s2", application_id="a2", participant_id="p2"),
    ]
    events = [
        trace("s1", "session_created"),
        trace("s1", "final_transcript_accepted", turn_id="t1"),
        trace("s1", "turn_interpreted", turn_id="t1", outcome="field_answer"),
        trace("s1", "response_released", turn_id="t1", latency_ms=1000),
        trace("s2", "session_created"),
        trace("s2", "final_transcript_accepted", turn_id="t2"),
        trace("s2", "interpreter_failed", turn_id="t2", outcome="failed_closed"),
        trace("s2", "response_released", turn_id="t2", latency_ms=4000),
    ]

    result = service().aggregate(states, events)

    assert result["session_count"] == 2
    assert result["turn_count"] == 2
    assert result["interpreter_success_rate_pct"] == 50.0
    assert result["response_latency_p50_ms"] == 2500.0
    assert result["response_latency_p95_ms"] == 4000.0
    assert result["latency_target_attainment_pct"] == 50.0
    assert result["failed_closed_count"] == 1
    assert result["hard_failure_count"] == 0


def test_session_summaries_keep_sessions_independently_selectable():
    state = ConversationState(
        session_id="session-choice",
        application_id="application-choice",
        participant_id="borrower-choice",
    )
    events = [
        trace("session-choice", "session_created"),
        trace("session-choice", "final_transcript_accepted", turn_id="turn-1"),
        trace("session-choice", "turn_interpreted", turn_id="turn-1"),
    ]

    summaries = service().session_summaries([state], events)

    assert summaries[0]["session_id"] == "session-choice"
    assert summaries[0]["turn_count"] == 1
    assert summaries[0]["verdict"] == "pass"
