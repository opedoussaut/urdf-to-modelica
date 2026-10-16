import pytest
import json
from kkh.rag.repair import repair


def test_invalid_candidate_requires_validation_before_acceptance():
    calls = []
    def evaluate(value, index):
        calls.append(value)
        return {"engineering_valid": value == -1, "parameter_correct": value == -1}
    outputs = iter(["1", "-1", "999"])
    attempts = repair([], lambda _: {"content": next(outputs)}, int, evaluate, max_attempts=3)
    assert calls == [1, -1]
    assert attempts[-1]["engineering_valid"]
    diagnostics = json.loads(attempts[1]["prompt"][-1]["content"].split("Diagnostics (no target answer): ", 1)[1])
    assert not {"expected", "target", "answer"}.intersection(diagnostics)


def test_repair_budget_and_invalid_response():
    with pytest.raises(ValueError):
        repair([], None, None, None, max_attempts=100)
    attempts = repair([], lambda _: {"content": "not-a-number"}, int, lambda *_: pytest.fail("Should not evaluate invalid source"), max_attempts=2)
    assert len(attempts) == 2
    assert all(not a["engineering_valid"] for a in attempts)
