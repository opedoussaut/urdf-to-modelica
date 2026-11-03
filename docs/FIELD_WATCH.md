# Field watch: robot foundation models and manipulation benchmarks

**As of 20 October 2026.** Sources were opened and checked on that date; nothing below is written from memory.
The field moves weekly, so every entry carries its date and link. Re-check before quoting a number.

Why this file exists: HT GEN7 PhysAI Studio trains no policy. Its evidence is (1) the engineering model's verification
(`reports/DETECTION_RESULTS.md`), (3) the grounding research question. This file tracks what learned robot "brains"
output and how they are measured, so the studio stays a useful **pre-deployment engineering check** for any of them
rather than a competitor to them. The plain-language version lives in the studio: Physical AI Atlas, concepts
*Robot foundation models* and *Benchmarks: how robot AI is measured*.

**Reading key.** *Vendor claim* = reported by the model's own authors or company. *Independent* = measured by a party
that did not build the model. "Not stated" means the source we opened does not say; it does not mean "no".

## 1. Models

### 1.1 Dream Labs, Dream-1 (out of stealth 19 Oct 2026)

| | |
|---|---|
| What it outputs | Two modes. Joint angles for robots it supports natively; for robots it has never seen, **end-effector (EEF) poses**: where each gripper should be and whether it is open or closed. **The robot's own IK solver** turns those poses into joint commands. Each call returns 1.6 s of actions. |
| Embodiment assumptions | Two arms with parallel grippers; three cameras (head + one wrist camera per arm). Vendor states performance depends on the quality of each robot's IK solver, and that robots whose kinematics or workspace differ sharply from training may get infeasible predictions. Vendor: Dream-1 "doesn't control how the arm reaches a pose, only where the gripper ends up". |
| Evaluation | *Vendor claim:* simulation on 27 unseen robots (300 rollouts each) against YAM, the robot it was trained on; real clips from 12 partner sites and in-house; one-shot adaptation still beats zero-shot. *Independent:* Robocurve (a Public Benefit Corporation) RoboDojo-RC Tier 1, mean score **59.3 %** over 120 runs, runs published with videos; next best on that leaderboard Gemini 4 Argon (high) 48 %, GR00T N1.7 10 %. Robocurve ran it ahead of launch; its investors are not named on its site and the robot platform used for RoboDojo-RC is not stated there. No other replication yet. |
| Availability, cost | Hosted API (platform.dreamlabs.ai), $3/h (Dream-1), $2/h (Dream-1-flash); fine-tuning as a service. Open weights not stated. Labelled **research beta**, "not been validated for safety-critical use". Runs in the cloud. |
| Impact on the studio | Highest. A cloud policy that emits gripper poses for an ALOHA-class arm and leaves IK to the robot is exactly the case the studio can check offline: are the poses reachable within URDF limits, and do the resulting joint motions stay within torque and speed? (Cloud inference conflicts with the studio's local-only runtime rule, so the studio can only consume recorded outputs, never call the API.) |

Sources: [Dream Labs, Zero-Shot to New Robots: Introducing Dream-1](https://dreamlabs.ai/research/dream-1/) ·
[Robocurve leaderboard](https://robocurve.org/) · [Robocurve, all runs](https://robocurve.org/all-runs/) ·
[SiliconANGLE, 19 Oct 2026, $90M seed](https://siliconangle.com/2026/10/19/dream-labs-raises-90m-to-help-build-more-intelligent-robots-with-simple-video-feeds/)

### 1.2 NVIDIA DreamZero, "World Action Models are Zero-shot Policies" (17 Feb 2026)

The paper that named the **World Action Model (WAM)**: "a foundation model designed to predict both actions and visual
future states in an aligned manner", built on a video diffusion backbone (14B), 7 Hz closed loop. Outputs relative
joint positions jointly with predicted video. Robots: AgiBot G1 (main), Franka/DROID, YAM (few-shot transfer with
30 min of play data). Evaluation mostly real robot, by the authors (*vendor claim*: over 2x generalisation vs VLAs).
The Dream Labs founders are among its authors.
Impact on the studio: confirms "learn from video, then adapt to a body" as the direction; the body still has to be
described somewhere, which is what the URDF + Modelica model does.
Source: [arXiv 2602.15922](https://arxiv.org/abs/2602.15922)

### 1.3 Physical Intelligence, pi series

| Model (date) | Outputs / embodiment | Evaluation | Availability |
|---|---|---|---|
| pi0 (31 Oct 2024), pi0-FAST, pi0.5 (22 Apr 2025) | Flow-matching (pi0, pi0.5) or tokenised (FAST) action chunks; per-robot checkpoints. openpi ships ALOHA checkpoints (towel, tupperware, pen-uncap) with 14-D actions, DROID and LIBERO. Joint vs EEF is set per robot config, not stated in the README. | Vendor real-robot results; pi0.5-LIBERO for the sim benchmark. Independent: RoboDojo real-world, pi0.5 was the best policy at **12.8 % success** (humans 100 %). | **Open weights**, Apache-2.0 (openpi). Inference > 8 GB GPU; LoRA fine-tune > 22.5 GB; Ubuntu only. |
| pi*0.6 (17 Nov 2025) | Learns from its own experience (RL "Recap"). | Vendor claim only (throughput, failure rate on espresso, laundry, boxes). | Not released as weights. |
| pi0.7 (16 Apr 2026) | Steerable: the prompt can set speed, quality and **control mode (joint or end-effector)**; bimanual UR5e laundry zero-shot. | Vendor real-robot only; no public benchmark named. | Weights not stated. |
| API beta (13 Oct 2026) | Hosted fine-tuning and inference. | Partner anecdotes, no figures. | Waitlist; pricing not stated. |

Impact on the studio: openpi is the one strong policy family with **public ALOHA checkpoints that output joint
targets**; its recorded actions are the most direct thing the studio's follower model could replay and check. The GPU
need (> 8 GB) exceeds this machine's 6 GB RTX A1000, so outputs would have to come from recordings, not live runs here.
Sources: [pi blog index](https://www.pi.website/blog) · [pi0.7](https://www.pi.website/blog/pi07) ·
[API beta](https://www.pi.website/blog/api-beta) · [openpi on GitHub](https://github.com/Physical-Intelligence/openpi)

### 1.4 NVIDIA Isaac GR00T N1.6 / N1.7

3B VLA. N1.7 (announced GTC, March 2026; now general availability) swaps in a Cosmos-Reason2-2B backbone. **Action
space: relative end-effector deltas** (a DROID tag also has relative joints); per-embodiment input/output layers;
embodiment tags for LIBERO Panda, SimplerEnv WidowX/Google, Unitree G1, SO-100, "new embodiment". No ALOHA tag.
Evaluation: vendor sim (RoboCasa, SimplerEnv, LIBERO) and G1 real, no numbers on the page. Independent: Robocurve
RoboDojo-RC Tier 1, **9.5 %**; LIBERO-Plus robustness 75.1 % (third-party paper). Code Apache-2.0, weights NVIDIA
Open Model License; inference 16 GB+ GPU, fine-tuning 40 GB+.
Impact on the studio: EEF-delta output again needs an IK step and limit checks before it reaches an ALOHA arm. Too
large for this GPU.
Sources: [Isaac-GR00T on GitHub](https://github.com/NVIDIA/Isaac-GR00T) ·
[GR00T N1.6 model card](https://huggingface.co/nvidia/GR00T-N1.6-3B) ·
[IndustrialVLA-Bench, arXiv 2609.25562](https://arxiv.org/abs/2609.25562)

### 1.5 Google DeepMind, Gemini Robotics 2 family (30 Jul 2026)

Gemini Robotics 2 (VLA, "vision and language input into motor control", whole-body humanoid to bi-arm), ER 2
(embodied reasoning: plans, does not output motor commands), On-Device 2 (local VLA). Robots shown: Apptronik Apollo 2,
Franka Duo, and for On-Device 2 adaptation Dexmate, SO101 and Trossen bi-arm platforms. Earlier Gemini Robotics models
(2025) were trained largely on ALOHA. Evaluation: vendor real-robot bar charts; ASIMOV safety benchmark; no independent
policy benchmark found. Availability: ER 2 in Google AI Studio; VLA and On-Device 2 for early-access partners only.
Impact on the studio: the most ALOHA-adjacent closed model, but not obtainable; watch for On-Device 2 access, which
would be the first local option with Trossen support.
Sources: [DeepMind blog, Gemini Robotics 2](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/) ·
[Gemini Robotics models page](https://deepmind.google/models/gemini-robotics/)

### 1.6 OpenVLA / OpenVLA-OFT (2024-2025)

7B VLA trained on 970k Open X-Embodiment trajectories; 7-D action (delta position, delta rotation, gripper) for
single-arm WidowX/Bridge; OFT adds continuous actions, faster inference and bimanual control. Evaluation: authors'
LIBERO 76.5 % (base) and WidowX real. Code MIT, weights under the Llama 2 licence; LoRA needs ~27 GB+.
Impact on the studio: low; single-arm EEF baseline, useful as the reference VLA in papers.
Source: [openvla on GitHub](https://github.com/openvla/openvla)

### 1.7 ACT and Diffusion Policy (2023, the ALOHA baselines)

ACT outputs "target joint positions for both arms", a 14-D absolute joint vector in chunks, 50 Hz; ALOHA's own policy,
80-90 % on 6 real tasks from 10 min of demonstrations (*authors*). Diffusion Policy predicts multi-step action
sequences by denoising, 12 tasks on 4 benchmarks (*authors*). Both small enough to train locally; both are standard
baselines in RoboTwin 2.0 (independent of their authors).
Impact on the studio: ACT on ALOHA is the most likely policy a user of the studio already has; its joint targets map
1:1 onto the follower model's inputs.
Sources: [ACT, arXiv 2304.13705](https://arxiv.org/abs/2304.13705) · [Diffusion Policy, arXiv 2303.04137](https://arxiv.org/abs/2303.04137)

### 1.8 LeRobot (Hugging Face)

Not a model: an open library to teleoperate, record (LeRobotDataset), train and deploy policies (ACT, Diffusion,
pi0/pi0.5, SmolVLA, ...) and evaluate in simulation (LIBERO, Meta-World, gym-aloha, RoboTwin). Hosts public ALOHA
datasets (e.g. `lerobot/aloha_static_coffee`) that the studio is using to set up twin validation.
Impact on the studio: the common data format; reading LeRobotDataset recordings is the cheapest way to feed any
policy's (or teleoperator's) actions into the twin.
Source: [LeRobot documentation](https://huggingface.co/docs/lerobot/index)

## 2. Benchmarks

| Benchmark | What it measures | Robot / sim | Status, caveats | Source |
|---|---|---|---|---|
| **LIBERO** (2023) | Task success of a policy, 4 suites, 130 tasks, lifelong learning | Single arm, simulation | Near saturated; LIBERO-PRO argues > 90 % scores largely reflect memorisation; LIBERO-Plus adds perturbations | [arXiv 2306.03310](https://arxiv.org/abs/2306.03310) · [LIBERO-PRO, arXiv 2510.03827](https://arxiv.org/abs/2510.03827) |
| **SimplerEnv** (CoRL 2024) | Sim success designed to correlate with real-world ranking (MMRV, Pearson) | Google Robot, WidowX; single arm; 7-D EEF delta | No bimanual tasks | [SimplerEnv](https://github.com/simpler-env/SimplerEnv) · [arXiv 2405.05941](https://arxiv.org/abs/2405.05941) |
| **RoboTwin 2.0** (2025) | 50 dual-arm tasks, Easy (clean) vs Hard (domain-randomised), 100 eval episodes/task | 5 embodiments incl. Aloha-AgileX (14 DoF), simulation | Online leaderboard; ACT, DP, DP3, RDT, pi0 as baselines | [arXiv 2506.18088](https://arxiv.org/abs/2506.18088) · [leaderboard](https://robotwin-platform.github.io/leaderboard) |
| **RoboDojo** (Jul 2026) | 42 sim tasks (generalisation, memory, precision, long horizon, open vocabulary) + 18 real tasks with remote real evaluation | Bimanual: ARX X5 (sim), ARX X5, Piper, Piper X (real) | 30 policies: best sim 8.8 % success vs humans 76 %; best real pi0.5 12.8 % | [arXiv 2607.04434](https://arxiv.org/abs/2607.04434) · [leaderboard](https://robodojo-benchmark.com/leaderboard) |
| **RoboDojo-RC Tier 1** (Robocurve, 2026) | Real-world mean score per attempt, 120 attempts, VLAs and LLM agents side by side, with cost and time | Not stated on the site | Dream-1 59.3 %, Gemini 4 Argon 48 %, GR00T N1.7 10 %; videos published | [robocurve.org](https://robocurve.org/) |
| **gym-aloha** | 2 sim tasks (TransferCube, Insertion), reward 0-4 | ALOHA in MuJoCo; 14-D absolute joint positions | Apache-2.0; the ACT paper's sim tasks | [gym-aloha](https://github.com/huggingface/gym-aloha) |

**What all of these measure:** whether a *policy* completes a task (success rate or score). **What none of them
measure:** whether the robot's engineering model is right, whether a commanded motion respects joint limits, torque
and speed with margin, or where each number in the model came from. That gap is the studio's ground.

## 3. Cross-cutting observations

1. **Output space is splitting.** ACT, openpi ALOHA checkpoints and DreamZero emit **joint** targets; Dream-1
   (zero-shot mode), GR00T N1.7, OpenVLA and SimplerEnv use **end-effector** poses or deltas; pi0.7 lets the prompt
   choose. EEF outputs move responsibility for feasibility (IK, limits, torque) onto the robot integrator.
2. **Independent evaluation is new and thin.** Robocurve and RoboDojo are the only independent multi-model results
   found; both report low absolute numbers on real bimanual robots (except Dream-1's 59 %, one evaluator, one run set).
3. **Sim benchmarks saturate fast** (LIBERO); real, remote evaluation (RoboDojo-RealEval, Robocurve) is where
   comparison is moving.
4. **Most frontier models are cloud or partner-only** (Dream-1, pi API, Gemini Robotics 2). Open weights that fit a
   6 GB GPU are limited to small policies (ACT, Diffusion Policy, SmolVLA-class).

## 4. Recommendations for the studio

1. **Do not chase policy leaderboards.** The studio trains no policy; a LIBERO or RoboDojo score would measure someone
   else's model. Say so explicitly in the studio (done: Atlas concept *Benchmarks: how robot AI is measured*).
2. **Add a "policy pre-flight" check that accepts both output types.** Joint targets (ACT, openpi ALOHA) go straight
   into the follower model; EEF poses (Dream-1, GR00T) go through URDF IK first. Report reachability, limit margin,
   peak torque vs URDF effort, and speed, with provenance labels. This is the concrete answer to Dream-1's own caveat
   that it controls only where the gripper ends up.
3. **Finish twin validation on public ALOHA recordings** (LeRobot `aloha_static_coffee`, held-out episodes frozen
   before tuning) and publish it as the studio's own benchmark: model error vs real encoders, per joint. That is the
   evidence a reviewer will ask for, and nobody else on this list reports it.
4. **Re-use RoboTwin 2.0 / gym-aloha only as input sources**, not as scores: their Aloha-AgileX and ALOHA tasks
   provide realistic bimanual joint trajectories to stress the pre-flight check.
5. **Re-check this file monthly** (or on any new release from Dream Labs, Physical Intelligence, NVIDIA GR00T,
   DeepMind Gemini Robotics, Robocurve, RoboDojo) and update the Atlas concepts when a claim changes.
