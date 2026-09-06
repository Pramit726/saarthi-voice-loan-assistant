from saarthi.domain.contracts import TraceEvent
from saarthi.domain.enums import Verdict
from saarthi.services.acceptance import AcceptanceService


def event(name: str) -> TraceEvent:
    return TraceEvent(
        event_type=name,
        session_id="s",
        application_id="a",
        trace_id="t",
        component="test",
        outcome="observed",
        generation_id=1,
        application_revision=0,
        state_version=1,
    )


def test_missing_evidence_is_inconclusive_not_pass():
    result = AcceptanceService().evaluate([event("session_created")])
    assert result.verdict is Verdict.INCONCLUSIVE


def test_any_hard_failure_forces_fail():
    result = AcceptanceService().evaluate(
        [event("session_created"), event("final_transcript_accepted"), event("turn_interpreted"), event("unsupported_claim_released")]
    )
    assert result.verdict is Verdict.FAIL


def test_complete_safe_trace_passes():
    result = AcceptanceService().evaluate(
        [event("session_created"), event("final_transcript_accepted"), event("turn_interpreted")]
    )
    assert result.verdict is Verdict.PASS
