import pytest
from pydantic import ValidationError

from saarthi.api.schemas import SessionCreateRequest


def test_session_creation_uses_fixed_english_profile() -> None:
    assert SessionCreateRequest().language == "en-IN"
    assert SessionCreateRequest(language="en-IN").language == "en-IN"


def test_session_creation_rejects_removed_hindi_profile() -> None:
    with pytest.raises(ValidationError):
        SessionCreateRequest(language="hi-IN")
