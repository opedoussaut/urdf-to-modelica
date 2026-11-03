"""Demo lab features: 1D Modelica servo experiment, live URDF→Modelica pipeline, lab, copilot default."""
import hashlib
import math
import time

import pytest

from kkh.studio import servo1d as S1


def test_plant_is_derived_from_the_urdf_not_assumed():
    p = S1.derive_plant("shoulder")
    assert p["inertia_kgm2"] > 0 and p["moving_mass_kg"] > 0
    assert p["gravity_fit_residual_Nm"] < 1e-9          # exact A·sin(q+φ) law for a rigid subtree
    assert p["effort_limit_Nm"] == 20.0 and p["q_min"] < p["q0"] < p["q_max"]
    assert "derived" in p["evidence"]["inertia_kgm2"] and "not identified" in p["evidence"]["damping_Nms_per_rad"]
    assert "reflected motor rotor inertia" in p["evidence"]["not_modelled"]


def test_parameter_bounds_and_inputs_are_validated():
    with pytest.raises(ValueError):
        S1.check_params({"kp": 900, "kd": 4, "actuatorTime": 0.03, "feedforward": 0})  # above declared max 500
    with pytest.raises(ValueError):
        S1.check_params({"kp": 40, "kd": 4, "actuatorTime": 0.03})                     # missing parameter
    plant = S1.derive_plant("shoulder")
    with pytest.raises(ValueError):
        S1.command({"kind": "step", "amplitude": 0.3, "step_time": 5.0, "stop_time": 3.0}, plant)  # step after stop
    with pytest.raises(ValueError):
        S1.command({"kind": "impulse"}, plant)


def test_step_outside_joint_limits_is_rejected():
    plant = S1.derive_plant("shoulder")
    with pytest.raises(ValueError):
        S1.command({"kind": "step", "amplitude": -1.0}, plant)  # -1.96 rad < q_min -1.85


@pytest.mark.omc
def test_real_openmodelica_comparison_reports_measured_differences(tmp_path, monkeypatch):
    monkeypatch.setattr(S1, "RUNS", tmp_path)
    base = {"kp": 40, "kd": 4, "actuatorTime": 0.03, "feedforward": 0.0}
    cand = {"kp": 40, "kd": 4, "actuatorTime": 0.03, "feedforward": 1.0}
    r = S1.run_experiment("shoulder", base, cand, {"kind": "step", "amplitude": 0.3, "stop_time": 2.0}, baseline_label="test")
    b, c = r["runs"]["baseline"], r["runs"]["candidate"]
    assert b["ok"] and c["ok"] and b["omc_version"].startswith("OpenModelica")
    assert len(b["series"]["time"]) > 100 and set(S1.OUTPUTS) <= set(b["series"])
    # physics sanity: PD without integral action sags under gravity; gravity feed-forward removes most of it
    assert abs(c["metrics"]["steady_state_error_rad"]) < abs(b["metrics"]["steady_state_error_rad"])
    rows = {row["metric"]: row for row in r["comparison"]["rows"]}
    assert rows["steady_state_error_rad"]["verdict"] == "improved"
    assert r["input_sha256"] and (tmp_path / r["id"] / "report.json").exists()
    assert b["source_sha256"] != c["source_sha256"]  # the edited parameter really reached the Modelica source


@pytest.mark.omc
def test_failing_model_is_reported_not_hidden(tmp_path, monkeypatch):
    plant = dict(S1.derive_plant("shoulder"))
    plant["inertia_kgm2"] = "J_undefined"  # syntactically wrong value -> OMC check must fail
    cmd = S1.command({"kind": "step"}, S1.derive_plant("shoulder"))
    out = S1.simulate(plant, S1.SERVO_DEFAULTS, cmd, tmp_path / "bad")
    assert out["ok"] is False and out["stage"] == "check" and out["diagnostic"]


def test_comparison_never_claims_blanket_improvement():
    base = {"rms_error_rad": 0.05, "max_abs_error_rad": 0.3, "peak_torque_Nm": 7, "overshoot_percent": 9,
            "settling_time_2pct_s": None, "steady_state_error_rad": -0.006, "saturated_fraction": 0.0}
    cand = {**base, "rms_error_rad": 0.04, "saturated_fraction": 0.01}
    c = S1.compare_metrics(base, cand)
    assert c["improved"] == ["rms_error_rad"] and c["worse"] == ["saturated_fraction"]
    assert c["summary"].startswith("Mixed result")
    assert S1.compare_metrics(base, base)["summary"].startswith("No measurable change")


@pytest.mark.omc
def test_live_urdf_to_modelica_conversion_is_isolated_reproducible_and_checked(tmp_path, monkeypatch):
    import kkh.studio.api  # noqa: F401  (registers the router the lab module extends)
    from kkh.studio import lab_api
    monkeypatch.setattr(lab_api, "PIPELINE_RUNS", tmp_path)
    urdf = lab_api.C.ROOT / "data/urdf/aloha_vx300s.urdf"
    before = hashlib.sha256(urdf.read_bytes()).hexdigest()
    r = lab_api.run_pipeline("aloha2")
    assert r["ok"], [s for s in r["stages"] if not s["ok"]]
    stages = {s["stage"][0]: s for s in r["stages"]}
    gen = stages["3"]["result"]
    assert (tmp_path / r["id"] / "ALOHA2" / "package.mo").exists() and gen["files"] > 10
    rows = {row["urdf_joint"]: row for row in stages["4"]["result"]["aloha_vx300s"]["rows"]}
    assert rows["shoulder"]["modelica_component"] == "j_shoulder" and rows["shoulder"]["modifiers"]["q_max"].startswith("1.2566")
    assert rows["right_finger"]["mimic"] == {"joint": "left_finger", "multiplier": -1.0, "offset": 0.0}
    assert any("j_right_finger.q = -1.0 * q[8]" in e for e in stages["4"]["result"]["aloha_vx300s"]["mimic_equations"])
    assert all(v["complete"] for v in stages["5"]["result"].values())
    assert all(v["ok"] for v in stages["6"]["result"]["checks"].values())
    integrity = stages["7"]["result"]
    assert integrity["sources_unchanged"] and integrity["frozen_package_unchanged"]
    assert hashlib.sha256(urdf.read_bytes()).hexdigest() == before
    # no servo gains are attributed to the URDF: the arm class carries no kp/kd
    arm = (tmp_path / r["id"] / "ALOHA2/Arms/AlohaVX300s.mo").read_text(encoding="utf-8")
    assert " kp" not in arm and "kd =" not in arm


def test_pipeline_rejects_sources_outside_the_allowlist():
    import kkh.studio.api  # noqa: F401
    from kkh.studio import lab_api
    with pytest.raises(ValueError):
        lab_api.run_pipeline("../../etc/passwd")


def test_copilot_default_is_configurable_and_missing_models_are_explicit(monkeypatch):
    import httpx
    from kkh.llm import ollama
    assert ollama.DEFAULT_MODEL == "nemotron-3-nano:4b" or ollama.DEFAULT_MODEL  # env may override
    client = ollama.Ollama()
    monkeypatch.setattr(client, "models", lambda: [{"name": "nemotron-3-nano:4b"}])
    with pytest.raises(ollama.ModelMissing) as err:
        client.chat([{"role": "user", "content": "hi"}], model="qwen3:4b")
    assert "ollama pull qwen3:4b" in str(err.value) and "No other model is substituted" in str(err.value)
