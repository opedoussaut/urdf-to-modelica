"""Step 4C: shared workspace frames, experimental shared-table layout, task-frame binding and closed gates."""
import shutil
import subprocess

import numpy as np
import pytest

from kkh import scenarios as S
from kkh.domain.aloha import scenario_binding as B
from kkh.engineering import workspace_frames as W
from kkh.engineering.workspace_registration import legacy_offsets

SHARED = "experimental_shared_table"
LEADER_HOME_OPEN = [0.0, -0.96, 1.16, 0.0, -0.3, 0.0, 0.0, 0.037]


@pytest.mark.parametrize("name", ["legacy_side_by_side", SHARED])
@pytest.mark.parametrize("role", W.ROLES)
def test_world_local_roundtrip_both_directions(name, role):
    lay = W.layout(name)
    p = [0.123, -0.045, 0.02]
    assert W.to_world(lay, W.to_local(lay, role, p)) == pytest.approx(p)
    q = W.LocalPoint(role, (0.3, 0.12, 0.02))
    assert W.to_local(lay, role, W.to_world(lay, q)).xyz == pytest.approx(q.xyz)


def test_shared_layout_task_points_in_both_base_frames():
    lay = W.layout(SHARED)
    a, b = [0.0, -0.06, 0.02], [0.0, 0.06, 0.02]
    assert W.to_local(lay, "leader", a).xyz == pytest.approx((0.469, -0.06, 0.02))
    assert W.to_local(lay, "follower", a).xyz == pytest.approx((0.469, 0.06, 0.02))  # yaw pi flips Y
    assert W.to_local(lay, "leader", b).xyz == pytest.approx((0.469, 0.06, 0.02))
    assert W.to_local(lay, "follower", b).xyz == pytest.approx((0.469, -0.06, 0.02))
    # identical local coordinates are different world points for the two arms
    same = (0.469, 0.06, 0.02)
    assert W.to_world(lay, W.LocalPoint("leader", same)) == pytest.approx(b)
    assert W.to_world(lay, W.LocalPoint("follower", same)) == pytest.approx(a)
    # converting between robots goes through the world, never by reusing coordinates
    assert W.convert(lay, W.LocalPoint("follower", same), "leader").xyz == pytest.approx((0.469, -0.06, 0.02))


def test_points_carry_their_frame_and_reject_invalid_input():
    with pytest.raises(ValueError):
        W.LocalPoint("wrist", (0, 0, 0))
    with pytest.raises(ValueError):
        W.LocalPoint("leader", (float("nan"), 0, 0))
    with pytest.raises(ValueError):
        W.to_local(W.layout(SHARED), "camera", [0, 0, 0])
    with pytest.raises(KeyError):
        W.layout("calibrated_hardware")


def test_legacy_layout_keeps_historic_offsets_for_step4_audits():
    assert legacy_offsets() == {"follower": 0.45, "leader": -0.5}
    lay = W.layout("legacy_side_by_side")
    assert W.to_world(lay, W.LocalPoint("follower", (0.3, 0.12, 0.02))) == pytest.approx([0.75, 0.12, 0.02])


def test_step4b_candidate_needs_the_follower_to_reach_behind_itself_in_the_legacy_layout():
    """Evidence for not applying the X-translation-only candidate: follower waist near +/- pi."""
    legacy = W.check_point(W.layout("legacy_side_by_side"), [-0.08, -0.08, 0.02])
    assert legacy["follower"]["local_m"][0] < -0.5
    assert abs(legacy["follower"]["position_ik"]["waist_rad"]) > 2.5
    shared = W.check_point(W.layout(SHARED), [-0.08, -0.08, 0.02])
    assert all(abs(shared[r]["position_ik"]["waist_rad"]) < 0.5 for r in W.ROLES)


def test_shared_scenario_is_one_cube_one_target_resting_on_the_table():
    sc = S.load("aloha2-cube-transfer-shared")
    lay = W.layout(SHARED)
    assert sc["frame"]["layout"] == SHARED and lay["scenario"] == sc["id"]
    assert len(sc["objects"]) == 1 and len(sc["targets"]) == 1
    half = sc["objects"][0]["size_m"][2] / 2
    a, b = sc["objects"][0]["start_m"], sc["targets"][0]["center_m"]
    assert a[2] == pytest.approx(lay["table"]["top_z"] + half)  # resting, not floating or sunk
    assert b[2] == pytest.approx(lay["table"]["top_z"])          # target pad on the table surface
    cx, cy = lay["table"]["center_xy"]
    sx, sy = lay["table"]["size_xy"]
    for p in (a, b):
        assert abs(p[0] - cx) < sx / 2 - half and abs(p[1] - cy) < sy / 2 - half
    assert sc["labels"][0]["position_m"][:2] == a[:2]


def test_layout_audit_reaches_task_points_but_never_opens_unverified_gates():
    report = W.audit_layout(SHARED)
    assert report["status"] == "EXPERIMENTAL_DISPLAY_LAYOUT_POSITION_IK_ONLY"
    assert report["cube_centre_on_table"]
    for point in report["task_points"].values():
        for role in W.ROLES:
            ik = point[role]["gripper_down_ik"]
            assert ik["reachable"] and ik["position_error_m"] <= 0.005 and ik["gripper_down_error_deg"] <= 5
            assert ik["collision_checked"] is False and ik["grasp_orientation_checked"] is False
    g = report["engineering_gates"]
    for closed in ("grasp_orientation_about_vertical", "robot_table_collision", "leader_follower_collision",
                   "physical_contact_3d", "hardware_registration", "enable_ab_shortcuts", "grasp_automation",
                   "hardware_motion"):
        assert g[closed] is False, closed
    assert "position IK only; orientation/collision/physical contact unverified" in report["statement"]


