import json
from pathlib import Path


def test_all_fifteen_canonical_scenarios_are_frozen_and_uniquely_named():
    path = Path(__file__).parent / "fixtures" / "canonical_scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    assert len(scenarios) == 15
    assert {item["id"] for item in scenarios} == {
        f"S{index:02d}" for index in range(1, 16)
    }
    assert len({item["name"] for item in scenarios}) == 15
    assert all(item["hard_assertion"] for item in scenarios)
