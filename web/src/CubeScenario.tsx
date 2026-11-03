import { CheckCircle2, Circle, Hand, Home, Move3d, MousePointer2, RotateCcw } from "lucide-react";
import type { SceneState } from "./RobotStage";

/** Live Level-1 visual grasp state (mirrors kkh.scenarios.evaluate; the backend result is authoritative). */
export type CubeState = {
  cube: number[];
  attached: boolean;
  offset: number[];
  closed: boolean;
  events: { t: number; event: string; distance?: number }[];
  invalidPenetrationSamples: number;
  insideCube: boolean;
};

export function initialCube(sc: any): CubeState {
  return { cube: [...sc.objects[0].start_m], attached: false, offset: [0, 0, 0], closed: false, events: [], invalidPenetrationSamples: 0, insideCube: false };
}

export function stepCube(state: CubeState, sc: any, ee: number[], opening: number, t: number): CubeState {
  const rule = sc.visual_grasp,
    half = sc.objects[0].size_m[2] / 2;
  let { cube, attached, offset, closed } = state;
  const events = [...state.events];
  const wasClosed = closed;
  // Point-in-box diagnostic only; no robot-mesh collision/contact solver is implied.
  const insideCube = !attached && ee.every((v, i) => Math.abs(v - cube[i]) < sc.objects[0].size_m[i] / 2 - 1e-5);
  const invalidPenetrationSamples = state.invalidPenetrationSamples + (insideCube ? 1 : 0);
  if (insideCube && !state.insideCube) events.push({ t, event: "invalid_penetration" });
  if (opening <= rule.gripper_closed_below) closed = true;
  else if (opening >= rule.gripper_open_above) closed = false;
  if (closed && !wasClosed) {
    const d = Math.hypot(ee[0] - cube[0], ee[1] - cube[1], ee[2] - cube[2]);
    if (d <= rule.capture_radius_m && !insideCube) {
      attached = true;
      offset = [cube[0] - ee[0], cube[1] - ee[1], cube[2] - ee[2]];
      events.push({ t, event: "grasp", distance: d });
    } else events.push({ t, event: "close_missed", distance: d });
  }
  if (!closed && wasClosed) {
    if (attached) {
      attached = false;
      cube = [cube[0], cube[1], half]; // declared rule: vertical drop
      events.push({ t, event: "release" });
    } else events.push({ t, event: "open" });
  }
  if (attached) cube = [ee[0] + offset[0], ee[1] + offset[1], ee[2] + offset[2]];
  return { cube, attached, offset, closed, events, invalidPenetrationSamples, insideCube };
}

export function inTarget(sc: any, cube: number[]) {
  const t = sc.targets[0];
  return Math.abs(cube[0] - t.center_m[0]) <= t.size_m[0] / 2 && Math.abs(cube[1] - t.center_m[1]) <= t.size_m[1] / 2;
}

export function sceneFor(sc: any, cube: number[], attached: boolean): SceneState {
  return {
    cube,
    attached,
    cubeSize: sc.objects[0].size_m[0],
    cubeColor: sc.objects[0].color,
    target: { center: sc.targets[0].center_m, size: sc.targets[0].size_m, color: sc.targets[0].color },
    marker: sc.labels[0].position_m,
  };
}

