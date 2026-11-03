"""Error-detection experiment: mutations and scoring."""
from pathlib import Path

import pytest

from kkh.benchmark import detection as D


def test_every_mutation_applies_exactly_and_changes_the_model():
    frozen = (D.FROZEN / D.CLASS_REL).read_text(encoding="utf-8")
    for m in D.MUTATIONS:
        out = m["apply"](frozen)
        assert (out == frozen) == (m["entity"] is None), m["id"]


def test_affirmation_filter_and_scoring():
    m = next(x for x in D.MUTATIONS if x["id"] == "M1-axis-sign")
    findings = [
        {"entity": "waist", "category": "joint_type", "explanation": "Axis (0,0,1) and n = {0,0,1}. Consistent."},
        {"entity": "elbow", "category": "joint_type", "explanation": "This is inconsistent because the axis is reversed."},
    ]
    assert D.is_affirmation(findings[0]) and not D.is_affirmation(findings[1])
    s = D.score(m, findings)
    assert s["detected"] is True and s["accepted_category"] is False  # localised, wrong category
    assert s["false_positives"] == 0 and s["strict_false_positives"] == 1 and s["affirmations_filtered"] == 1
