"""Physics evidence bridge must be scientifically labeled and never fake missing runs."""
import csv
from pathlib import Path
import pytest
from kkh.engineering.physics_replay import replay


def test_missing_result_is_not_fabricated(tmp_path):
    with pytest.raises(FileNotFoundError, match='run the experiment'):
        replay(tmp_path/'nonexistent.csv', tmp_path/'model.mo')


def test_sample_limit(tmp_path):
    with pytest.raises(ValueError, match='max_samples'):
        replay(tmp_path/'x.csv', max_samples=1)


def test_real_runner_contract_fields():
    from kkh.engineering.grasp_experiment import validate_result
    assert callable(validate_result)