export function ArmControls({
  mode,
  setMode,
  gripper,
  onGripper,
  onHome,
  onJog,
  onPreset,
  busy,
}: {
  mode: string;
  setMode: (m: string) => void;
  gripper: number;
  onGripper: (open: boolean) => void;
  onHome: () => void;
  onJog: (axis: number, delta: number) => void;
  onPreset: (where: "A" | "B") => void;
  busy: boolean;
}) {
  return (
    <div className="wb-arm-controls" aria-label="Leader arm controls">
      <div className="wb-segment">
        <button aria-pressed={mode === "joint"} className={mode === "joint" ? "wb-primary" : ""} onClick={() => setMode("joint")}>
          <Hand size={14} /> Move leader arm
        </button>
        <button aria-pressed={mode === "ee"} onClick={() => setMode("ee")}>
          <Move3d size={14} /> Drag leader end effector
        </button>
        <button aria-pressed={mode === "orbit"} onClick={() => setMode("orbit")}>
          <MousePointer2 size={14} /> Look around
        </button>
      </div>
      <div className="wb-gripper">
        <span>Gripper {Math.round(gripper * 100)} % open</span>
        <button onClick={() => onGripper(true)} aria-label="Open gripper">Open</button>
        <button onClick={() => onGripper(false)} aria-label="Close gripper">Close</button>
      </div>
      <div className="wb-jog" aria-label="Move the leader gripper (Cartesian, IK)">
        <span>Move leader gripper (2 cm)</span>
        {(
          [
            ["X−", 0, -0.02],
            ["X+", 0, 0.02],
            ["Y−", 1, -0.02],
            ["Y+", 1, 0.02],
            ["Down", 2, -0.02],
            ["Up", 2, 0.02],
          ] as const
        ).map(([label, axis, d]) => (
          <button key={label} disabled={busy} onClick={() => onJog(axis, d)}>
            {label}
          </button>
        ))}
        <button disabled={busy} onClick={() => onPreset("A")} title="Not calibrated to leader base frame yet">
          <Move3d size={13} /> Above A
        </button>
        <button disabled={busy} onClick={() => onPreset("B")} title="Not calibrated to leader base frame yet">
          <Move3d size={13} /> Above B
        </button>
      </div>
      <button onClick={onHome}>
        <Home size={14} /> Home
      </button>
    </div>
  );
}

const grasp = (r: any): number | undefined => r.events.find((e: any) => e.event === "grasp")?.distance_m;

export const GUIDED_STEPS = [
  { id: "prepare", title: "Prepare", text: "Task: move the amber cube from A to the green area B. The teal leader is your input; the blue follower copies its joints and touches the cube. Press Reset scenario to start from home." },
  { id: "practice", title: "Practice", text: "Move leader arm is active: drag a highlighted teal link left/right, use the joint sliders, or the gripper buttons X/Y/Up/Down. Commands are rate-limited for smooth motion. Nothing is recorded yet." },
  { id: "record", title: "Record", text: "Press Start recording. Status, elapsed time and captured samples are shown below. Return to home first if you want a clean start." },
  { id: "perform", title: "Perform", text: "Bring the gripper to the cube with the Move-gripper buttons (X/Y, then Down), press Close, lift (Up), move over B and press Open. On the shared table the leader gripper carries the cube; in the legacy layout the follower does. Above A/B stay disabled until frame registration is verified. Follow the checklist." },
  { id: "save", title: "Stop & save", text: "Stop recording, name the experiment and save it." },
  { id: "replay", title: "Replay", text: "Replay animates the follower with the recorded joint angles (kinematic replay). The cube path comes from the backend evaluation of the saved recording." },
  { id: "simulate", title: "Simulate", text: "Run the OpenModelica follower model on this recording (Dynamic follower panel). This is a torque-driven simulation, not the replay and not a physical robot." },
  { id: "diagnose", title: "Diagnose & improve", text: "Ask the copilot why the follower deviates, inspect the parameters and Modelica editor, create a proposal revision, validate, simulate and compare." },
];

export function GuidedPanel({
  step,
  setStep,
  onExit,
  onReset,
  checklist,
  actions,
}: {
  step: number;
  setStep: (n: number) => void;
  onExit: () => void;
  onReset: () => void;
  checklist: { label: string; done: boolean; step: string }[];
  actions: React.ReactNode;
}) {
  const s = GUIDED_STEPS[step];
  return (
    <section className="wb-guided" aria-label="Guided cube transfer">
      <ol className="wb-steps">
        {GUIDED_STEPS.map((g, i) => (
          <li key={g.id} className={i === step ? "active" : i < step ? "done" : ""}>
            <button onClick={() => setStep(i)}>
              {i + 1}. {g.title}
            </button>
          </li>
        ))}
      </ol>
      <div className="wb-guided-body">
        <strong>
          Step {step + 1} · {s.title}
        </strong>
        <p>{s.text}</p>
        {(s.id === "perform" || s.id === "save") && (
          <ul className="wb-checklist">
            {checklist.filter((c) => c.step === s.id).map((c) => (
              <li key={c.label} className={c.done ? "done" : ""}>
                {c.done ? <CheckCircle2 size={14} /> : <Circle size={14} />} {c.label}
              </li>
            ))}
          </ul>
        )}
        <div className="wb-toolbar">{actions}</div>
        <div className="wb-toolbar wb-guided-nav">
          <button disabled={step === 0} onClick={() => setStep(step - 1)}>
            Back
          </button>
          <button className="wb-primary" disabled={step === GUIDED_STEPS.length - 1} onClick={() => setStep(step + 1)}>
            Next
          </button>
          <button onClick={onReset}>
            <RotateCcw size={13} /> Reset scenario
          </button>
          <button onClick={onExit}>Exit guided mode</button>
        </div>
      </div>
    </section>
  );
}

