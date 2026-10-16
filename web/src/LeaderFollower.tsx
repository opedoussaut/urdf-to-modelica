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
    [controller, setController] = useState("baseline"),
    [gains, setGains] = useState({ kp: 80, kd: 8, lag: 0.03 });
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
        const result = simulation?.data.results?.[controller];
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
  const run = async (axes: number) => {
    if (!context.trajectory) return;
    setBusy(
      `OpenModelica · ${axes === 1 ? "single shoulder axis" : "six dynamic axes"} · baseline and comparison`,
    );
    setError("");
    try {
      const record = await waitJob(
        await request(
          "/trajectory/" + context.trajectory + "/simulate?axes=" + axes,
          "POST",
          { ...gains, model: context.model },
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
                    setContext({ selected: id, robot: "aloha_wx250s" })
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
            <h2>Dynamic follower</h2>
            <Activity size={17} />
          </div>
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
            <option value="">Select a saved simulation…</option>
            {runItems.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} · {new Date(r.created).toLocaleString()}
              </option>
            ))}
          </select>
          <p>
            Real OpenModelica MultiBody dynamics: URDF inertias, gravity,
            coupling, bounded actuator torque and source joint friction.
          </p>
          <div className="wb-control-settings">
            {(
              [
                ["kp", "Comparison Kp · Nm/rad", 1, 500, 0.5],
                ["kd", "Comparison Kd · Nm·s/rad", 0, 80, 0.1],
                ["lag", "Actuator lag · s", 0.005, 0.3, 0.005],
              ] as const
            ).map(([key, label, min, max, step]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  aria-label={label}
                  min={min}
                  max={max}
                  step={step}
                  value={gains[key]}
                  onChange={(e) =>
                    setGains({ ...gains, [key]: +e.target.value })
                  }
                />
                <small>Illustrative · user override; saved with each run</small>
              </label>
            ))}
          </div>
          <div className="wb-toolbar">
            <button
              disabled={!context.trajectory || !!busy}
              onClick={() => run(1)}
            >
              1 · Shoulder axis
            </button>
            <button
              className="wb-primary"
              disabled={!context.trajectory || !!busy}
              onClick={() => run(6)}
            >
              2 · Six-axis comparison
            </button>
          </div>
          {busy && (
            <p className="wb-notice">
              {busy}. Compiling and simulating two isolated models…
            </p>
          )}
          <p className="wb-footnote">
            Gains 40/4 versus 80/8 plus inverse-dynamics feedforward; assumed 30
            ms torque lag. Gripper is prescribed. URDF friction/damping are
            generic, uncalibrated defaults. No identified motor transmission,
            backlash or payload. This is an illustrative engineering model.
          </p>
          {simulation && (
            <>
              <select
                aria-label="Follower controller playback"
                value={controller}
                onChange={(e) => setController(e.target.value)}
              >
                <option value="baseline">Baseline controller playback</option>
                <option value="improved">Comparison controller playback</option>
              </select>
              <table className="wb-table">
                <thead>
                  <tr>
                    <th>Measured on same reference</th>
                    <th>Baseline</th>
                    <th>Comparison</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["EE RMS", "ee_rms_m", 1000, "mm"],
                    ["EE maximum", "ee_max_m", 1000, "mm"],
                    [
                      "Limit violation samples",
                      "limit_violation_samples",
                      1,
                      "",
                    ],
                    ["Compile + run", "runtime_s", 1, "s"],
                  ].map(([label, key, scale, unit]) => (
                    <tr key={String(key)}>
                      <td>{label}</td>
                      {["baseline", "improved"].map((n) => (
                        <td key={n}>
                          {(
                            simulation.data.results[n].metrics[String(key)] *
                            Number(scale)
                          ).toFixed(3)}{" "}
                          {unit}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <details>
                <summary>Joint errors, delays and peak effort</summary>
                {["baseline", "improved"].map((n) => (
                  <pre key={n}>
                    {n +
                      ":\n" +
                      JSON.stringify(
                        simulation.data.results[n].metrics,
                        null,
                        2,
                      )}
                  </pre>
                ))}
              </details>
              <p className="wb-notice">{simulation.data.conclusion}</p>
              <p className="wb-footnote">
                Reference {simulation.data.trajectory?.slice(0, 8)} · model
                revision{" "}
                {simulation.data.model_revision?.slice(0, 8) ||
                  "generated baseline"}{" "}
                · controller revision{" "}
                {simulation.data.controller_revision?.slice(0, 8) || "default"}
              </p>
              <JointSignal
                result={simulation.data.results[controller]}
                index={Math.max(
                  0,
                  Math.min(5, config?.joint_ids.indexOf(context.selected) || 0),
                )}
                name={context.selected}
              />
              <Signal result={simulation.data.results[controller]} />
            </>
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
