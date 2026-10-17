"""Task scenarios: Level-1 visual grasp rule, ALOHA binding (follower IK), API linkage and semantic trace."""
import numpy as np
import pytest

from kkh import scenarios as S
from kkh.domain.aloha import scenario_binding as B
from kkh.studio.storage import Store

HOME = [0.0, -0.96, 1.16, 0.0, -0.3, 0.0, 0.0, 0.037]  # leader home with the gripper fully open
CLOSED = 0.015


def _ik(q, target):
    r = B.follower_ik(q, target)
    assert r["success"], r["message"]
    return r["q"]


def scripted_transfer(scenario, release_in_target=True):
    """Leader joint path: open -> above A -> down -> close -> lift -> above B -> down -> open (joint-space ramps)."""
    a, half = scenario["objects"][0]["start_m"], scenario["objects"][0]["size_m"][2] / 2
    b = scenario["targets"][0]["center_m"] if release_in_target else [a[0], a[1] + 0.06]
    waypoints = [list(HOME)]
    q = _ik(HOME, [a[0], a[1], half + 0.08]); waypoints.append(q)
    q = _ik(q, [a[0], a[1], half + 0.02]); waypoints.append(q)
    q = list(q); q[7] = CLOSED; waypoints.append(q)
    q = _ik(q, [a[0], a[1], half + 0.10]); waypoints.append(q)
    q = _ik(q, [b[0], b[1], half + 0.10]); waypoints.append(q)
    q = _ik(q, [b[0], b[1], half + 0.02]); waypoints.append(q)
    q = list(q); q[7] = HOME[7]; waypoints.append(q)
    rows = []
    for p, n in zip(waypoints, waypoints[1:]):
        for s in np.linspace(0, 1, 25, endpoint=False):
            rows.append((np.array(p) + s * (np.array(n) - np.array(p))).tolist())
    rows.append(waypoints[-1])
    return [0.02 * k for k in range(len(rows))], rows


def test_scenario_definition_is_versioned_and_hashed():
    sc = S.load("aloha2-cube-transfer")
    assert sc["version"] == "1.0.0" and len(sc["sha256"]) == 64
    assert sc["physics"]["level"] == 1 and sc["visual_grasp"]["capture_radius_m"] > 0
    assert any(x["id"] == "aloha2-cube-transfer" for x in S.available())
    with pytest.raises(Exception):
        S.load("../secrets")


def test_visual_grasp_rule_events_and_metrics():
    sc = S.load("aloha2-cube-transfer")
    a, b = np.array(sc["objects"][0]["start_m"]), np.array(sc["targets"][0]["center_m"])
    half = sc["objects"][0]["size_m"][2] / 2
    # synthetic signals: approach A open, close at A, carry to B, open
    ee = [a + [0, 0, 0.1], a + [0, 0, 0.02], a + [0, 0, 0.02], a + [0, 0, 0.1], np.r_[b[:2], 0.1], np.r_[b[:2], 0.03], np.r_[b[:2], 0.03]]
    opening = [1, 1, 0, 0, 0, 0, 1]
    r = S.evaluate(sc, list(range(7)), np.array(ee), np.array(opening))
    m = r["metrics"]
    assert m["grasped"] and m["released"] and m["grasp_before_release"] and m["cube_in_target"] and m["task_completed"]
    assert [e["event"] for e in r["events"]] == ["grasp", "release"]
    assert r["cube_path"][3][3] == 1 and r["cube_path"][-1][2] == pytest.approx(half)  # carried, then dropped
    assert any("not physical" in x for x in r["limitations"])
    # closing far from the cube is a missed grasp; the cube never moves
    far = [a + [0.2, 0, 0.1]] * 3
    r = S.evaluate(sc, [0, 1, 2], np.array(far), np.array([1, 0, 1]))
    assert r["metrics"]["missed_grasps"] == 1 and not r["metrics"]["grasped"] and not r["metrics"]["task_completed"]
    assert r["metrics"]["cube_final_m"] == pytest.approx(list(a), abs=1e-4)
    # hysteresis: an opening between the thresholds neither closes nor opens
    r = S.evaluate(sc, [0, 1], np.array([a, a]), np.array([1, 0.45]))
    assert all(e["event"] != "grasp" for e in r["events"])  # penetration is now reported


def test_follower_ik_reaches_scenario_and_rejects_unreachable():
    sc = S.load("aloha2-cube-transfer")
    a = sc["objects"][0]["start_m"]
    r = B.follower_ik(HOME, [a[0], a[1], 0.10])
    assert r["success"] and r["error_m"] < 0.005 and r["q"][7] == HOME[7]
    ee, op = B.signals([r["q"]])
    assert np.linalg.norm(ee[0] - [a[0], a[1], 0.10]) < 0.005 and op[0] == pytest.approx(1.0)
    far = B.follower_ik(HOME, [2.0, 0.0, 0.1])
    assert not far["success"] and far["q"] == HOME


def test_scripted_transfer_completes_and_misplaced_release_does_not():
    sc = S.load("aloha2-cube-transfer")
    for in_target in (True, False):
        time, rows = scripted_transfer(sc, in_target)
        ee, op = B.signals(rows)
        m = S.evaluate(sc, time, ee, op)["metrics"]
        assert m["grasped"] and m["released"]
        assert m["task_completed"] is in_target and m["cube_in_target"] is in_target


