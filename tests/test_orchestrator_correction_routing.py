from saarthi.domain.contracts import CommittedFieldValue
from saarthi.domain.enums import ChangeKind, FieldId, TurnAct, TurnRoute


async def test_existing_field_answer_is_confirmed_before_correction(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter, build_test_orchestrator

    from saarthi.storage.repository import InMemoryStateRepository

    application.fields[FieldId.PREFERRED_TENURE] = CommittedFieldValue(
        field_id=FieldId.PREFERRED_TENURE,
        typed_value=12,
        source_turn_id="earlier-turn",
        source_span="twelve months",
        normalizer_version="test",
        validator_version="test",
        committed_at_revision=1,
        last_change_kind=ChangeKind.INITIAL,
    )
    application.revision = 1
    conversation.pending_field = None
    conversation.linked_application_revision = 1

    correction_text = "Update that tenure to six months."
    confirmation_text = "yes"
    interpreter = ScriptedInterpreter(
        {
            correction_text: proposal_factory(
                route=TurnRoute.FIELD_ANSWER,
                acts=[TurnAct.ANSWER],
                target=FieldId.PREFERRED_TENURE,
                value=6,
                explicit_write=True,
                rationale="model_called_existing_value_an_answer",
            ),
            confirmation_text: proposal_factory(
                route=TurnRoute.FIELD_ANSWER,
                acts=[TurnAct.ANSWER],
                target=FieldId.PREFERRED_TENURE,
                value=6,
                explicit_write=True,
                rationale="confirmed_pending_write",
            ),
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    orchestrator = build_test_orchestrator(repository, interpreter)

    first = await orchestrator.process_final_transcript(
        transcript_factory(correction_text)
    )

    assert first.draft.fields[FieldId.PREFERRED_TENURE].typed_value == 12
    assert first.state.pending_write_confirmation is not None
    assert first.response_plan.purpose == "confirm_correction"
    assert "change it to 6" in " ".join(first.response_plan.message_segments)

    second = await orchestrator.process_final_transcript(
        transcript_factory(confirmation_text)
    )

    assert second.commit_result is not None
    assert second.commit_result.accepted
    assert second.draft.fields[FieldId.PREFERRED_TENURE].typed_value == 6
    assert second.state.pending_write_confirmation is None
