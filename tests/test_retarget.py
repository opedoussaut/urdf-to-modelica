"""Step 5: leader demonstration -> retargeted follower attempt (world-frame IK) -> follower-joint reference."""
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from kkh import scenarios as S
from kkh.domain.aloha import retarget as RT
from kkh.domain.aloha import scenario_binding as B
from kkh.studio import robotics as R

sys.path.insert(0, str(Path(__file__).parent))
from test_workspace_frames import _demonstration  # noqa: E402  (scripted shared-table demonstration)

SHARED = "experimental_shared_table"


@pytest.fixture(scope="module")
def demo():
    sc = S.load("aloha2-cube-transfer-shared")
    t, rows = _demonstration(sc)
    data = R.trajectory({"configuration_id": R.CONFIG_ID, "joint_ids": R.JOINTS, "time": t, "q": rows,
                         "scenario": {"id": sc["id"], "version": sc["version"], "sha256": sc["sha256"]}})
    return sc, data, RT.retarget(data, SHARED)


def test_retargeted_attempt_reproduces_the_demonstrated_gripper_path(demo):
    sc, data, out = demo
    report = out["report"]
    assert report["within_tolerance_fraction"] == 1.0
    assert report["position_error_m"]["max"] <= RT.POSITION_TOLERANCE_M
    assert report["approach_tilt_error_deg"]["max"] <= RT.TILT_TOLERANCE_DEG
    ee_leader, op_leader = B.signals(data["q"], sc, "leader")
    ee_follower, op_follower = B.follower_signals(out["data"]["q"], sc)
    assert np.max(np.linalg.norm(ee_leader - ee_follower, axis=1)) <= RT.POSITION_TOLERANCE_M
    assert np.allclose(op_leader, op_follower, atol=1e-9)  # normalised opening transferred


def test_attempt_is_honestly_labelled_and_gates_stay_closed(demo):
    _, _, out = demo
    d, checked = out["data"], out["report"]["checked"]
    assert d["reference_space"] == "follower_joints" and d["derived"]["kind"] == "retargeted_follower_attempt"
    for gate in ("collision", "contact", "hardware_registration", "grasp_orientation_about_vertical"):
        assert checked[gate] is False
    assert "no collision or contact model" in d["provenance"]


def test_follower_joint_recordings_are_validated_against_follower_limits(demo):
    _, _, out = demo
    validated = R.trajectory(out["data"])
    assert validated["reference_space"] == "follower_joints"
    bad = dict(out["data"])
    bad["q"] = [list(r) for r in out["data"]["q"]]
    bad["q"][0][1] = 3.0  # beyond the follower shoulder limit
    with pytest.raises(ValueError):
        R.trajectory(bad)
    with pytest.raises(ValueError):
        R.trajectory({**out["data"], "reference_space": "camera_pixels"})
    with pytest.raises(ValueError):
        RT.retarget(validated, SHARED)  # an attempt cannot be retargeted again


def test_kinematic_attempt_completes_the_task_and_cannot_be_scored_as_leader(demo):
    sc, data, out = demo
    attempt = R.trajectory(out["data"])
    result = S.evaluate_recording(attempt)
    assert result["metrics"]["task_completed"]
    assert result["evaluated_on"]["title"] == "Follower attempt (retargeted, kinematic)"
    with pytest.raises(ValueError):
        S.evaluate_recording(attempt, manipulator="leader")
    # contrast: the joint-mapped replay of the same demonstration does not complete the task
    assert not S.evaluate_recording(data, manipulator="follower")["metrics"]["task_completed"]


def test_openmodelica_reference_uses_follower_joints_without_remapping(demo, tmp_path):
    from kkh.studio.dynamics import generate
    from kkh.studio.models import BASELINE
    _, _, out = demo
    attempt = R.trajectory(out["data"])
    generate(tmp_path / "ALOHA2", attempt, axes=1, source_package=BASELINE)
    text = (tmp_path / "ALOHA2" / "RecordedFollower.mo").read_text(encoding="utf-8")
    first = text.split("table=[", 1)[1].split(";", 1)[0].split(",")
    assert [float(v) for v in first[1:]] == pytest.approx(attempt["q"][0])


def test_api_creates_derived_attempt_and_rejects_invalid_sources(demo, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from kkh.api.main import app
    import kkh.studio.api as api
    from kkh.studio.storage import Store
    monkeypatch.setattr(api, "store", Store(tmp_path / "api.sqlite"))
    client = TestClient(app)
    sc, data, _ = demo
    body = {k: data[k] for k in ("configuration_id", "joint_ids", "time", "q")}
    saved = client.post("/api/workbench/documents/trajectory", json={"name": "shared demo", "data": {
        **body, "scenario": {"id": sc["id"], "version": sc["version"]}}}).json()
    job = client.post(f"/api/workbench/trajectory/{saved['id']}/retarget").json()
    for _ in range(300):
        state = client.get(f"/api/workbench/job/{job['id']}").json()
        if state["data"]["status"] != "running":
            break
        time.sleep(0.1)
    assert state["data"]["status"] == "complete", state
    result = state["data"]["result"]
    attempt = result["record"]
    assert attempt["data"]["derived"]["source"] == saved["id"] and result["task"]["metrics"]["task_completed"]
    # an attempt and a legacy-frame recording cannot be retargeted
    assert client.post(f"/api/workbench/trajectory/{attempt['id']}/retarget").status_code == 422
    legacy = S.load("aloha2-cube-transfer")
    plain = client.post("/api/workbench/documents/trajectory", json={"name": "legacy", "data": {
        **body, "scenario": {"id": legacy["id"], "version": legacy["version"]}}}).json()
    assert client.post(f"/api/workbench/trajectory/{plain['id']}/retarget").status_code == 422
