"""Bounded proposal/validation loop; candidates never modify the accepted model."""
from __future__ import annotations

import json


def repair(messages, propose, decode, evaluate, max_attempts=2):
    if not 1 <= max_attempts <= 3:
        raise ValueError("Repair budget must be 1–3 attempts")
    history = list(messages)
    attempts = []
    for index in range(max_attempts):
        attempt = {"attempt": index + 1, "prompt": list(history)}
        try:
            response = propose(history)
            attempt["response"] = response
            value = decode(response["content"])
            attempt["proposal"] = value
            attempt.update(evaluate(value, index))
        except Exception as exc:
            attempt.update(error=str(exc), engineering_valid=False)
        attempts.append(attempt)
        if attempt["engineering_valid"]:
            break
        validation = attempt.get("validation", {})
        feedback = {"source_parameter_match": attempt.get("parameter_correct", False),
                    "check_ok": attempt.get("check_ok", False), "simulate_ok": attempt.get("simulate_ok", False),
                    "forward_kinematics": validation.get("forward_kinematics"),
                    "mimic_max_error": validation.get("mimic_max_error"),
                    "limit_violations": validation.get("limit_violations"), "error": attempt.get("error")}
        history += [{"role": "assistant", "content": attempt.get("response", {}).get("content", "{}")},
                    {"role": "user", "content": "The proposal failed independent validation. Re-read the original source and correct the requested parameter. Return the same JSON schema. Diagnostics (no target answer): " + json.dumps(feedback)}]
    return attempts