export function TaskResultCard({ result, compare }: { result: any; compare?: any }) {
  if (!result) return null;
  const simulated = result.evaluated_on?.kind === "simulated";
  const role = result.evaluated_on?.role;
  const attempt = !simulated && role === "follower" && !!result.frame;
  const title = result.evaluated_on?.title
    ? result.evaluated_on.title
    : simulated
    ? "Task on the OpenModelica follower"
    : role === "leader"
      ? "Leader demonstration (visual task)"
      : attempt
        ? "Follower attempt (joint-mapped replay, no retargeting)"
        : "Visual task result (commanded motion)";
  const m = result.metrics;
  const row = (ok: boolean, label: string) => (
    <li className={ok ? "done" : "missing"}>
      {ok ? <CheckCircle2 size={14} /> : <Circle size={14} />} {label}
    </li>
  );
  return (
    <div className="wb-task-result">
      <strong>
        {title} ·{" "}
        {m.task_completed ? "completed" : "not completed"}{" "}
        {(() => {
          const derived = !simulated && result.evaluated_on?.reference_space === "follower_joints";
          const kind = simulated ? "simulated" : derived ? "derived" : "observed";
          return (
            <span className={"wb-evidence " + kind}>
              {simulated ? "simulated" : derived ? "derived (retargeted)" : "observed commands"}
            </span>
          );
        })()}{" "}
        <span className="wb-evidence assumed">Level-1 rule</span>
      </strong>
      <ul className="wb-checklist">
        {row(m.grasped, `Gripper closed on the cube${result.events.find((e: any) => e.event === "grasp") ? ` at ${result.events.find((e: any) => e.event === "grasp").t.toFixed(2)} s` : ""}`)}
        {row(m.released, `Released${result.events.find((e: any) => e.event === "release") ? ` at ${result.events.find((e: any) => e.event === "release").t.toFixed(2)} s` : ""}`)}
        {row(m.cube_in_target, `Cube in target B (${(m.distance_to_target_centre_m * 1000).toFixed(0)} mm from centre)`)}
        {m.missed_grasps > 0 && <li className="missing">Missed grasp attempts: {m.missed_grasps}</li>}
        {m.invalid_penetration_samples > 0 && <li className="missing">Invalid interaction: end-effector point entered the cube ({m.invalid_penetration_samples} samples). Task cannot be validated.</li>}
        {compare && (
          <li>
            Placement difference vs commanded motion:{" "}
            {(Math.hypot(m.cube_final_m[0] - compare.metrics.cube_final_m[0], m.cube_final_m[1] - compare.metrics.cube_final_m[1]) * 1000).toFixed(1)} mm
            {grasp(result) !== undefined && grasp(compare) !== undefined &&
              ` · grasp distance ${(grasp(result)! * 1000).toFixed(1)} mm (commanded ${(grasp(compare)! * 1000).toFixed(1)} mm)`}
          </li>
        )}
      </ul>
      <small>
        Computed by the backend on {result.evaluated_on?.label || "the saved recording"}
        {simulated && result.evaluated_on.revision ? ` (revision ${result.evaluated_on.revision.slice(0, 8)}, ${result.evaluated_on.result})` : ""}, scenario{" "}
        {result.scenario.id} {result.scenario.version}. {simulated && "Gripper opening = recorded command (gripper not torque-driven). "}
        {result.limitations.join(" ")}
      </small>
    </div>
  );
}