def test_api_links_recording_to_scenario_task_and_trace(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from kkh.api.main import app
    import kkh.studio.api as api
    import kkh.semantic.trace as trace

    written = []
    monkeypatch.setattr(trace, "_write", lambda g: written.append(g) or {"graphdb": "captured"})  # no GraphDB writes
    monkeypatch.setattr(api, "store", Store(tmp_path / "api.sqlite"))
    client = TestClient(app)
    sc = client.get("/api/workbench/scenarios/aloha2-cube-transfer").json()
    time, rows = scripted_transfer(sc)
    config = client.get("/api/workbench/configuration").json()
    data = {"configuration_id": config["configuration_id"], "joint_ids": config["joint_ids"], "time": time, "q": rows,
            "provenance": "test", "scenario": {"id": sc["id"], "version": sc["version"]},
            "traceability": {"model_revision": "rev-under-test", "gripper_commands": [{"t": 1.0, "command": "close"}]}}
    bad = client.post("/api/workbench/documents/trajectory", json={"name": "x", "data": {**data, "scenario": {"id": sc["id"], "version": "0.0.1"}}})
    assert bad.status_code == 422
    saved = client.post("/api/workbench/documents/trajectory", json={"name": "Scripted cube transfer", "data": data}).json()
    assert saved["data"]["scenario"]["sha256"] == sc["sha256"]
    task = client.get(f"/api/workbench/trajectory/{saved['id']}/task").json()
    assert task["metrics"]["task_completed"] and not task["scenario_changed_since_recording"]
    assert len(task["cube_path"]) == len(rows)
    # the observation reaches the semantic trace with its scenario and the model revision it was recorded against
    from rdflib import RDF
    obs = [g for g in written if (None, RDF.type, trace.K.Observation) in g]
    assert obs and (None, trace.K.forScenario, trace.E[f"scenario/{sc['id']}/{sc['version']}"]) in obs[-1]
    assert (None, trace.PROV.wasInfluencedBy, trace.revision_node("rev-under-test")) in obs[-1]
    # Cartesian follower control endpoint
    ik = client.post("/api/workbench/follower-ik", json={"q": HOME, "target": [0.3, -0.14, 0.1]}).json()
    assert ik["success"]
    plain = client.post("/api/workbench/documents/trajectory", json={"name": "plain", "data": {k: v for k, v in data.items() if k != "scenario"}}).json()
    assert client.get(f"/api/workbench/trajectory/{plain['id']}/task").status_code == 404


@pytest.mark.graphdb
def test_ontology_applicability_separates_tunable_assumptions_from_verified_facts():
    from kkh.semantic.graphdb import GraphDB
    from kkh.semantic.parameters import applicability
    db = GraphDB(timeout=8)
    try:
        kp = applicability(db, "ALOHA2.Control.FollowerServoSettings.shoulder", "kp")
        assert kp["applicable"] and kp["evidence_status"] == "Assumed", kp
        tau = applicability(db, "ALOHA2.Arms.AlohaVX300s.j_shoulder", "tau_max")
        assert not tau["applicable"]
    finally:
        db.close()


def test_simulated_signals_match_kinematic_signals_for_perfect_tracking():
    """A follower that tracks perfectly must give the same task signals as the kinematic replay."""
    from kkh.studio import robotics as R
    sc = S.load("aloha2-cube-transfer")
    time, rows = scripted_transfer(sc)
    follower = [R.mapping(r)["q"] for r in rows]
    ee_k, op_k = B.signals(rows)
    ee_s, op_s = B.simulated_signals(follower, time, time, rows)
    assert np.allclose(ee_k, ee_s, atol=1e-9) and np.allclose(op_k, op_s)
    assert S.evaluate(sc, time, ee_s, op_s)["metrics"]["task_completed"]


def test_task_evaluation_rejects_ambiguous_or_corrupt_data():
    sc = S.load("aloha2-cube-transfer")
    with pytest.raises(ValueError, match="timestamps"):
        S.evaluate(sc, [], np.empty((0, 3)), [])
    with pytest.raises(ValueError, match="timestamps"):
        S.evaluate(sc, [0, 0], np.zeros((2, 3)), [1, 1])
    with pytest.raises(ValueError, match="must match"):
        S.evaluate(sc, [0, 1], np.zeros((1, 3)), [1, 1])
    with pytest.raises(ValueError, match="finite"):
        S.evaluate(sc, [0], [[float("nan"), 0, 0]], [1])

    trajectory = {"scenario": {"id": sc["id"], "version": sc["version"]}, "time": [0, 1], "q": [[0] * 8] * 2}
    simulation = {"results": {"before": {}, "after": {}}}
    with pytest.raises(ValueError, match="explicitly"):
        S.evaluate_recording(trajectory, simulation)
    with pytest.raises(ValueError, match="does not exist"):
        S.evaluate_recording(trajectory, simulation, result="unknown")
    with pytest.raises(ValueError, match="no results"):
        S.evaluate_recording(trajectory, {"results": {}}, result="before")


def test_penetration_blocks_visual_grasp_and_success():
    sc = S.load("aloha2-cube-transfer")
    centre = np.asarray(sc["objects"][0]["start_m"], float)
    # Closing with the end-effector reference point *inside* the solid cube is invalid.
    r = S.evaluate(sc, [0, 1, 2], [centre, centre, centre], [1, 0, 1])
    assert r["metrics"]["invalid_penetration_samples"] == 3
    assert not r["metrics"]["grasped"]
    assert not r["metrics"]["task_completed"]
    assert "invalid_penetration" in [e["event"] for e in r["events"]]
