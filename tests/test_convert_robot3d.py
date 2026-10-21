"""3D robot description (meshes resolved inside the repository only), preview meshes, live check states."""
import pytest

from kkh.convert import robot3d, score, sources


@pytest.mark.parametrize("source", list(sources.PINNED))
def test_pinned_robots_resolve_every_mesh(source):
    urdf, _ = sources.resolve(source)
    if not urdf.exists():
        pytest.skip("pinned source not fetched (tools/fetch_sources.py)")
    d, meshes = robot3d.describe(source)
    visuals = [v for link in d["links"].values() for v in link["visuals"]]
    assert visuals and all(v["mesh"] is not None or v["shape"] for v in visuals)  # a mesh file or a URDF primitive
    root = sources.ROOT.resolve()
    assert all(root in p.parents for p in meshes)
    assert len(d["joints"]) == len(d["links"]) - 1


def test_mesh_paths_never_leave_the_repository(tmp_path):
    urdf = sources.ROOT / "data" / "urdf" / "aloha_wx250s.urdf"
    assert robot3d.resolve_mesh(urdf, "file:///etc/passwd") is None
    assert robot3d.resolve_mesh(urdf, "../../../../../../Windows/win.ini") is None
    assert robot3d.resolve_mesh(urdf, None) is None


def test_preview_mesh_is_smaller_valid_stl():
    urdf, _ = sources.resolve("aloha_wx250s")
    _, meshes = robot3d.describe("aloha_wx250s")
    big = max(meshes, key=lambda p: p.stat().st_size)
    low = robot3d.simplified(big)
    data = low.read_bytes()
    n = int.from_bytes(data[80:84], "little")
    assert 0 < n and len(data) == 84 + 50 * n
    assert low.stat().st_size <= big.stat().st_size


def test_live_checks_states():
    items = score.live_checks({"produced": True, "loads": True, "checks": False}, {"produced", "loads", "checks"})
    states = {c["id"]: c["state"] for c in items}
    assert states["loads"] == "pass" and states["checks"] == "fail"
    assert all(states[k] == "skipped" for k in ("simulates", "coverage", "kinematics", "parameters", "dynamics"))
    running = score.live_checks({"produced": True}, {"produced"}, "loads")
    assert [c["state"] for c in running][:3] == ["pass", "running", "pending"]


def test_llm_budget_grows_with_the_robot():
    from kkh.convert import llm
    from kkh.engineering.urdf_model import load_urdf
    small = load_urdf(sources.resolve("aloha_wx250s")[0])
    msgs = [{"role": "user", "content": "x" * 16000}]
    b = llm.budget(small, msgs)
    assert b["max_tokens"] == llm.SETTINGS["max_tokens"]  # the arms keep the campaign's output cap
    assert b["num_ctx"] >= b["prompt_tokens_est"] + 2 * b["max_tokens"] and b["num_ctx"] % 1024 == 0
    g1 = sources.resolve("unitree_g1")[0]
    if g1.exists():
        big = llm.budget(load_urdf(g1), msgs)
        assert big["max_tokens"] > b["max_tokens"] and big["num_ctx"] > b["num_ctx"]
