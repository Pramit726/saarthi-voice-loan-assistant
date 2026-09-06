from saarthi.domain.contracts import TraceEvent
from saarthi.services.replay import TraceReplayService


def patch_event(previous: int, current: int, field: str, value) -> TraceEvent:
    return TraceEvent(
        event_type="application_patch_decided",
        session_id="s",
        application_id="a",
        trace_id="t",
        component="guarded_reducer",
        outcome="committed",
        generation_id=current,
        application_revision=current,
        state_version=current,
        payload={
            "accepted": True,
            "changed_field": field,
            "new_value": value,
            "previous_revision": previous,
            "new_revision": current,
        },
    )


def test_replay_reconstructs_corrections_in_order():
    fields, revision = TraceReplayService().replay_fields(
        [
            patch_event(0, 1, "requested_amount", "100000.00"),
            patch_event(1, 2, "loan_purpose", "education"),
            patch_event(2, 3, "requested_amount", "80000.00"),
        ]
    )
    assert revision == 3
    assert fields == {"requested_amount": "80000.00", "loan_purpose": "education"}
