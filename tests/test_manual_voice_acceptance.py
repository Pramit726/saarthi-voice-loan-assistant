import pytest

pytestmark = [
    pytest.mark.manual,
    pytest.mark.skip(reason="Requires two listeners and a live voice session"),
]


def test_rime_financial_pairwise_listening_sheet():
    """Manual gate: critical value-label pairs must be intelligible and natural to both listeners."""
    raise NotImplementedError


def test_live_barge_in_user_facing_stop_latency():
    """Manual gate: measure microphone barge-in to audible stop; p95 target is at most 500 ms."""
    raise NotImplementedError
