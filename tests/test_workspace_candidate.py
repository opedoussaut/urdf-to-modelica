import pytest
from kkh.engineering.workspace_candidate import evaluate_candidate, candidates


def fake_reach(model, point):
    # Contrived deterministic domain for exercising the registration transform.
    err = 0.0 if 0 <= point[0] <= 1.0 else 0.2
    return {'reachable_position_only': err == 0.0, 'best_position_error_m': err}


def test_task_points_are_transformed_for_both_arms():
    result = evaluate_candidate([0.4, 0, .02], [.4, .1, .02],
                                {'leader': 0.0, 'follower': 0.2}, fake_reach)
    assert result['position_ik_feasible']
    assert result['task_points']['cube_A']['arms']['leader']['local_m'] == [0.4, 0., .02]
    assert result['task_points']['cube_A']['arms']['follower']['local_m'][0] == pytest.approx(.2)


def test_rejects_nonfinite_or_missing_registration():
    with pytest.raises(ValueError):
        evaluate_candidate([float('nan'), 0, 0], [0, 0, 0], {'leader': 0, 'follower': 0}, fake_reach)
    with pytest.raises(ValueError):
        evaluate_candidate([0, 0, 0], [0, 0, 0], {'leader': 0}, fake_reach)


def test_no_candidate_can_be_applied_without_other_gates():
    scenario = {'objects': [{'size_m': [.04, .04, .04]}]}
    result = candidates(scenario, {'leader': -0.5, 'follower': .45}, reach=fake_reach)
    assert result['candidates_evaluated'] == 12
    assert not result['engineering_gates']['safe_to_apply_to_live_scene']
    assert result['status'] == 'NO_COMMON_POSITION_IK_CANDIDATE'
