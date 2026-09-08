from saarthi.domain.contracts import TurnProposal
from saarthi.domain.enums import FieldId, TurnAct, TurnRoute
from saarthi.providers.groq import InterpretationPayload
from saarthi.services.interpreter import (
    RetrievedFewShotInterpreter,
    control_command_for_text,
    is_calculation_request,
)


def payload(**overrides) -> InterpretationPayload:
    values = {
        "acts": ["answer"],
        "route": "field_answer",
        "target_field": "requested_amount",
        "candidate_value": 100000,
        "source_span": "one lakh",
        "reference_resolution": "pending_field",
        "control": None,
        "uncertainty": 0.05,
        "rationale_code": "plain_answer",
        "explicit_write": True,
    }
    values.update(overrides)
    return InterpretationPayload.model_validate(values)


def test_plain_explicit_answer_remains_write_candidate(
    transcript_factory, conversation
):
    result = RetrievedFewShotInterpreter._guard(
        payload(), transcript_factory("one lakh"), conversation
    )
    assert result.route is TurnRoute.FIELD_ANSWER
    assert result.target_field is FieldId.REQUESTED_AMOUNT
    assert result.explicit_write is True


def test_plain_current_field_answer_does_not_depend_on_model_write_flag(
    transcript_factory, conversation
):
    conversation.pending_field = FieldId.PREFERRED_TENURE
    result = RetrievedFewShotInterpreter._guard(
        payload(
            target_field="preferred_tenure",
            candidate_value=12,
            source_span="Twelve months.",
            explicit_write=False,
        ),
        transcript_factory("Twelve months."),
        conversation,
    )
    assert result.target_field is FieldId.PREFERRED_TENURE
    assert result.candidate_value == 12
    assert result.explicit_write is True


def test_plain_answer_for_non_pending_field_is_not_implicitly_writable(
    transcript_factory, conversation
):
    result = RetrievedFewShotInterpreter._guard(
        payload(
            target_field="preferred_tenure", candidate_value=12, explicit_write=False
        ),
        transcript_factory("Twelve months."),
        conversation,
    )
    assert result.target_field is FieldId.PREFERRED_TENURE
    assert result.explicit_write is False


def test_question_can_never_become_write_candidate(transcript_factory, conversation):
    result = RetrievedFewShotInterpreter._guard(
        payload(
            acts=["doubt"],
            route="product_question",
            candidate_value=None,
            explicit_write=True,
        ),
        transcript_factory("what is the processing fee?"),
        conversation,
    )
    assert result.acts == [TurnAct.DOUBT]
    assert result.explicit_write is False


def test_mixed_answer_and_doubt_is_held(transcript_factory, conversation):
    result = RetrievedFewShotInterpreter._guard(
        payload(
            acts=["answer", "doubt", "mixed"],
            route="calculation",
            candidate_value=100000,
        ),
        transcript_factory("one lakh, but what will I receive?"),
        conversation,
    )
    assert TurnAct.MIXED in result.acts
    assert result.explicit_write is False


def test_low_stt_confidence_forces_clarification(transcript_factory, conversation):
    result = RetrievedFewShotInterpreter._guard(
        payload(), transcript_factory("one lakh", confidence=0.42), conversation
    )
    assert result.route is TurnRoute.CLARIFICATION
    assert result.explicit_write is False
    assert result.rationale_code == "low_stt_confidence"


def test_hedged_value_forces_clarification_even_when_model_says_answer(
    transcript_factory, conversation
):
    conversation.pending_field = FieldId.MONTHLY_INCOME
    result = RetrievedFewShotInterpreter._guard(
        payload(
            target_field="monthly_income",
            candidate_value=80000,
            source_span="probably around eighty thousand",
            explicit_write=True,
        ),
        transcript_factory("It is probably around eighty thousand."),
        conversation,
    )
    assert result.route is TurnRoute.CLARIFICATION
    assert result.target_field is FieldId.MONTHLY_INCOME
    assert result.candidate_value == 80000
    assert result.explicit_write is False
    assert result.rationale_code == "hedged_value"


async def test_hedged_money_is_understood_without_calling_the_llm(
    transcript_factory, conversation
):
    conversation.pending_field = FieldId.MONTHLY_INCOME
    interpreter = RetrievedFewShotInterpreter(client=None)  # type: ignore[arg-type]

    result = await interpreter.interpret(
        transcript_factory("It is probably around eighty thousand."), conversation
    )

    assert result.route is TurnRoute.CLARIFICATION
    assert result.target_field is FieldId.MONTHLY_INCOME
    assert result.candidate_value == 80000
    assert result.explicit_write is False
    assert result.rationale_code == "hedged_value"


