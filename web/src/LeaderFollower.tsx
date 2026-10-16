import { useEffect, useRef, useState } from "react";
import {
  Circle,
  Square,
  Play,
  Pause,
  RotateCcw,
  Save,
  Trash2,
  WandSparkles,
  Activity,
} from "lucide-react";
import RobotStage from "./RobotStage";
import { request, waitJob, message, type Doc, type Context } from "./studio";
export default function LeaderFollower({
  context,
  setContext,
}: {
  context: Context;
  setContext: (c: Partial<Context>) => void;
}) {
  const [config, setConfig] = useState<any>(),
    [q, setQ] = useState<number[]>([]),
    [poses, setPoses] = useState<any>(),
    [mode, setMode] = useState("orbit"),
    [camera, setCamera] = useState("perspective"),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const [recording, setRecording] = useState(false),
    [draft, setDraft] = useState<any>(),
    [items, setItems] = useState<Doc[]>([]),
    [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false),
    [name, setName] = useState("Leader demonstration"),
    [busy, setBusy] = useState(""),
    [simulation, setSimulation] = useState<Doc>(),
    [runItems, setRunItems] = useState<Doc[]>([]),
    [controller, setController] = useState("reference"),
    [workspace, setWorkspace] = useState<Doc>(),
    [revisions, setRevisions] = useState<Doc[]>([]),
    [referenceRevision, setReferenceRevision] = useState(""),
    [candidateRevision, setCandidateRevision] = useState("");
  const current = useRef(q),
    selected = useRef(context.selected),
    ikBusy = useRef(false),
    pendingTarget = useRef<number[] | null>(null);
  current.current = q;
  selected.current = context.selected;
  const refresh = () => request<Doc[]>("/documents/trajectory").then(setItems);
  const refreshRuns = () =>
    request<Doc[]>("/documents/simulation").then(setRunItems);
  useEffect(() => {
    request("/configuration")
      .then((c) => {
        setConfig(c);
        setQ(c.home);
      })
      .catch((e) => setError(message(e)));
    refresh();
    refreshRuns();
  }, []);
  useEffect(() => {
    if (context.trajectory)
      request<Doc>("/record/" + context.trajectory)
        .then((d) => {
          setDraft(d.data);
          setName(d.name);
          setQ(d.data.q[0]);
          setTime(0);
          setPlaying(false);
        })
        .catch((e) => setError(message(e)));
  }, [context.trajectory]);
  useEffect(() => {
    if (context.run)
      request<Doc>("/record/" + context.run)
        .then(setSimulation)
        .catch((e) => setError(message(e)));
  }, [context.run]);
  useEffect(() => {
    if (!q.length) return;
    let disposed = false;
    const timer = setTimeout(async () => {
      try {
        const p = await request("/pose", "POST", { q });
        const results = simulation?.data.results || {};
        const result = results[controller] || results.candidate || Object.values<any>(results)[0];
        if (result) {
          let i = result.time.findIndex((t: number) => t >= time);
          if (i < 0) i = result.time.length - 1;
          p.follower = await request("/follower-pose", "POST", {
            q: result.q_actual[i],
          });
        }
        if (!disposed) {
          setPoses(p);
          if (p.mapping.warnings.length)
            setNotice(p.mapping.warnings.join("; "));
        }
      } catch (e) {
        if (!disposed) setError(message(e));
      }
    }, 20);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [q, simulation, controller, time]);
  useEffect(() => {
    if (!recording) return;
    const samples: number[][] = [],
      times: number[] = [];
    const start = performance.now();
    const timer = setInterval(() => {
      times.push((performance.now() - start) / 1000);
      samples.push([...current.current]);
      setTime(times.at(-1)!);
    }, 20);
    return () => {
      clearInterval(timer);
      if (times.length >= 3)
        setDraft({
          configuration_id: config.configuration_id,
          joint_ids: config.joint_ids,
          time: times.map((t) => t - times[0]),
          q: samples,
          provenance:
            "Recorded from interactive leader control, browser monotonic clock; source URDF limits enforced",
        });
    };
  }, [recording, config]);
  useEffect(() => {
    if (!playing || !draft) return;
    const start = performance.now() - time * 1000;
    const timer = setInterval(() => {
      const t = Math.min((performance.now() - start) / 1000, draft.time.at(-1));
      seek(t);
      if (t >= draft.time.at(-1)) setPlaying(false);
    }, 25);
    return () => clearInterval(timer);
  }, [playing, draft, simulation, controller]);
  function seek(t: number) {
    setTime(t);
    if (!draft) return;
    let i = draft.time.findIndex((v: number) => v >= t);
    if (i < 0) i = draft.time.length - 1;
    const a = Math.max(0, i - 1),
      alpha = (t - draft.time[a]) / (draft.time[i] - draft.time[a] || 1);
    setQ(
      draft.q[a].map((v: number, j: number) => v + (draft.q[i][j] - v) * alpha),
    );
  }
  const joints = config?.leader.joints || [];
  const change = (index: number, value: number) => {
    setPlaying(false);
    setQ((old) => {
      const next = [...old],
        joint = joints.find((j: any) => j.name === config.joint_ids[index]);
      const lo = joint?.limit?.lower ?? -Math.PI,
        hi = joint?.limit?.upper ?? Math.PI;
      next[index] = Math.min(hi, Math.max(lo, value));
      return next;
    });
  };
  const select = (link: string) => {
    const child = link.split("/").at(-1);
    const joint = joints.find((j: any) => j.child === child);
    // Driving the leader (joint drag / IK) changes only the joint; the engineering focus robot (usually the
    // follower under study) is changed by clicking a robot in orbit mode or by the focus switch.
    if (mode !== "orbit") setContext({ selected: joint?.name || child! });
    else
      setContext({
        selected: joint?.name || child!,
        robot: link.startsWith("leader/") ? "aloha_wx250s" : "aloha_vx300s",
      });
  };
  const target = async (t: number[]) => {
    pendingTarget.current = t;
    if (ikBusy.current) return;
    ikBusy.current = true;
    try {
      while (pendingTarget.current) {
        const target = pendingTarget.current;
        pendingTarget.current = null;
        const result = await request("/ik", "POST", {
          q: current.current,
          target,
        });
        setNotice(result.message);
        if (result.success) {
          current.current = result.q;
          setQ(result.q);
        }
      }
    } catch (e) {
      setError(message(e));
    } finally {
      ikBusy.current = false;
    }
  };
  const focus = DYNAMIC_JOINTS.includes(context.selected)
    ? context.selected
    : "shoulder";
  const refreshRevisions = async () => {
    if (!context.model) return setRevisions([]);
    const [w, all] = await Promise.all([
      request<Doc>("/record/" + context.model),
      request<Doc[]>("/documents/revision"),
    ]);
    const own = all
      .filter((r) => r.data.workspace === context.model)
      .sort((a, b) => (a.created < b.created ? 1 : -1));
    setWorkspace(w);
    setRevisions(own);
    setReferenceRevision(
      (old) => old && own.some((r) => r.id === old) ? old : w.data.accepted || own.at(-1)?.id || "",
    );
    setCandidateRevision(w.data.head);
  };
  useEffect(() => {
    refreshRevisions().catch((e) => setError(message(e)));
  }, [context.model, context.model_revision]);
  const modelAction = async (body: any, label: string) => {
    if (!context.model) return;
    setBusy(label);
    setError("");
    try {
      let result: any = await request("/model/" + context.model + "/action", "POST", body);
      if (result?.kind === "job") result = await waitJob(result);
      await refreshRevisions();
      return result;
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  };
  const run = async (axes: number) => {
    if (!context.trajectory) return;
    setBusy(
      `OpenModelica · ${axes === 1 ? focus + " axis" : "six torque-driven axes"} · ${referenceRevision === candidateRevision ? "one revision" : "reference and candidate revisions"}`,
    );
    setError("");
    try {
      const record = await waitJob(
        await request(
          "/trajectory/" + context.trajectory + "/simulate?axes=" + axes,
          "POST",
          {
            model: context.model,
            reference_revision: referenceRevision || undefined,
            candidate_revision: candidateRevision || undefined,
            focus,
          },
        ),
      );
      setSimulation(record);
      setTime(0);
      if (draft) setQ(draft.q[0]);
      setContext({ run: record.id });
      refreshRuns();
      setNotice(record.data.conclusion);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  };
  const save = async () => {
    try {
      const record = await request<Doc>("/documents/trajectory", "POST", {
        name,
        data: draft,
      });
      setContext({ trajectory: record.id, run: undefined });
      await refresh();
      setNotice(
        "Recording saved locally with numerical velocities, accelerations and provenance.",
      );
    } catch (e) {
      setError(message(e));
    }
  };
  return (
    <div className="wb-workspace">
      <div className="wb-title">
        <div>
          <span className="wb-eyebrow">TELEOPERATION LAB</span>
          <h1>Leader–Follower</h1>
          <p>Shape a motion. Record the reference. Measure the follower.</p>
        </div>
        <span className="wb-badge">
          {simulation ? "TORQUE-DRIVEN RESULT" : "KINEMATIC REPLAY"}
        </span>
      </div>
      <div className="wb-lab-grid">
        <section className="wb-card">
          <div className="wb-toolbar">
            <div className="wb-segment">
              {[
                ["orbit", "Orbit"],
                ["joint", "Joint drag"],
                ["ee", "End-effector IK"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  aria-pressed={mode === id}
                  onClick={() => setMode(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <select
              aria-label="Camera"
              value={camera}
              onChange={(e) => setCamera(e.target.value)}
            >
              {["perspective", "front", "top", "side"].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <button
              onClick={() => {
                setQ(config.home);
                setPlaying(false);
                setTime(0);
              }}
              disabled={!config}
            >
              <RotateCcw size={14} />
              Home
            </button>
          </div>
          <RobotStage
            poses={poses}
            mode={mode}
            camera={camera}
            selected={
              (context.robot === "aloha_wx250s"
                ? "leader/"
                : "follower_right/") +
              (joints.find((j: any) => j.name === context.selected)?.child ||
                context.selected)
            }
            onSelect={select}
            onJoint={(delta) => {
              const index = config.joint_ids.indexOf(selected.current);
              if (index >= 0)
                change(
                  index,
                  current.current[index] + delta * (index === 7 ? 0.01 : 1),
                );
            }}
            onTarget={target}
          />
          <div className="wb-record-bar">
            <button
              className={recording ? "wb-danger" : ""}
              onClick={() => {
                setPlaying(false);
                setRecording(!recording);
                if (!recording) {
                  setContext({ trajectory: undefined, run: undefined });
                  setSimulation(undefined);
                  setDraft(undefined);
                }
              }}
            >
              {recording ? <Square size={14} /> : <Circle size={14} />}{" "}
              {recording ? "Stop recording" : "Record leader"}
            </button>
            <button
              disabled={!draft || recording}
              onClick={() => setPlaying(!playing)}
            >
              {playing ? <Pause size={14} /> : <Play size={14} />}{" "}
              {playing ? "Pause" : "Play"}
            </button>
            <button
              disabled={!draft || recording}
              onClick={() => {
                setPlaying(false);
                seek(0);
              }}
            >
              <RotateCcw size={14} />
              Reset
            </button>
            <span className="wb-mono">{time.toFixed(2)} s</span>
            <input
              aria-label="Trajectory seek"
              type="range"
              min="0"
              max={draft?.time.at(-1) || 1}
              step=".01"
              value={Math.min(time, draft?.time.at(-1) || 1)}
              disabled={!draft || recording}
              onChange={(e) => {
                setPlaying(false);
                seek(+e.target.value);
              }}
            />
          </div>
          <div className="wb-footnote">
            Teal: commanded leader · Blue:{" "}
            {simulation
              ? "selected OpenModelica follower response"
              : "joint-mapped kinematic follower"}
            . Side-by-side offsets are for display; hardware registration is
            unknown.
          </div>
        </section>
        <aside className="wb-card wb-inspector">
          <div className="wb-panel-heading">
            <h2>Joint control</h2>
            <span>SI UNITS</span>
          </div>
          {config?.joint_ids.map((id: string, index: number) => {
            const joint = joints.find((j: any) => j.name === id);
            return (
              <div
                className={
                  "wb-joint " + (context.selected === id ? "selected" : "")
                }
                key={id}
              >
                <button
                  onClick={() =>
                    setContext({ selected: id })
                  }
                >
                  {id.replaceAll("_", " ")}
                  <small>{index === 7 ? "m" : "rad"}</small>
                </button>
                <input
                  aria-label={id}
                  type="range"
                  min={joint?.limit?.lower ?? -Math.PI}
                  max={joint?.limit?.upper ?? Math.PI}
                  step={index === 7 ? 0.0001 : 0.002}
                  value={q[index] ?? 0}
                  onChange={(e) => change(index, +e.target.value)}
                />
                <output>{q[index]?.toFixed(index === 7 ? 4 : 3)}</output>
              </div>
            );
          })}
          <div className="wb-callout">
            <strong>Explicit correspondence</strong>
            <p>{config?.mapping.rotational}</p>
            <p>{config?.mapping.gripper}</p>
            <p>{config?.mapping.cartesian}</p>
          </div>
        </aside>
      </div>
      {notice && (
        <div className="wb-notice" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="wb-error" role="alert">
          {error}
        </div>
      )}
      <div className="wb-lower-grid">
        <section className="wb-card wb-pad">
          <div className="wb-panel-heading">
            <h2>Motion library</h2>
            <span>LOCAL · VERSIONED</span>
          </div>
          <div className="wb-toolbar">
            <input
              aria-label="Recording name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button disabled={!draft || recording} onClick={save}>
              <Save size={14} />
              Save recording
            </button>
          </div>
          <div className="wb-list">
            {items.map((item) => (
              <div
                key={item.id}
                className={context.trajectory === item.id ? "active" : ""}
              >
                <button
                  disabled={recording}
                  onClick={() => {
                    setContext({ trajectory: item.id, run: undefined });
                    setSimulation(undefined);
                    setDraft(item.data);
                    setName(item.name);
                    setTime(0);
                    setQ(item.data.q[0]);
                  }}
                >
                  <strong>{item.name}</strong>
                  <small>
                    {item.data.time.at(-1).toFixed(2)} s ·{" "}
                    {item.data.time.length} samples ·{" "}
                    {item.data.derived ? "smoothed copy" : "original"}
                  </small>
                </button>
                <a
                  href={"/api/workbench/record/" + item.id}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={"Export " + item.name}
                >
                  JSON
                </a>
                <button
                  aria-label={"Delete " + item.name}
                  onClick={async () => {
                    if (
                      !confirm(
                        "Delete this saved trajectory? Its original provenance remains in the local audit history.",
                      )
                    )
                      return;
                    try {
                      await request(
                        "/record/" +
                          item.id +
                          "?version=" +
                          item.version +
                          "&confirmed=true",
                        "DELETE",
                      );
                      if (context.trajectory === item.id)
                        setContext({ trajectory: undefined });
                      refresh();
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {!items.length && (
              <p className="wb-muted">
                Record a leader motion and save it to create your first
                reference.
              </p>
            )}
          </div>
          <button
            disabled={!context.trajectory || recording}
            onClick={async () => {
              try {
                const item = await request(
                  "/trajectory/" + context.trajectory + "/smooth",
                  "POST",
                );
                setContext({ trajectory: item.id, run: undefined });
                setDraft(item.data);
                setSimulation(undefined);
                refresh();
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            <WandSparkles size={14} />
            Create smoothed copy
          </button>
          <p className="wb-footnote">
            Nonuniform timestamps → second-order numerical velocities →
            numerical accelerations. Smoothing resamples uniformly and creates a
            new Savitzky–Golay copy; the original stays intact.
          </p>
        </section>
        <section className="wb-card wb-pad">
          <div className="wb-panel-heading">
            <h2>Dynamic follower · revision comparison</h2>
            <Activity size={17} />
          </div>
          <p className="wb-footnote">
            Kinematic replay (3D, above) copies joint angles. This panel runs
            the real OpenModelica torque-driven follower: URDF inertias,
            gravity, coupling, effort limits, and the servo parameters stored
            in each model revision (<code>Control/FollowerServoSettings.mo</code>,
            assumed values).
          </p>
          {!context.model ? (
            <p className="wb-notice">
              Open the Modelica Engineering Editor once to create an editable
              model; its revisions are compared here.
            </p>
          ) : (
            <div className="wb-revision-pick">
              {(
                [
                  ["Reference revision", referenceRevision, setReferenceRevision],
                  ["Candidate revision", candidateRevision, setCandidateRevision],
                ] as const
              ).map(([label, value, set]) => (
                <label key={label}>
                  {label}
                  <select
                    aria-label={label}
                    value={value}
                    onChange={(e) => set(e.target.value)}
                  >
                    {revisions.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.id.slice(0, 8)} · {r.data.status}
                        {workspace?.data.accepted === r.id ? " · accepted" : ""}
                        {workspace?.data.head === r.id ? " · head" : ""} ·{" "}
                        {r.name.slice(0, 48)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          )}
          {context.model && candidateRevision && (
            <p className="wb-footnote">
              Candidate {candidateRevision.slice(0, 8)} ·{" "}
              {revisions.find((r) => r.id === candidateRevision)?.data.status || "unknown"}
              {candidateRevision === workspace?.data.head &&
                revisions.find((r) => r.id === candidateRevision)?.data.status !== "validated" && (
                  <>
                    {" "}
                    ·{" "}
                    <button
                      disabled={!!busy}
                      onClick={() =>
                        modelAction(
                          { action: "check", class_name: "ALOHA2.Experiments.RightArmReach" },
                          "OpenModelica validation of the candidate revision",
                        )
                      }
                    >
                      Validate candidate (OpenModelica)
                    </button>
                  </>
                )}
            </p>
          )}
          <div className="wb-toolbar">
            <button
              disabled={!context.trajectory || !!busy}
              onClick={() => run(1)}
              title="Only the focus joint is torque driven; faster"
            >
              Simulate {focus} axis
            </button>
            <button
              className="wb-primary"
              disabled={!context.trajectory || !!busy}
              onClick={() => run(6)}
            >
              Simulate six axes
            </button>
          </div>
          {!context.trajectory && (
            <p className="wb-muted">Select or record a leader trajectory first.</p>
          )}
          {busy && <p className="wb-notice">{busy}…</p>}
          <select
            aria-label="Saved follower simulation"
            value={context.run || ""}
            onChange={async (e) => {
              if (!e.target.value) {
                setSimulation(undefined);
                setContext({ run: undefined });
                return;
              }
              try {
                const result = await request<Doc>("/record/" + e.target.value);
                setSimulation(result);
                setContext({
                  run: result.id,
                  trajectory: result.data.trajectory,
                });
                setTime(0);
                setPlaying(false);
              } catch (error) {
                setError(message(error));
              }
            }}
          >
            <option value="">Saved simulations…</option>
            {runItems.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} · {new Date(r.created).toLocaleString()}
              </option>
            ))}
          </select>
          {simulation && (
            <SimulationResult
              simulation={simulation}
              focus={simulation.data.focus || focus}
              joints={config?.joint_ids || []}
              controller={controller}
              setController={setController}
              workspace={workspace}
              revisions={revisions}
              busy={!!busy}
              onValidate={() =>
                modelAction(
                  { action: "check", class_name: "ALOHA2.Experiments.RightArmReach" },
                  "OpenModelica validation of the candidate revision",
                )
              }
              onAccept={(revision: string) =>
                modelAction({ action: "accept", revision }, "Accepting revision")
              }
              onRollback={async (revision: string) => {
                if (!context.model) return;
                const changes = await request("/model/" + context.model + "/changes");
                await modelAction(
                  { action: "restore", revision, hashes: changes.hashes },
                  "Restoring reference revision",
                );
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
}
function Signal({ result }: { result: any }) {
  const values = result.ee_error_m.map((n: number) => n * 1000),
    hi = Math.max(...values, 0.001);
  return (
    <div className="wb-signal">
      <span>End-effector error · mm · actual OMC result</span>
      <svg
        viewBox="0 0 600 100"
        role="img"
        aria-label="Measured follower end-effector error"
      >
        <path
          d={values
            .map(
              (v: number, i: number) =>
                `${i ? "L" : "M"}${(i / (values.length - 1)) * 600},${90 - (v / hi) * 75}`,
            )
            .join(" ")}
          fill="none"
          stroke="#2563EB"
          strokeWidth="2"
        />
        <text x="4" y="12" fill="#92a4ba">
          {hi.toFixed(2)} mm
        </text>
      </svg>
    </div>
  );
}

function JointSignal({
  result,
  index,
  name,
}: {
  result: any;
  index: number;
  name: string;
}) {
  const reference = result.q_reference.map((row: number[]) => row[index]),
    actual = result.q_actual.map((row: number[]) => row[index]),
    lo = Math.min(...reference, ...actual),
    hi = Math.max(...reference, ...actual),
    span = Math.max(hi - lo, 0.001);
  const path = (values: number[]) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${(i / (values.length - 1)) * 600},${90 - ((v - lo) / span) * 75}`,
      )
      .join(" ");
  return (
    <div className="wb-signal">
      <span>{name} · joint tracking · rad</span>
      <svg
        viewBox="0 0 600 110"
        role="img"
        aria-label="Mapped leader reference and measured follower joint angle"
      >
        <path
          d={path(reference)}
          fill="none"
          stroke="#0D9488"
          strokeWidth="2"
        />
        <path d={path(actual)} fill="none" stroke="#2563EB" strokeWidth="2" />
        <text x="4" y="12" fill="#8da5bd">
          {hi.toFixed(3)} rad
        </text>
        <text x="4" y="107" fill="#8da5bd">
          {lo.toFixed(3)} rad
        </text>
      </svg>
      <p className="wb-footnote">
        Teal: mapped leader reference · Blue: torque-driven follower response
      </p>
    </div>
  );
}

const DYNAMIC_JOINTS = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate"];

function SimulationResult({
  simulation,
  focus,
  joints,
  controller,
  setController,
  workspace,
  revisions,
  busy,
  onValidate,
  onAccept,
  onRollback,
}: {
  simulation: Doc;
  focus: string;
  joints: string[];
  controller: string;
  setController: (v: string) => void;
  workspace?: Doc;
  revisions: Doc[];
  busy: boolean;
  onValidate: () => void;
  onAccept: (revision: string) => void;
  onRollback: (revision: string) => void;
}) {
  const results = simulation.data.results || {};
  const names = Object.keys(results);
  const runs: any[] = simulation.data.runs || names.map((n) => ({ name: n, label: n }));
  const index = Math.max(0, joints.indexOf(focus));
  const ref = results.reference || results.baseline;
  const cand = results.candidate || results.improved;
  const label = (n: string) =>
    runs.find((r) => r.name === n)?.label?.split(" · ")[0] ||
    ({ baseline: "baseline (legacy)", improved: "comparison (legacy)" } as any)[n] ||
    n;
  const status = (rid?: string) => revisions.find((r) => r.id === rid)?.data.status;
  const candidateRun = runs.find((r) => r.name === "candidate");
  const referenceRun = runs.find((r) => r.name === "reference");
  const candidateStatus = status(candidateRun?.revision);
  const servo = (n: string) => results[n]?.config?.servo?.[focus];
  const rows: [string, (m: any) => number, number, string][] = [
    [`${focus} RMS error`, (m) => m.joint_rms_rad[index], 1000, "mrad"],
    [`${focus} maximum error`, (m) => m.joint_max_rad[index], 1000, "mrad"],
    ["End-effector RMS error", (m) => m.ee_rms_m, 1000, "mm"],
    ["End-effector maximum error", (m) => m.ee_max_m, 1000, "mm"],
    [`${focus} peak effort`, (m) => m.peak_effort_Nm[index], 1, "N·m"],
    ["Limit-violation samples", (m) => m.limit_violation_samples + m.velocity_limit_violation_samples, 1, ""],
  ];
  return (
    <div className="wb-sim-result">
      {ref && <TrackingComparison reference={ref} candidate={cand} index={index} name={focus} />}
      <table className="wb-table">
        <thead>
          <tr>
            <th>Measured on the same recorded reference (OpenModelica)</th>
            {names.map((n) => (
              <th key={n}>{label(n)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([title, get, scale, unit]) => (
            <tr key={title}>
              <td>{title}</td>
              {names.map((n) => (
                <td key={n}>
                  {(get(results[n].metrics) * scale).toFixed(unit ? 2 : 0)} {unit}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td>{focus} servo (kp · kd · lag · feed-forward)</td>
            {names.map((n) => (
              <td key={n}>
                {servo(n)
                  ? `${servo(n).kp} · ${servo(n).kd} · ${servo(n).actuatorTime} s · ${servo(n).feedforward}`
                  : results[n].config?.kp !== undefined
                    ? `${results[n].config.kp} · ${results[n].config.kd} (legacy)`
                    : "—"}
              </td>
            ))}
          </tr>
          <tr>
            <td>Revision</td>
            {names.map((n) => {
              const rid = runs.find((r) => r.name === n)?.revision;
              return (
                <td key={n}>
                  {rid ? rid.slice(0, 8) : "generated baseline"}
                  {rid && status(rid) ? ` · ${status(rid)}` : ""}
                  {rid && workspace?.data.accepted === rid ? " · accepted" : ""}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
      <p className="wb-notice">{simulation.data.conclusion}</p>
      {candidateRun?.revision && workspace && (
        <div className="wb-decision">
          <strong>Decision on candidate {candidateRun.revision.slice(0, 8)}</strong>
          <span>
            {workspace.data.accepted === candidateRun.revision
              ? "Accepted: this validated revision is now the model's reference revision."
              : candidateStatus === "validated"
              ? "OpenModelica validation passed."
              : candidateRun.revision === workspace.data.head
                ? "Not yet validated by OpenModelica."
                : "Only the head revision can be validated."}
          </span>
          <div className="wb-toolbar">
            <button
              disabled={busy || candidateStatus === "validated" || candidateRun.revision !== workspace.data.head}
              onClick={onValidate}
            >
              Validate candidate (OpenModelica)
            </button>
            <button
              className="wb-primary"
              disabled={busy || candidateStatus !== "validated" || workspace.data.accepted === candidateRun.revision}
              onClick={() => onAccept(candidateRun.revision)}
            >
              Accept candidate
            </button>
            {referenceRun?.revision && (
              <button
                disabled={busy}
                onClick={() => {
                  if (confirm("Restore the reference revision into a new working revision? The candidate stays in history."))
                    onRollback(referenceRun.revision);
                }}
              >
                Roll back to reference
              </button>
            )}
          </div>
          <small>
            Acceptance requires a validated revision and your explicit click; roll back creates a new revision and
            keeps the candidate in history.
          </small>
        </div>
      )}
      <select
        aria-label="Follower response shown in 3D playback"
        value={controller}
        onChange={(e) => setController(e.target.value)}
      >
        {names.map((n) => (
          <option key={n} value={n}>
            3D playback: {label(n)} follower response
          </option>
        ))}
      </select>
      <Signal result={results[controller] || results[names[0]]} />
      <details>
        <summary>All joint metrics, delays and limitations</summary>
        {names.map((n) => (
          <pre key={n}>{label(n) + ":\n" + JSON.stringify(results[n].metrics, null, 2)}</pre>
        ))}
        <ul>
          {(simulation.data.limitations || []).map((l: string) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function TrackingComparison({
  reference,
  candidate,
  index,
  name,
}: {
  reference: any;
  candidate?: any;
  index: number;
  name: string;
}) {
  const col = (rows: number[][]) => rows.map((r) => r[index]);
  const lead = col(reference.q_reference),
    a = col(reference.q_actual),
    b = candidate ? col(candidate.q_actual) : [];
  const all = [...lead, ...a, ...b],
    lo = Math.min(...all),
    hi = Math.max(...all),
    span = Math.max(hi - lo, 1e-4);
  const t0 = reference.time[0],
    t1 = reference.time.at(-1) || 1;
  const path = (time: number[], values: number[]) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${(((time[i] - t0) / (t1 - t0)) * 600).toFixed(1)},${(95 - ((v - lo) / span) * 82).toFixed(1)}`,
      )
      .join(" ");
  const err = candidate
    ? candidate.q_actual.map((r: number[], i: number) => (r[index] - candidate.q_reference[i][index]) * 1000)
    : [];
  const emax = Math.max(1e-3, ...err.map(Math.abs));
  return (
    <div className="wb-signal">
      <span>{name} · leader reference vs follower responses · rad · OpenModelica</span>
      <svg viewBox="0 0 600 105" role="img" aria-label={`${name} reference and simulated follower angles`}>
        <path d={path(reference.time, lead)} fill="none" stroke="#0D9488" strokeWidth="2.5" />
        <path d={path(reference.time, a)} fill="none" stroke="#7aa7f7" strokeWidth="2" strokeDasharray="6 4" />
        {candidate && <path d={path(candidate.time, b)} fill="none" stroke="#2563EB" strokeWidth="2" />}
        <text x="4" y="11" fill="#8da5bd">{hi.toFixed(3)} rad</text>
        <text x="4" y="103" fill="#8da5bd">{lo.toFixed(3)} rad</text>
      </svg>
      <p className="wb-legend">
        <span className="leader">— leader reference (mapped)</span>
        <span className="ref">- - reference revision follower</span>
        {candidate && <span className="cand">— candidate revision follower</span>}
      </p>
      {candidate && (
        <>
          <span>{name} · candidate tracking error · mrad</span>
          <svg viewBox="0 0 600 60" role="img" aria-label="Candidate tracking error">
            <line x1="0" x2="600" y1="30" y2="30" stroke="#33465c" />
            <path
              d={err
                .map(
                  (v: number, i: number) =>
                    `${i ? "L" : "M"}${(((candidate.time[i] - t0) / (t1 - t0)) * 600).toFixed(1)},${(30 - (v / emax) * 26).toFixed(1)}`,
                )
                .join(" ")}
              fill="none"
              stroke="#2563EB"
              strokeWidth="1.5"
            />
            <text x="4" y="10" fill="#8da5bd">±{emax.toFixed(2)} mrad</text>
          </svg>
        </>
      )}
    </div>
  );
}
