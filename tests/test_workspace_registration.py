import pytest
from kkh.engineering.workspace_registration import audit, offsets, transform_point


def test_render_offsets_are_read_from_source():
    assert offsets('const FOLLOWER_OFFSET = 0.45, LEADER_OFFSET = -0.5;') == {'follower': .45, 'leader': -.5}
    with pytest.raises(ValueError):
        offsets('const LEADER_OFFSET = 0;')


def test_transform_roundtrip_and_validation():
    p = [.3, .12, .02]
    q = transform_point(p, .45, -.5)
    assert q == pytest.approx([1.25, .12, .02])
    assert transform_point(q, -.5, .45) == pytest.approx(p)
    with pytest.raises(ValueError):
        transform_point([float('nan'), 0, 0], 0, 0)


def test_actual_scenario_never_authorizes_uncalibrated_motion():
    result = audit()
    assert result['task_points']['cube_A']['leader_local_display_only_m'] == pytest.approx([1.25, .12, .02])
    assert result['engineering_gates']['enable_ab_shortcuts'] is False
    assert result['engineering_gates']['hardware_base_registration'] is False
    assert result['status'] == 'BLOCKED_UNREACHABLE_TASK_POINT'
