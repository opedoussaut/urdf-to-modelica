"""Level 2 (planned): physically simulated manipulation. NOT IMPLEMENTED.

The visual Level-1 logic in kkh.scenarios.evaluate must be replaceable by a physics backend without changing
scenario files or the UI contract (cube path + events + metrics). Candidate backends: Modelica contact libraries,
MuJoCo (the official ALOHA 2 MJCF exists), NVIDIA Isaac Sim. Payload effects would additionally feed the Modelica
follower model (cube mass on the gripper body), closing the loop to the engineering simulation.
"""
from __future__ import annotations

from typing import Protocol


class PhysicsBackend(Protocol):
    name: str

    def load_scene(self, scenario: dict, robot_configuration: str) -> None:
        """Create the robot, table, objects and targets with contact/friction properties."""

    def step(self, time: float, joint_positions: list[float]) -> dict:
        """Advance with the follower joint command; return object poses and contact states."""

    def result(self) -> dict:
        """Same contract as kkh.scenarios.evaluate: events, cube_path, metrics, limitations."""


IMPLEMENTED: list[str] = []  # no physics backend is implemented or claimed
