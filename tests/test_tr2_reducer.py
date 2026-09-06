from saarthi.domain.contracts import ApplicationPatch
from saarthi.domain.enums import ChangeKind, FieldId
from saarthi.domain.reducer import GuardedReducer


def patch(application, **overrides) -> ApplicationPatch:
    values = {
        "idempotency_key": "turn-1:proposal-1",
        "session_id": application.owner_session_id,
        "application_id": application.application_id,
        "expected_application_revision": application.revision,
        "source_turn_id": "turn-1",
        "source_generation_id": 1,
        "target_field": FieldId.REQUESTED_AMOUNT,
        "normalized_candidate": 100000,
        "source_span": "one lakh rupees",
        "explicit_target": True,
    }
    values.update(overrides)
    return ApplicationPatch(**values)


def test_valid_patch_changes_exactly_one_field_and_one_revision(application):
    result = GuardedReducer().apply(application, patch(application), current_generation_id=1)
    assert result.accepted
    assert result.new_revision == 1
    assert set(result.draft.fields) == {FieldId.REQUESTED_AMOUNT}
    assert application.revision == 0
    assert application.fields == {}


def test_stale_generation_has_no_effect(application):
    result = GuardedReducer().apply(application, patch(application), current_generation_id=2)
    assert not result.accepted
    assert result.reason_code == "stale_generation"
    assert result.new_revision == application.revision


def test_revision_conflict_has_no_effect(application):
    result = GuardedReducer().apply(
        application,
        patch(application, expected_application_revision=9),
        current_generation_id=1,
    )
    assert not result.accepted
    assert result.reason_code == "application_revision_conflict"


def test_unconfirmed_correction_is_rejected(application):
    reducer = GuardedReducer()
    first = reducer.apply(application, patch(application), current_generation_id=1).draft
    correction = patch(
        first,
        idempotency_key="turn-2:proposal-2",
        expected_application_revision=1,
        source_turn_id="turn-2",
        source_generation_id=2,
        normalized_candidate=80000,
        confirmation_required=True,
        confirmed=False,
        change_kind=ChangeKind.CORRECTION,
    )
    result = reducer.apply(first, correction, current_generation_id=2)
    assert not result.accepted
    assert result.reason_code == "confirmation_required"
    assert first.fields[FieldId.REQUESTED_AMOUNT].typed_value == 100000


def test_confirmed_correction_changes_only_target(application):
    reducer = GuardedReducer()
    first = reducer.apply(application, patch(application), current_generation_id=1).draft
    second_patch = patch(
        first,
        idempotency_key="turn-2:purpose",
        expected_application_revision=1,
        source_turn_id="turn-2",
        source_generation_id=2,
        target_field=FieldId.LOAN_PURPOSE,
        normalized_candidate="education",
    )
    second = reducer.apply(first, second_patch, current_generation_id=2).draft
    correction = patch(
        second,
        idempotency_key="turn-3:correction",
        expected_application_revision=2,
        source_turn_id="turn-3",
        source_generation_id=3,
        normalized_candidate=80000,
        confirmation_required=True,
        confirmed=True,
        change_kind=ChangeKind.CORRECTION,
    )
    result = reducer.apply(second, correction, current_generation_id=3)
    assert result.accepted
    assert result.draft.fields[FieldId.REQUESTED_AMOUNT].typed_value == 80000
    assert result.draft.fields[FieldId.LOAN_PURPOSE].typed_value == "education"
    assert len(result.draft.change_history) == 3


def test_out_of_range_amount_is_rejected(application):
    result = GuardedReducer().apply(
        application,
        patch(application, normalized_candidate=400000),
        current_generation_id=1,
    )
    assert not result.accepted
    assert result.reason_code == "invalid_field_value"
