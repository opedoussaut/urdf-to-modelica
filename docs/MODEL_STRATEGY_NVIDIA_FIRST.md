# HT GEN7 PhysAI Studio — NVIDIA-first model strategy (research note, 17 October 2026)

Two separate model tracks. They answer different questions and must never be ranked against each other.

## Track 1 — engineering copilot (Ollama, local): implemented

| Item | State (verified 17 Oct 2026) |
|---|---|
| Default model | `nemotron-3-nano:4b` (single default `kkh.llm.ollama.DEFAULT_MODEL`, override `KKH_OLLAMA_MODEL`). Used by the Studio API, the Dual AI Copilot UI (from `/api/health` → `ollama.default_model`), RAG copilot and benchmark CLIs. |
| Installed models | `ollama list`: only `nemotron-3-nano:4b` (2.8 GB). `ollama ps`: 100 % GPU, RTX A1000 6 GB (≈4.4 GB used with the model resident). |
| Direct smoke test | "Why does position-only IK not prove an ALOHA gripper can grasp a cube?" → answered in 6.0 s (4.6 s load, 58 tokens). One of four bullets was wrong (claimed IK ignores joint limits; ours respects them): LLM output stays unverified. |
| Missing model | Explicit error `Local model 'X' is not installed … ollama pull X … No other model is substituted.` |
| Historical results | `reports/DETECTION_RESULTS.md` and benchmark reports keep their model IDs (qwen3:4b / qwen3:8b). They are **not** re-labelled and are not comparable like-for-like with Nemotron. A Nemotron re-run of the detection experiment is a separate, future measurement. |

### Ollama cleanup list (gated; nothing executed)

As of 17 Oct 2026 18:00 the seven non-NVIDIA models listed in the brief (`ministral-3:8b`, `gemma3:4b`, `qwen3:4b`,
`qwen3:8b`, `gemma4:latest`, `mistral:instruct`, `mistral:latest`) are **already absent** from `ollama list`.
There is nothing to remove. **Keep `nemotron-3-nano:4b`.** Consequences already in effect:
re-running historical qwen experiments requires `ollama pull qwen3:4b` / `qwen3:8b` first; the Studio reports this
explicitly instead of substituting a model.

## Track 2 — embodied AI / robot policy: research only, not deployed

Candidates to evaluate later, each in its own runtime (not Ollama, not a chatbot):

- **NVIDIA Isaac GR00T N-series** (generalist robot action / VLA) — robot-action policy; needs embodiment-specific
  fine-tuning data and an action space adapter for the ALOHA arms.
- **NVIDIA Cosmos Reason** (physical-world visual reasoning) — perception / physical reasoning; *not* a policy and
  not evidence of grasp success.
- **π₀.₅** (Physical Intelligence) — independent VLA baseline, kept as the planned comparison.

**Fair-evaluation protocol (to adopt before any claim):** a registered ALOHA task set; fixed initial object poses;
the same observation inputs and episode budgets; seeds; declared checkpoints and fine-tuning data; task-success,
collision and completion metrics with a failure taxonomy; published vs GEN7-measured scores kept apart. Results are
labelled as *simulation*, *validated engineering physics* or *real robot*. Perception scores (Cosmos) are reported
separately from manipulation success. Never cherry-pick incompatible benchmarks (LIBERO vs SimplerEnv/Bridge/WidowX).

**Hardware gate:** 6 GB VRAM supports Nemotron 3 Nano 4B. It is **not** evidence that GR00T, Cosmos 8B/32B or
larger Nemotron models run locally at acceptable speed. Any download, quantised runtime or GPU-serving stack needs a
feasibility assessment and explicit approval first.
