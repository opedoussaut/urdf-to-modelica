"""Generic engineering services: URDF FK conventions, generator, OMC round-trip on a synthetic robot."""
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from kkh.engineering import modelica_gen as mg
from kkh.engineering.modelica_inspect import completeness, parse_class
from kkh.engineering.urdf_model import axis_angle, load_urdf, rpy_to_matrix

FIX = Path(__file__).parent / "fixtures"


def test_rpy_matches_urdf_extrinsic_xyz():
    rpy = (0.3, -0.2, 0.7)
    ref = Rotation.from_euler("xyz", rpy).as_matrix()  # extrinsic x-y-z == URDF roll-pitch-yaw
    assert np.allclose(rpy_to_matrix(rpy), ref, atol=1e-14)


def test_axis_angle_is_rotation():
    R = axis_angle([1, 2, 3], 0.8)
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-14)
    assert np.allclose(Rotation.from_matrix(R).as_rotvec(), 0.8 * np.array([1, 2, 3]) / np.sqrt(14), atol=1e-12)


def test_structure_and_mimic():
    r = load_urdf(FIX / "rpy_chain.urdf")
    rep = r.validate_structure()
    assert rep["ok"], rep["errors"]
    assert [j.name for j in r.actuated_joints()] == ["j1", "j2", "slide"]
    poses = r.forward_kinematics({"j2": 0.4})
    p_twin = r.forward_kinematics({"j2": 0.4, "twin": -0.5 * 0.4 + 0.1})["l4"]
    assert np.allclose(poses["l4"], p_twin)


def test_generated_class_is_structurally_complete(tmp_path):
    r = load_urdf(FIX / "rpy_chain.urdf")
    text, cm = mg.robot_class(r, "T", "Chain", "T", "test", lambda m: m)
    f = tmp_path / "Chain.mo"
    f.write_text(text)
    rep = completeness(r, f)
    assert rep["complete"], rep["issues"]
    assert cm.placeholders == ["tool"]
    assert cm.mimic == {"twin": ("j2", -0.5, 0.1)}
    assert len(parse_class(f)["connections"]) == 1 + 2 * len(r.joints) + 3 * 3


def _write_pkg(root: Path, robot) -> None:
    files = mg.component_library("T")
    text, _ = mg.robot_class(robot, "T", "Chain", "T", "test", lambda m: m)
    files["Chain.mo"] = text
    t, Q = [0.0, 1.0, 2.0], [[0.0, 0.0, 0.0], [1.2, -0.8, 0.08], [-0.5, 0.6, 0.02]]
    rows = "; ".join(", ".join(mg.fmt(x) for x in q) for q in Q)
    files["Run.mo"] = f'''within T;
model Run
  inner Modelica.Mechanics.MultiBody.World world(n = {{0, 0, -1}});
  T.Chain chain(animation = false);
  T.Blocks.WaypointTrajectory traj(n = 3, nWp = 3, t_wp = {mg.vec(t)}, Q = [{rows}]);
equation
  connect(world.frame_b, chain.frame_a);
  connect(traj.q, chain.q); connect(traj.qd, chain.qd); connect(traj.qdd, chain.qdd);
end Run;
'''
    files["package.mo"] = 'package T\n  annotation (uses(Modelica(version = "4.1.0")));\nend T;\n'
    files["package.order"] = "Components\nBlocks\nChain\nRun\n"
    for rel, txt in files.items():
        p = root / "T" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)


@pytest.mark.omc
def test_omc_roundtrip_matches_reference_fk(tmp_path):
    from kkh.engineering.omc import MatResult, OMCService
    from kkh.engineering.validation import compare_frames

    r = load_urdf(FIX / "rpy_chain.urdf")
    _write_pkg(tmp_path, r)
    omc = OMCService(tmp_path / "work")
    try:
        assert omc.load_package(tmp_path / "T" / "package.mo").ok
        chk = omc.check("T.Run")
        assert chk.ok, chk.messages
        sim = omc.simulate("T.Run", stop_time=2.0, intervals=100)
        assert sim.ok, sim.messages
        res = MatResult(sim.data["resultFile"])
    finally:
        omc.close()
    links = [{"urdf": l, "r_vars": [f"chain.{l}.frame_a.r_0[{i}]" for i in (1, 2, 3)],
              "R_vars": [f"chain.{l}.frame_a.R.T[{i},{j}]" for i in (1, 2, 3) for j in (1, 2, 3)]} for l in r.links]
    joints = [{"urdf": "j1", "var": "chain.j_j1.phi"}, {"urdf": "j2", "var": "chain.j_j2.phi"},
              {"urdf": "slide", "var": "chain.j_slide.s"}]
    rep = compare_frames(res, r, links, joints, n_samples=21)
    assert rep["pass"], rep
    # Mimic joint follows the master with multiplier/offset
    assert np.allclose(res.get("chain.j_twin.phi"), -0.5 * res.get("chain.j_j2.phi") + 0.1, atol=1e-12)
