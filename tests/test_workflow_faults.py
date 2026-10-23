"""Fault set v1 for the repair experiment: frozen, pinned to the Stage 1 output, one exact edit per fault."""
import pytest

from kkh.convert import urdfmodelica
from kkh.workflow import faults as F
from kkh.workflow import stage1_convert as s1
from kkh.workflow import stage2_check as s2

needs_converter = pytest.mark.skipif(not (urdfmodelica.UMO / "Resources" / "urdf_to_package.py").exists(),
                                     reason="pinned URDFModelica not fetched")


def test_fault_set_is_well_formed():
    ids = [f["id"] for f in F.FAULTS]
    assert ids == [f"F{i:02d}" for i in range(1, 11)] and len(set(ids)) == len(ids)
    assert all(f["category"] in s2.CATEGORIES for f in F.FAULTS)
    assert {f["id"] for f in F.FAULTS if f["held_out"]} == {"F08", "F09", "F10"}
    assert len({f["category"] for f in F.FAULTS}) >= 6  # spread over the mission taxonomy
    assert all(f["restored"][0] in ("present", "absent") for f in F.FAULTS)
    assert F.set_digest() == F.set_digest()


@needs_converter
def test_every_fault_applies_once_to_the_pinned_files_and_is_detectably_undone(tmp_path):
    s1.run("aloha_vx300s", tmp_path, check_reproducible=False, log=lambda *_: None)
    made = F.build(tmp_path, tmp_path / "faults")
    assert len(made) == 10 and all(m["sha_before"] != m["sha_after"] for m in made)
    for f in F.FAULTS:
        assert F.restored(f, F.stage1_ws(tmp_path))  # the original satisfies every restore condition
        assert not F.restored(f, tmp_path / "faults" / f["id"] / "ws")  # each faulted copy does not
    with pytest.raises(ValueError):  # applying to a file that is not the pinned one is refused
        F.apply(F.FAULTS[0], tmp_path / "faults" / "F01" / "ws", expected_sha=made[0]["sha_before"])
