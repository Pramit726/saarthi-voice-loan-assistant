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
    orchestrator = build_test_orchestrator(repository, interpreter)
    await repository.create(application, conversation)

    first = await orchestrator.process_final_transcript(
        transcript_factory(correction_text)
    )

    assert first.draft.fields[FieldId.PREFERRED_TENURE].typed_value == 12
    assert first.state.pending_write_confirmation is not None
    assert first.response_plan.purpose == "confirm_correction"
    assert "change it to 6 months" in " ".join(first.response_plan.message_segments)

    second = await orchestrator.process_final_transcript(
        transcript_factory(confirmation_text)
    )

    assert second.commit_result is not None
    assert second.commit_result.accepted
    assert second.draft.fields[FieldId.PREFERRED_TENURE].typed_value == 6
    assert second.state.pending_field is FieldId.REQUESTED_AMOUNT
    assert "Next question" in " ".join(second.response_plan.message_segments)
    assert "loan amount" in " ".join(second.response_plan.message_segments)
    assert second.state.pending_write_confirmation is None


async def test_confirmed_amount_correction_asks_next_unanswered_field(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter, build_test_orchestrator

    from saarthi.storage.repository import InMemoryStateRepository

    values = {
        FieldId.REQUESTED_AMOUNT: 100000,
        FieldId.LOAN_PURPOSE: "home renovation",
        FieldId.PREFERRED_TENURE: 12,
        FieldId.EMPLOYMENT_TYPE: "salaried",
    }
    for field_id, value in values.items():
        application.fields[field_id] = CommittedFieldValue(
            field_id=field_id,
            typed_value=value,
            source_turn_id="earlier-turn",
            source_span=str(value),
            normalizer_version="test",
            validator_version="test",
            committed_at_revision=1,
            last_change_kind=ChangeKind.INITIAL,
        )
    application.revision = 4
    conversation.pending_field = FieldId.MONTHLY_INCOME
    conversation.linked_application_revision = 4

    correction_text = "Update the loan amount to eighty thousand."
    confirmation_text = "yes"
    interpreter = ScriptedInterpreter(
        {
            correction_text: proposal_factory(
                route=TurnRoute.CORRECTION,
                acts=[TurnAct.CORRECTION],
                target=FieldId.REQUESTED_AMOUNT,
                value=80000,
                explicit_write=True,
                rationale="user_correction",
            ),
            confirmation_text: proposal_factory(
                route=TurnRoute.CORRECTION,
                acts=[TurnAct.CORRECTION],
                target=FieldId.REQUESTED_AMOUNT,
                value=80000,
                explicit_write=True,
                rationale="confirmed_pending_write",
            ),
        }
    )
    repository = InMemoryStateRepository()
    orchestrator = build_test_orchestrator(repository, interpreter)
    application.current_projection = orchestrator.grounding.calculator.calculate(
        application
    )
    old_projection_id = application.current_projection.projection_id
    await repository.create(application, conversation)

    await orchestrator.process_final_transcript(transcript_factory(correction_text))
    result = await orchestrator.process_final_transcript(
        transcript_factory(confirmation_text)
    )

    assert result.commit_result is not None and result.commit_result.accepted
    assert result.draft.fields[FieldId.REQUESTED_AMOUNT].typed_value == 80000
    assert result.state.pending_field is FieldId.MONTHLY_INCOME
    response = " ".join(result.response_plan.message_segments)
    assert "Next question" in response
    assert "monthly take-home income" in response
    assert result.draft.current_projection is not None
    assert result.draft.current_projection.projection_id != old_projection_id
    assert result.draft.current_projection.requested_amount == 80000
    assert result.draft.current_projection.source_application_revision == 5
    events = await repository.list_events(conversation.session_id)
    assert any(event.event_type == "projection_invalidated" for event in events)
    assert any(event.event_type == "projection_refreshed" for event in events)


async def test_affirmation_after_interrupted_correction_repeats_current_prompt(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter, build_test_orchestrator

    from saarthi.storage.repository import InMemoryStateRepository

    application.fields[FieldId.REQUESTED_AMOUNT] = CommittedFieldValue(
        field_id=FieldId.REQUESTED_AMOUNT,
        typed_value=80000,
        source_turn_id="earlier-turn",
        source_span="eighty thousand",
        normalizer_version="test",
        validator_version="test",
        committed_at_revision=1,
        last_change_kind=ChangeKind.INITIAL,
    )
    application.revision = 1
    conversation.pending_field = FieldId.CITY
    conversation.last_safe_prompt = "Which city should the demonstration draft record?"
    conversation.linked_application_revision = 1
    interpreter = ScriptedInterpreter(
        {
            "okay": proposal_factory(
                route=TurnRoute.FIELD_ANSWER,
                acts=[TurnAct.AMBIGUOUS],
                target=FieldId.CITY,
                value=None,
                explicit_write=False,
                rationale="non_specific_confirmation",
            )
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    orchestrator = build_test_orchestrator(repository, interpreter)

    result = await orchestrator.process_final_transcript(transcript_factory("okay"))

    assert result.response_plan.purpose == "resume_prompt"
    assert result.response_plan.message_segments == [
        "Which city should the demonstration draft record?"
    ]
    assert result.draft.revision == 1


async def test_hedged_income_is_confirmed_before_commit(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter, build_test_orchestrator

    from saarthi.storage.repository import InMemoryStateRepository

    conversation.pending_field = FieldId.MONTHLY_INCOME
    interpreter = ScriptedInterpreter(
        {
            "It is probably around eighty thousand.": proposal_factory(
                route=TurnRoute.CLARIFICATION,
                acts=[TurnAct.AMBIGUOUS],
                target=FieldId.MONTHLY_INCOME,
                value=80000,
                explicit_write=False,
                rationale="hedged_value",
            )
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    orchestrator = build_test_orchestrator(repository, interpreter)

    result = await orchestrator.process_final_transcript(
        transcript_factory("It is probably around eighty thousand.")
    )

    assert result.commit_result is None
    assert result.draft.revision == 0
    assert result.response_plan.purpose == "clarify_hedged_value"
    assert result.response_plan.message_segments == [
        "I understood your monthly income as 80,000 rupees. Should I record that?"
    ]


async def test_fuzzy_city_candidate_is_held_for_confirmation(
    application,
    conversation,
    transcript_factory,
    proposal_factory,
):
    from conftest import ScriptedInterpreter, build_test_orchestrator

    from saarthi.storage.repository import InMemoryStateRepository

    conversation.pending_field = FieldId.CITY
    interpreter = ScriptedInterpreter(
        {
            "Bangaloroo": proposal_factory(
                route=TurnRoute.CLARIFICATION,
                acts=[TurnAct.AMBIGUOUS],
                target=FieldId.CITY,
                value="Bengaluru",
                explicit_write=False,
                rationale="fuzzy_city_candidate",
            )
        }
    )
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    orchestrator = build_test_orchestrator(repository, interpreter)

    result = await orchestrator.process_final_transcript(
        transcript_factory("Bangaloroo")
    )

    assert result.commit_result is None
    assert result.draft.revision == 0
    assert result.state.pending_write_confirmation is not None
    assert result.response_plan.purpose == "confirm_resolved_candidate"
    assert "Bengaluru" in result.response_plan.message_segments[0]
