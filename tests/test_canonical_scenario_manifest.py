import json
from pathlib import Path


def test_all_sixteen_canonical_scenarios_are_frozen_and_uniquely_named():
    path = Path(__file__).parent / "fixtures" / "canonical_scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    assert len(scenarios) == 16
    assert {item["id"] for item in scenarios} == {
        f"S{index:02d}" for index in range(1, 17)
    }
    assert len({item["name"] for item in scenarios}) == 16
    assert all(item["hard_assertion"] for item in scenarios)