def test_legacy_scenario_never_accepts_a_leader_point():
    legacy = S.load("aloha2-cube-transfer")
    with pytest.raises(ValueError):
        B.signals([LEADER_HOME_OPEN], legacy, "leader")
    ee, _ = B.signals([LEADER_HOME_OPEN], legacy)  # follower base frame, unchanged behaviour
    assert ee.shape == (1, 3)


def test_shared_scenario_signals_are_in_the_display_world():
    sc = S.load("aloha2-cube-transfer-shared")
    lay = W.layout(SHARED)
    ee_leader, op = B.signals([LEADER_HOME_OPEN], sc, "leader")
    from kkh.studio import robotics as R
    fk = R.robot_for("aloha_wx250s").forward_kinematics(dict(zip(R.JOINTS, LEADER_HOME_OPEN)))["ee_gripper_link"][:3, 3]
    assert ee_leader[0] == pytest.approx(W.to_world(lay, W.LocalPoint("leader", tuple(fk))))
    assert op[0] == pytest.approx(1.0)
    ee_follower, _ = B.signals([LEADER_HOME_OPEN], sc, "follower")
    assert ee_follower[0][0] > 0 > ee_leader[0][0]  # each arm's home pose is on its own side of the table


def _demonstration(sc):
    """Leader joint path on the shared table: open -> above A -> down -> close -> up -> above B -> down -> open."""
    lay = W.layout(SHARED)
    half = sc["objects"][0]["size_m"][2] / 2
    a, b = sc["objects"][0]["start_m"], sc["targets"][0]["center_m"]

    def q_at(p, grip):
        ik = W.ik_check("aloha_wx250s", W.to_local(lay, "leader", p).xyz, gripper_down=True)
        assert ik["reachable"], ik
        return [*ik["q"], 0.0, grip]

    closed = 0.015
    waypoints = [LEADER_HOME_OPEN,
                 q_at([a[0], a[1], half + 0.08], 0.037), q_at([a[0], a[1], half + 0.02], 0.037),
                 q_at([a[0], a[1], half + 0.02], closed), q_at([a[0], a[1], half + 0.10], closed),
                 q_at([b[0], b[1], half + 0.10], closed), q_at([b[0], b[1], half + 0.02], closed),
                 q_at([b[0], b[1], half + 0.02], 0.037)]
    rows = []
    for p, n in zip(waypoints, waypoints[1:]):
        for s in np.linspace(0, 1, 20, endpoint=False):
            rows.append((np.array(p) + s * (np.array(n) - np.array(p))).tolist())
    rows.append(waypoints[-1])
    return [0.02 * k for k in range(len(rows))], rows


def test_demonstration_succeeds_and_joint_replay_attempt_is_reported_honestly():
    sc = S.load("aloha2-cube-transfer-shared")
    time, rows = _demonstration(sc)
    trajectory = {"scenario": {"id": sc["id"], "version": sc["version"], "sha256": sc["sha256"]},
                  "time": time, "q": rows}
    demo = S.evaluate_recording(trajectory)
    assert demo["evaluated_on"]["role"] == "leader" and demo["metrics"]["task_completed"]
    attempt = S.evaluate_recording(trajectory, manipulator="follower")
    assert attempt["evaluated_on"]["role"] == "follower" and "no retargeting" in attempt["evaluated_on"]["label"]
    # Joint-space replay on facing mounts does not reach A: no grasp, no completed task claimed.
    assert not attempt["metrics"]["task_completed"]
    assert any("not physical" in x for x in demo["limitations"])


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_typescript_frame_module_passes_its_unit_tests():
    from kkh.engineering.workspace_frames import ROOT
    out = subprocess.run(["node", "--test", "web/src/workspaceFrames.test.ts"], cwd=ROOT, capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr


def test_api_serves_layouts_with_closed_gates_and_validates_manipulator(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from kkh.api.main import app
    import kkh.studio.api as api
    import kkh.semantic.trace as trace
    from kkh.studio.storage import Store
    monkeypatch.setattr(trace, "_write", lambda g: {"graphdb": "captured"})  # no GraphDB writes from tests
    monkeypatch.setattr(api, "store", Store(tmp_path / "api.sqlite"))
    client = TestClient(app)
    data = client.get("/api/workbench/workspace/layouts").json()
    assert set(data["layouts"]) == {"legacy_side_by_side", SHARED}
    assert data["calibration"]["hardware_registration"] is False
    assert data["gates"]["enable_ab_shortcuts"] is False and data["gates"]["hardware_registration"] is False
    sc = S.load("aloha2-cube-transfer-shared")
    time, rows = _demonstration(sc)
    config = client.get("/api/workbench/configuration").json()
    saved = client.post("/api/workbench/documents/trajectory", json={"name": "shared demo", "data": {
        "configuration_id": config["configuration_id"], "joint_ids": config["joint_ids"], "time": time, "q": rows,
        "provenance": "test", "scenario": {"id": sc["id"], "version": sc["version"]}}}).json()
    demo = client.get(f"/api/workbench/trajectory/{saved['id']}/task").json()
    attempt = client.get(f"/api/workbench/trajectory/{saved['id']}/task?manipulator=follower").json()
    assert demo["metrics"]["task_completed"] and not attempt["metrics"]["task_completed"]
    assert client.get(f"/api/workbench/trajectory/{saved['id']}/task?manipulator=camera").status_code == 422
