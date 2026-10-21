"""Modes 1 and 2 - local LLM (Ollama) writes the Modelica model from the URDF.

Mode 1 (llm): URDF text only. Mode 2 (llm_rag): the same prompt plus Modelica library classes retrieved by the
BM25 keyword index (kkh.convert.library_index). Everything else is identical: model, seed, temperature, context and
output budgets, repair budget. Repairs receive only real OpenModelica diagnostics, never a target model.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from kkh.engineering.urdf_model import load_urdf
from kkh.llm.ollama import DEFAULT_MODEL, Ollama

from .sources import prompt_text

SETTINGS = {"seed": 42, "temperature": 0, "num_ctx": 24576, "max_tokens": 10000, "repair_attempts": 2}

SYSTEM = """You are a Modelica engineer. Convert a robot described in URDF into ONE self-contained Modelica file that
OpenModelica 1.27 can load, check and simulate with the Modelica Standard Library 4.1.0 (Modelica.Mechanics.MultiBody).
Contract (follow exactly):
- One package named {pkg} containing a model named {pkg}Test (the model to simulate).
- {pkg}Test contains `inner Modelica.Mechanics.MultiBody.World world;` with gravity on.
- One component per URDF link, named exactly like the link with '/' and '-' replaced by '_' (e.g. base_link). Use a
  MultiBody body whose frame_a is the URDF link frame (mass, centre of mass and inertia from <inertial>).
- One joint component per URDF joint named j_<joint name> (same replacement), placed between parent and child link
  frames, with the URDF <origin> xyz/rpy applied before the joint and the joint axis n = the URDF <axis>.
- Revolute/continuous -> Modelica.Mechanics.MultiBody.Joints.Revolute, prismatic -> Prismatic, fixed -> a rigid
  connection (FixedTranslation / FixedRotation). Joints are NOT actuated (no flange connections): the robot falls under
  gravity. Use the URDF values only; do not invent parameters.
- Mimic joints: express the URDF mimic relation if you can, otherwise leave a comment.
Return only Modelica code, no prose, no markdown fences."""

REPAIR = """OpenModelica rejected the file. Fix it and return the complete corrected Modelica file only (no prose).
Diagnostics from OpenModelica (real output):
{diagnostics}"""

TRUNCATED = """Your reply was cut off at the output limit ({limit} tokens) before the file was complete. Write the complete
file again, more compactly: no comments, no annotations, one declaration per line, only what the contract requires."""


def package_name(robot_name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_]", "_", robot_name)
    return ("R_" + n) if not n[:1].isalpha() else n


def extract_code(text: str) -> str:
    text = text.split("</think>")[-1]
    fence = re.search(r"```(?:modelica)?\s*\n(.*?)```", text, re.S)
    return (fence.group(1) if fence else text).strip() + "\n"


def model_names(code: str, pkg: str) -> str | None:
    test = re.search(r"\bmodel\s+(\w*Test\w*)", code)
    top = re.search(r"\bpackage\s+(\w+)", code)
    if test:
        return f"{top.group(1)}.{test.group(1)}" if top else test.group(1)
    last = re.findall(r"\bmodel\s+(\w+)", code)
    if last:
        return f"{top.group(1)}.{last[-1]}" if top else last[-1]
    return None


def _library_context(robot) -> tuple[str, list[dict]]:
    from .library_index import retrieve_for
    hits = retrieve_for(robot)
    text = "\n\n".join(f"// {h['class']} (from {Path(h['file']).name})\n{h['text']}" for h in hits)
    return text, [{k: h[k] for k in ("class", "query", "score", "file")} for h in hits]


def convert(urdf: Path, out_dir: Path, rag: bool, score_fn, model: str | None = None, log=print,
            phase=lambda name, attempt, attempts: None, stream=None) -> dict:
    """Generate, then check with OpenModelica (via score_fn) and repair at most SETTINGS['repair_attempts'] times."""
    t0 = time.time()
    model = model or DEFAULT_MODEL
    robot = load_urdf(urdf)
    pkg = package_name(robot.name)
    system = SYSTEM.format(pkg=pkg)
    user = f"URDF of robot '{robot.name}' (visual/collision geometry removed):\n{prompt_text(urdf)}"
    retrieved = []
    if rag:
        context, retrieved = _library_context(robot)
        user += ("\n\nReference: Modelica library classes retrieved by keyword search (signatures; use their exact "
                 "names and parameters):\n" + context)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user + "\n/no_think"}]
    out = {"mode": "llm_rag" if rag else "llm", "llm_model": model, "settings": SETTINGS, "retrieved": retrieved,
           "prompt_sha256": hashlib.sha256(json.dumps(messages).encode()).hexdigest(),
           "prompt_chars": sum(len(m["content"]) for m in messages), "attempts": [], "llm_calls": 0,
           "human_interventions": 0}
    client = Ollama(timeout=900)
    best = None
    try:
        for attempt in range(1 + SETTINGS["repair_attempts"]):
            a = {"attempt": attempt + 1}
            t = time.time()
            phase("writing", attempt + 1, 1 + SETTINGS["repair_attempts"])
            try:
                resp = client.chat(messages, model=model, seed=SETTINGS["seed"], max_tokens=SETTINGS["max_tokens"],
                                   num_ctx=SETTINGS["num_ctx"], allow_truncated=True, on_token=stream)
            except Exception as exc:
                a.update(error=f"LLM call failed: {exc}"[:500], seconds=round(time.time() - t, 1))
                out["attempts"].append(a)
                break
            out["llm_calls"] += 1
            code = extract_code(resp["content"])
            d = out_dir / f"attempt{attempt + 1}"
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"{pkg}.mo"
            f.write_text(code, encoding="utf-8")
            target = model_names(code, pkg)
            a.update(file=f, model=target, llm_seconds=round(time.time() - t, 1), metrics=resp["metrics"],
                     code_chars=len(code), truncated=resp.get("truncated", False))
            log(f"  {out['mode']} attempt {attempt + 1}: {len(code)} chars{' (cut off)' if a['truncated'] else ''}, scoring")
            # a cut-off file is still scored as written: it is the method's real output
            phase("checking", attempt + 1, 1 + SETTINGS["repair_attempts"])
            s = score_fn(f if target else None, target, d)
            a["score"] = s
            out["attempts"].append(a)
            if best is None or s["rank_key"] >= best["score"]["rank_key"]:  # ties: the later (repaired) attempt is the method's answer
                best = a
            if s.get("simulates"):
                break
            if a["truncated"]:
                # restart from the original prompt (the cut-off file would not fit in the context with a rewrite)
                messages = [messages[0], {"role": "user", "content": user + "\n\n" + TRUNCATED.format(limit=SETTINGS["max_tokens"]) + "\n/no_think"}]
                continue
            diag = s.get("simulate_messages") or s.get("check_messages") or s.get("load_messages") or "No Modelica model found in the reply."
            messages += [{"role": "assistant", "content": code},
                         {"role": "user", "content": REPAIR.format(diagnostics=diag[-2500:]) + "\n/no_think"}]
    finally:
        client.close()
    out["repair_attempts"] = max(0, len(out["attempts"]) - 1)
    if best:
        out.update(main_file=best["file"], model=best["model"], best_attempt=best["attempt"], score=best["score"])
    out["seconds"] = round(time.time() - t0, 1)
    return out
