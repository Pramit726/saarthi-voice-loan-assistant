from saarthi.domain.enums import FieldId, TurnAct, TurnRoute
from saarthi.providers.groq import InterpretationPayload
from saarthi.services.interpreter import RetrievedFewShotInterpreter


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


def test_plain_explicit_answer_remains_write_candidate(transcript_factory, conversation):
    result = RetrievedFewShotInterpreter._guard(payload(), transcript_factory("one lakh"), conversation)
    assert result.route is TurnRoute.FIELD_ANSWER
    assert result.target_field is FieldId.REQUESTED_AMOUNT
    assert result.explicit_write is True


def test_question_can_never_become_write_candidate(transcript_factory, conversation):
    result = RetrievedFewShotInterpreter._guard(
        payload(acts=["doubt"], route="product_question", candidate_value=None, explicit_write=True),
        transcript_factory("what is the processing fee?"),
        conversation,
    )
    assert result.acts == [TurnAct.DOUBT]
    assert result.explicit_write is False


def test_mixed_answer_and_doubt_is_held(transcript_factory, conversation):
    result = RetrievedFewShotInterpreter._guard(
        payload(acts=["answer", "doubt", "mixed"], route="calculation", candidate_value=100000),
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


def test_control_is_resolved_without_llm(transcript_factory):
    result = RetrievedFewShotInterpreter._direct_control(transcript_factory("please stop speaking"))
    assert result is not None
    assert result.route is TurnRoute.CONTROL
    assert result.explicit_write is False
