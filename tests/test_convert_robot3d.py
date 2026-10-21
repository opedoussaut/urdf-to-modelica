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
    assert visuals and all(v["mesh"] is not None for v in visuals)
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
