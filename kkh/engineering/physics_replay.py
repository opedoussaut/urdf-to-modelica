"""Read-only, explicitly labeled Modelica surrogate replay for HT GEN7 PhysAI Studio.

This is *not* a physics backend for live ALOHA interaction. Results originate in an
OpenModelica CSV, and remain separate from the Level-1 visual task evaluator.
"""
from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

from kkh.engineering.grasp_experiment import validate_result

ROOT = Path(__file__).resolve().parents[2]
CSV_FILE = ROOT / 'runs' / 'grasp-experiment' / 'GEN7Contact.TwoFingerGrasp_res.csv'
MODEL_FILE = ROOT / 'engineering' / 'modelica' / 'GEN7Contact' / 'TwoFingerGrasp.mo'


def replay(csv_file: Path = CSV_FILE, model_file: Path = MODEL_FILE, max_samples: int = 250) -> dict:
    """Return a validated and bounded physics replay without running or editing anything."""
    if not 2 <= max_samples <= 2000:
        raise ValueError('max_samples must be between 2 and 2000')
    if not csv_file.is_file():
        raise FileNotFoundError(f'No Modelica grasp result at {csv_file}; run the experiment first')
    if not model_file.is_file():
        raise FileNotFoundError(f'Modelica source missing at {model_file}')
    metrics = validate_result(csv_file)
    with csv_file.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        required = ('time', 'z', 'x', 'gripGap', 'fingerZ', 'leftNormal',
                    'rightNormal', 'tableNormal', 'leftFriction', 'rightFriction')
        selected = {}
        for name in required:
            matches = [field for field in columns if field == name or field.endswith('.' + name)]
            if len(matches) != 1:
                raise ValueError(f'Expected unique OpenModelica output {name}, got {matches}')
            selected[name] = matches[0]
        samples = []
        for line in reader:
            point = {name: float(line[column]) for name, column in selected.items()}
            if not all(math.isfinite(value) for value in point.values()):
                raise ValueError('Nonfinite OpenModelica replay value')
            samples.append(point)
    if not samples:
        raise ValueError('Empty OpenModelica result')
    # Deterministic, include endpoints, never imply 250 Hz or real-time stepping.
    count = min(max_samples, len(samples))
    indices = [round(i * (len(samples) - 1) / (count - 1)) for i in range(count)]
    return {
        'model': 'GEN7Contact.TwoFingerGrasp',
        'role': 'offline_reduced_order_physics_evidence',
        'authoritative_for': 'this isolated surrogate experiment only',
        'not_authoritative_for': ['live ALOHA gripper', 'leader recording', 'follower task success', 'real robot'],
        'frame': 'surrogate: horizontal x and cube-centre z above a plane; NOT ALOHA scene coordinates',
        'physics_claim': 'unvalidated two-dimensional prescribed-finger model; no actual ALOHA contact',
        'source_csv_sha256': hashlib.sha256(csv_file.read_bytes()).hexdigest(),
        'modelica_source_sha256': hashlib.sha256(model_file.read_bytes()).hexdigest(),
        'metrics': metrics,
        'total_samples': len(samples),
        'samples': [samples[i] for i in indices],
    }
