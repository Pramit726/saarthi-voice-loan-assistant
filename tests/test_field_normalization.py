import pytest

from saarthi.domain.enums import FieldId
from saarthi.domain.fields import normalise_and_validate


@pytest.mark.parametrize(
    ("spoken_answer", "expected_city"),
    [
        ("Pune", "Pune"),
        ("my city is Pune", "Pune"),
        ("The city would be Bengaluru.", "Bengaluru"),
        ("I live in New Delhi", "New Delhi"),
        ("I am from Navi Mumbai", "Navi Mumbai"),
        ("please record my city as Pune, Maharashtra", "Pune"),
    ],
)
def test_city_normalizer_extracts_city_from_spoken_answer(
    spoken_answer: str, expected_city: str
) -> None:
    assert normalise_and_validate(FieldId.CITY, spoken_answer) == expected_city