async def test_valid_plain_money_answer_bypasses_the_llm(
    transcript_factory, conversation
):
    interpreter = RetrievedFewShotInterpreter(client=None)  # type: ignore[arg-type]

    result = await interpreter.interpret(
        transcript_factory("one lakh rupees"), conversation
    )

    assert result.route is TurnRoute.FIELD_ANSWER
    assert result.target_field is FieldId.REQUESTED_AMOUNT
    assert result.candidate_value == 100000
    assert result.rationale_code == "deterministic_valid_field_answer"


async def test_spoken_tenure_answer_bypasses_the_llm(transcript_factory, conversation):
    conversation.pending_field = FieldId.PREFERRED_TENURE
    interpreter = RetrievedFewShotInterpreter(client=None)  # type: ignore[arg-type]

    result = await interpreter.interpret(
        transcript_factory("twelve months"), conversation
    )

    assert result.candidate_value == 12
    assert result.explicit_write is True


def test_questions_and_low_confidence_turns_do_not_use_plain_answer_fast_path(
    transcript_factory, conversation
):
    conversation.pending_field = FieldId.PREFERRED_TENURE
    assert (
        RetrievedFewShotInterpreter._direct_plain_answer(
            transcript_factory("what does tenure mean"), conversation
        )
        is None
    )
    assert (
        RetrievedFewShotInterpreter._direct_plain_answer(
            transcript_factory("twelve months", confidence=0.42), conversation
        )
        is None
    )


def test_uncertainty_is_not_committed_as_free_text(transcript_factory, conversation):
    conversation.pending_field = FieldId.LOAN_PURPOSE

    assert (
        RetrievedFewShotInterpreter._direct_plain_answer(
            transcript_factory("I don't know"), conversation
        )
        is None
    )


def test_control_is_resolved_without_llm(transcript_factory):
    result = RetrievedFewShotInterpreter._direct_control(
        transcript_factory("please stop speaking")
    )
    assert result is not None
    assert result.route is TurnRoute.CONTROL
    assert result.explicit_write is False


def test_voice_control_variants_are_resolved_without_llm(transcript_factory):
    for text in ("stop", "pause", "repeat that", "go back", "show my draft"):
        result = RetrievedFewShotInterpreter._direct_control(transcript_factory(text))
        assert result is not None
        assert result.route is TurnRoute.CONTROL
        assert result.explicit_write is False


def test_control_text_normalization_handles_voice_spacing():
    assert control_command_for_text("  Repeat   that. ").value == "repeat"
    assert control_command_for_text("Show my draft").value == "show_summary"


def test_projection_questions_are_routed_deterministically():
    assert is_calculation_request("If I choose twelve months, what would the EMI be?")
    assert is_calculation_request("How much would reach my account?")
    assert not is_calculation_request("Is the processing fee included in EMI?")


def test_low_confidence_projection_question_is_not_directly_accepted(
    transcript_factory,
):
    result = RetrievedFewShotInterpreter._direct_calculation(
        transcript_factory("What would my EMI be?", confidence=0.42)
    )
    assert result is None


async def test_cancel_that_rejects_pending_change_instead_of_cancelling_draft(
    transcript_factory, conversation
):
    conversation.pending_write_confirmation = TurnProposal(
        source_transcript_id="turn-old",
        acts=[TurnAct.CORRECTION],
        route=TurnRoute.CORRECTION,
        target_field=FieldId.PREFERRED_TENURE,
        candidate_value=6,
        source_span="six months",
        rationale_code="pending_correction",
        explicit_write=True,
    )
    result = await RetrievedFewShotInterpreter(
        client=None  # type: ignore[arg-type]
    ).interpret(transcript_factory("cancel that"), conversation)
    assert result.rationale_code == "discard_pending_write"
    assert result.route is TurnRoute.FALLBACK


async def test_spoken_punctuation_does_not_break_pending_confirmation(
    transcript_factory, conversation
):
    conversation.pending_write_confirmation = TurnProposal(
        source_transcript_id="turn-old",
        acts=[TurnAct.CORRECTION],
        route=TurnRoute.CORRECTION,
        target_field=FieldId.REQUESTED_AMOUNT,
        candidate_value=80000,
        source_span="eighty thousand",
        rationale_code="pending_correction",
        explicit_write=True,
    )
    result = await RetrievedFewShotInterpreter(
        client=None  # type: ignore[arg-type]
    ).interpret(transcript_factory("Yes, go ahead."), conversation)
    assert result.rationale_code == "confirmed_pending_write"
    assert result.candidate_value == 80000
