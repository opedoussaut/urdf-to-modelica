import { useEffect, useMemo, useState } from "react";
import { Play, RotateCcw, GitPullRequest, Code2, Network, History, AlertTriangle, CheckCircle2 } from "lucide-react";
import TimeChart, { type Series } from "./TimeChart";
import { message, request, waitJob, type Context, type Doc } from "./studio";

const KEYS = ["kp", "kd", "actuatorTime", "feedforward"] as const;
type Key = (typeof KEYS)[number];
const LABEL: Record<Key, string> = {
  kp: "Proportional gain kp",
  kd: "Derivative gain kd",
  actuatorTime: "Actuator lag Ta",
  feedforward: "Gravity feed-forward ff",
};
const STEP: Record<Key, number> = { kp: 1, kd: 0.1, actuatorTime: 0.005, feedforward: 0.05 };
const C_CMD = "#0f172a",
  C_BASE = "#94a3b8",
  C_CAND = "#1d4ed8";

const clean = (s: string) => (/^-0(\.0+)?$/.test(s) ? s.slice(1) : s);
const mrad = (v?: number | null) => (v === null || v === undefined ? "—" : clean((v * 1000).toFixed(1)));
const num = (v?: number | null, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));

const METRICS: [string, string, (m: any) => string, string][] = [
  ["rms_error_rad", "RMS tracking error", (m) => mrad(m.rms_error_rad), "mrad"],
  ["max_abs_error_rad", "Max tracking error", (m) => mrad(m.max_abs_error_rad), "mrad"],
  ["peak_torque_Nm", "Peak torque", (m) => num(m.peak_torque_Nm), "N·m"],
  ["overshoot_percent", "Overshoot", (m) => num(m.overshoot_percent, 1), "%"],
  ["settling_time_2pct_s", "Settling (2 %)", (m) => (m.settling_time_2pct_s === null ? "not within run" : num(m.settling_time_2pct_s, 3)), "s"],
  ["steady_state_error_rad", "Steady-state error", (m) => mrad(m.steady_state_error_rad), "mrad"],
  ["saturated_fraction", "Torque saturated", (m) => num(m.saturated_fraction * 100, 1), "% of time"],
];

export default function SimLab({
  context,
  setContext,
  open,
}: {
  context: Context;
  setContext: (c: Partial<Context>) => void;
  open: (i: number) => void;
}) {
  const joint = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate"].includes(context.selected)
    ? context.selected
    : "shoulder";
  const [setup, setSetup] = useState<any>(),
    [params, setParams] = useState<Record<Key, number>>(),
    [input, setInput] = useState({ kind: "step", amplitude: 0.3, step_time: 0.5, ramp_time: 0.3, stop_time: 3, trajectory: "" }),
    [result, setResult] = useState<Doc>(),
    [runs, setRuns] = useState<any[]>([]),
    [state, setState] = useState<{ phase: "idle" | "running" | "done" | "error"; text?: string; started?: number }>({ phase: "idle" }),
    [tick, setTick] = useState(0),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [showSource, setShowSource] = useState(false);

  const load = () =>
    request("/lab/servo1d/setup?joint=" + joint + (context.model ? "&model=" + context.model : ""))
      .then((s) => {
        setSetup(s);
        setParams({ ...s.baseline });
        setError("");
      })
      .catch((e) => setError(message(e)));
  const loadRuns = () => request<any[]>("/lab/servo1d/runs").then(setRuns).catch(() => {});
  useEffect(() => {
    load();
    loadRuns();
  }, [joint, context.model, context.model_revision]);
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("run");
    if (id) openRun(id);
  }, []);
  useEffect(() => {
    if (state.phase !== "running") return;
    const t = setInterval(() => setTick((n) => n + 1), 500);
    return () => clearInterval(t);
  }, [state.phase]);

  const changed = setup && params ? KEYS.filter((k) => Math.abs(params[k] - setup.baseline[k]) > 1e-12) : [];
  const run = async (compare: boolean) => {
    if (!setup || !params) return;
    setState({ phase: "running", started: Date.now(), text: compare ? "Compiling and simulating baseline and candidate" : "Compiling and simulating baseline" });
    setError("");
    setNotice("");
    try {
      const body: any = {
        joint,
        model: context.model || undefined,
        input: { ...input, trajectory: input.kind === "trajectory" ? input.trajectory : undefined },
      };
      if (compare) body.candidate = params;
      const record = await waitJob(await request("/lab/servo1d/run", "POST", body));
      setResult(record);
      const failed = Object.entries(record.data.runs).filter(([, r]: any) => !r.ok);
      setState(failed.length ? { phase: "error", text: "OpenModelica reported an error" } : { phase: "done" });
      loadRuns();
    } catch (e) {
      setState({ phase: "error", text: message(e) });
    }
  };
  const openRun = (id: string) =>
    request<Doc>("/record/" + id)
      .then((r) => {
        setResult(r);
        setState({ phase: "done" });
        // Show the parameters that produced this saved run (candidate if any).
        const p = r.data.runs.candidate?.params || r.data.runs.baseline?.params;
        if (p) setParams({ ...p });
      })
      .catch((e) => setError(message(e)));
  const propose = async () => {
    if (!result || !context.model) return;
    try {
      const out = await request("/lab/servo1d/" + result.id + "/propose", "POST", { model: context.model });
      setContext({ model_revision: out.revision });
      setNotice(
        `Proposal revision ${out.revision.slice(0, 8)} created (not accepted). Validate it with OpenModelica and accept it explicitly in the Modelica editor or the Leader–Follower comparison.`,
      );
    } catch (e) {
      setError(message(e));
    }
  };

  const data = result?.data;
  const base = data?.runs?.baseline,
    cand = data?.runs?.candidate;
  const series = (key: string, scale = 1): Series[] => {
    if (!base?.ok) return [];
    const s: Series[] = [];
    if (key === "q") s.push({ name: "commanded", color: C_CMD, t: base.series.time, y: base.series.q_cmd.map((v: number) => v * scale), dash: "5 4", width: 1.6 });
    s.push({ name: cand ? "baseline" : "response", color: cand ? C_BASE : C_CAND, t: base.series.time, y: base.series[key].map((v: number) => v * scale) });
    if (cand?.ok) s.push({ name: "candidate", color: C_CAND, t: cand.series.time, y: cand.series[key].map((v: number) => v * scale) });
    return s;
  };
  const verdict = (k: string) => data?.comparison?.rows.find((r: any) => r.metric === k);
  const plant = setup?.plant;
  const elapsed = state.started ? ((Date.now() - state.started) / 1000).toFixed(0) : "0";
  void tick;

  return (
    <div className="lab">
      <header className="lab-head">
        <div>
          <span className="lab-eyebrow">STEP 4 · SIMULATE · MODELICA 1D · OPENMODELICA</span>
          <h1>Joint simulation</h1>
          <p>
            One follower joint as a single-degree-of-freedom servo: change a tunable parameter, run the real OpenModelica
            model and compare against the baseline on the identical command.
          </p>
        </div>
        <label className="lab-select">
          Joint
          <select value={joint} onChange={(e) => setContext({ selected: e.target.value, robot: "aloha_vx300s" })}>
            {(setup?.joints || ["shoulder"]).map((j: string) => (
              <option key={j}>{j}</option>
            ))}
          </select>
        </label>
      </header>
      {error && <div className="lab-alert error">{error}</div>}
      {notice && <div className="lab-alert info">{notice}</div>}

      <section className="lab-card lab-schematic" aria-label="Model architecture">
        <div className="lab-card-head">
          <h2>Model architecture · ViperX follower · {joint}</h2>
          <span className="lab-tag">MSL Mechanics.Rotational + Blocks</span>
        </div>
        <Schematic plant={plant} params={params} />
        {plant && (
          <p className="lab-footnote">
            Inertia and gravity torque are <b>derived</b> from the follower URDF inertials ({plant.links.length} bodies,{" "}
            {plant.moving_mass_kg} kg) with the outer joints at the ALOHA start pose; massless placeholders skipped:{" "}
            {plant.massless_placeholders.join(", ") || "none"}. Not modelled: {plant.evidence.not_modelled}.
          </p>
        )}
      </section>

      <div className="lab-grid">
        <section className="lab-card" aria-label="Parameters">
          <div className="lab-card-head">
            <h2>Parameters</h2>
            <button className="lab-ghost" disabled={!changed.length} onClick={() => setParams({ ...setup.baseline })}>
              <RotateCcw size={14} /> Reset to baseline
            </button>
          </div>
          <p className="lab-footnote">Baseline: {setup?.baseline_label || "loading…"}</p>
          {params &&
            KEYS.map((k) => {
              const [lo, hi] = setup.bounds[k];
              const sem = setup.semantics?.[k];
              return (
                <div key={k} className={"lab-param" + (changed.includes(k) ? " changed" : "")}>
                  <div className="lab-param-row">
                    <label htmlFor={"p-" + k}>{LABEL[k]}</label>
                    <span className="lab-badge assumed">assumed · tunable</span>
                  </div>
                  <div className="lab-param-row">
                    <input
                      id={"p-" + k}
                      type="range"
                      min={lo}
                      max={hi}
                      step={STEP[k]}
                      value={params[k]}
                      onChange={(e) => setParams({ ...params, [k]: +e.target.value })}
                    />
                    <input
                      className="lab-number"
                      type="number"
                      min={lo}
                      max={hi}
                      step={STEP[k]}
                      value={params[k]}
                      aria-label={LABEL[k] + " value"}
                      onChange={(e) => setParams({ ...params, [k]: +e.target.value })}
                    />
                    <span className="lab-unit">{setup.units[k]}</span>
                  </div>
                  <small>
                    baseline {setup.baseline[k]} · declared range [{lo}, {hi}] (ALOHA2.Control.ServoGains)
                    {sem?.applicable !== undefined && (
                      <> · knowledge graph: {sem.applicable ? "may be changed" : "blocked"} ({sem.evidence_status})</>
                    )}
                  </small>
                </div>
              );
            })}
          {plant && (
            <div className="lab-fixed">
              <h3>Plant (not editable here)</h3>
              <dl>
                <dt>Equivalent inertia J</dt>
                <dd>
                  {plant.inertia_kgm2} kg·m² <span className="lab-badge derived">derived</span>
                </dd>
                <dt>Gravity torque</dt>
                <dd>
                  {plant.gravity_amplitude_Nm} N·m · sin(q + {plant.gravity_phase_rad}) <span className="lab-badge derived">derived</span>
                </dd>
                <dt>Damping d · friction τc</dt>
                <dd>
                  {plant.damping_Nms_per_rad} N·m·s/rad · {plant.coulomb_friction_Nm} N·m <span className="lab-badge urdf">URDF generic</span>
                </dd>
                <dt>Torque limit</dt>
                <dd>
                  ±{plant.effort_limit_Nm} N·m <span className="lab-badge verified">URDF verified</span>
                </dd>
                <dt>Joint limits</dt>
                <dd>
                  [{plant.q_min.toFixed(3)}, {plant.q_max.toFixed(3)}] rad <span className="lab-badge verified">URDF verified</span>
                </dd>
              </dl>
            </div>
          )}
        </section>

        <section className="lab-card" aria-label="Experiment">
          <div className="lab-card-head">
            <h2>Experiment input</h2>
            <span className="lab-tag">same command for every run</span>
          </div>
          <div className="lab-seg" role="group" aria-label="Input type">
            {[
              ["step", "Step"],
              ["trajectory", "Recorded leader motion"],
            ].map(([k, l]) => (
              <button key={k} aria-pressed={input.kind === k} className={input.kind === k ? "on" : ""} onClick={() => setInput({ ...input, kind: k })}>
                {l}
              </button>
            ))}
          </div>
          {input.kind === "step" ? (
            <div className="lab-fields">
              {(
                [
                  ["amplitude", "Step amplitude", "rad", 0.05],
                  ["step_time", "Step time", "s", 0.1],
                  ["ramp_time", "Ramp (0 = ideal step)", "s", 0.05],
                  ["stop_time", "Stop time", "s", 0.5],
                ] as const
              ).map(([k, l, u, st]) => (
                <label key={k}>
                  {l}
                  <span>
                    <input type="number" step={st} value={(input as any)[k]} onChange={(e) => setInput({ ...input, [k]: +e.target.value })} />
                    {u}
                  </span>
                </label>
              ))}
              {plant && (
                <small className="lab-footnote">
                  From the start pose q₀ = {plant.q0.toFixed(3)} rad to {(plant.q0 + input.amplitude).toFixed(3)} rad (≈
                  {((input.amplitude * 180) / Math.PI).toFixed(1)}°); targets outside the URDF limits are rejected.
                </small>
              )}
            </div>
          ) : (
            <label className="lab-fields">
              Recording (mapped to follower joint space)
              <select value={input.trajectory} onChange={(e) => setInput({ ...input, trajectory: e.target.value })}>
                <option value="">Choose a saved recording…</option>
                {(setup?.trajectories || []).map((t: any) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {t.duration_s.toFixed(1)} s
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="lab-actions">
            <button className="lab-primary" disabled={!setup || state.phase === "running" || (input.kind === "trajectory" && !input.trajectory)} onClick={() => run(true)}>
              <Play size={15} /> Run &amp; compare to baseline
            </button>
            <button className="lab-ghost" disabled={!setup || state.phase === "running"} onClick={() => run(false)}>
              Run baseline only
            </button>
          </div>
          <div className={"lab-status " + state.phase} role="status">
            {state.phase === "idle" && "Ready. Each run compiles and simulates the Modelica model in a new isolated directory."}
            {state.phase === "running" && (
              <>
                <span className="lab-spinner" /> {state.text} in OpenModelica… {elapsed} s (typically 7–10 s; no cancel)
              </>
            )}
            {state.phase === "done" && data && (
              <>
                <CheckCircle2 size={15} /> {data.created === undefined ? "" : `Run ${result!.id.slice(0, 8)} · ${new Date(data.created).toLocaleString()}`}
              </>
            )}
            {state.phase === "error" && (
              <>
                <AlertTriangle size={15} /> {state.text}
              </>
            )}
          </div>
          {changed.length > 0 && (
            <p className="lab-footnote">
              Candidate changes: {changed.map((k) => `${k} ${setup.baseline[k]} → ${params![k]}`).join(", ")}
            </p>
          )}
          <details className="lab-history">
            <summary>
              <History size={14} /> Saved runs ({runs.length}) — archived results, labelled as such
            </summary>
            <ul>
              {runs.slice(0, 8).map((r) => (
                <li key={r.id}>
                  <button className="lab-link" onClick={() => openRun(r.id)}>
                    {new Date(r.created).toLocaleString()} · {r.name}
                  </button>
                  <small>{r.summary || (r.ok ? "baseline only" : "failed")}</small>
                </li>
              ))}
            </ul>
          </details>
        </section>
      </div>

      {data && (
        <section className="lab-card lab-results" aria-label="Results">
          <div className="lab-card-head">
            <h2>
              Results · {data.input.label}
              {result && state.phase === "done" && Date.now() - new Date(data.created).getTime() > 5 * 60 * 1000 && (
                <span className="lab-badge archived">archived run · {new Date(data.created).toLocaleString()}</span>
              )}
            </h2>
            <span className="lab-tag">OpenModelica · MAT result parsed</span>
          </div>
          {Object.entries(data.runs).map(([name, r]: any) =>
            r.ok ? null : (
              <div key={name} className="lab-alert error">
                <b>{name}: OpenModelica {r.stage} failed.</b>
                <pre>{r.diagnostic}</pre>
              </div>
            ),
          )}
          {base?.ok && (
            <>
              <div className="lab-kpis">
                {METRICS.map(([k, label, f, unit]) => {
                  const v = verdict(k);
                  return (
                    <div key={k} className={"lab-kpi " + (v?.verdict || "")}>
                      <span>{label}</span>
                      <b>
                        {f(cand?.ok ? cand.metrics : base.metrics)} <small>{unit}</small>
                      </b>
                      {cand?.ok && (
                        <em>
                          baseline {f(base.metrics)} · {v?.verdict === "n/a" ? "n/a" : v?.verdict}
                        </em>
                      )}
                    </div>
                  );
                })}
              </div>
              {data.comparison && <p className="lab-summary">{data.comparison.summary}</p>}
              <div className="lab-charts">
                <TimeChart title="Joint angle: commanded vs actual" unit="rad" series={series("q")} />
                <TimeChart title="Tracking error e = q_cmd − q" unit="mrad" series={series("e", 1000)} />
                <TimeChart
                  title="Applied actuator torque"
                  unit="N·m"
                  series={series("tau")}
                  bands={plant ? [{ y: plant.effort_limit_Nm, label: "+τmax (URDF)" }, { y: -plant.effort_limit_Nm, label: "−τmax" }].filter((b) => {
                    const all = [...(base.series.tau as number[]), ...((cand?.series?.tau as number[]) || [])];
                    return Math.abs(b.y) < Math.max(...all.map(Math.abs)) * 1.6;
                  }) : []}
                />
                <TimeChart title="Joint velocity" unit="rad/s" series={series("qd")} />
              </div>
              <div className="lab-provenance">
                <span>{base.omc_version}</span>
                <span>class ServoJoint1D · dassl · tol 1e-6 · 800 intervals</span>
                <span>run {result!.id.slice(0, 8)} · {data.run_directory}</span>
                <span>input sha256 {data.input_sha256.slice(0, 12)}…</span>
                <span>baseline source {base.source_sha256.slice(0, 12)}…{cand?.ok ? ` · candidate ${cand.source_sha256.slice(0, 12)}…` : ""}</span>
                <span>
                  compile {num(base.timing_s.timeCompile, 1)} s · simulate {num(base.timing_s.timeSimulation, 2)} s
                </span>
                <span>baseline: {data.baseline_label}</span>
              </div>
              <div className="lab-actions">
                <button className="lab-ghost" onClick={() => setShowSource(!showSource)}>
                  <Code2 size={14} /> {showSource ? "Hide" : "Inspect"} Modelica
                </button>
                <button className="lab-ghost" onClick={() => open(7)}>
                  <Network size={14} /> View semantic provenance
                </button>
                <button
                  className="lab-primary"
                  disabled={!cand?.ok || !context.model || !!data.proposal_revision}
                  title={!context.model ? "Open an editable model in the Modelica editor first" : ""}
                  onClick={propose}
                >
                  <GitPullRequest size={14} /> {data.proposal_revision ? `Proposed as ${data.proposal_revision.slice(0, 8)}` : "Propose revision (not accepted)"}
                </button>
              </div>
              {showSource && <pre className="lab-code">{(cand?.ok ? cand : base).source || "Source not stored for this archived run."}</pre>}
              <ul className="lab-limits">
                {data.limitations.map((l: string) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </div>
  );
}

function Schematic({ plant, params }: { plant?: any; params?: Record<Key, number> }) {
  const blocks = useMemo(
    () => [
      { x: 10, label: "Command", sub: "q_cmd(t), q̇_cmd(t)", kind: "input" },
      { x: 150, label: "PD + feed-forward", sub: params ? `kp ${params.kp} · kd ${params.kd} · ff ${params.feedforward}` : "", kind: "assumed" },
      { x: 300, label: "Saturation", sub: plant ? `±${plant.effort_limit_Nm} N·m` : "", kind: "verified" },
      { x: 430, label: "Actuator lag", sub: params ? `Ta ${params.actuatorTime} s` : "", kind: "assumed" },
      { x: 560, label: "Link inertia", sub: plant ? `J ${plant.inertia_kgm2} kg·m²` : "", kind: "derived" },
    ],
    [plant, params],
  );
  return (
    <svg className="lab-diagram" viewBox="0 0 700 150" role="img" aria-label="1D servo block diagram">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#64748b" />
        </marker>
      </defs>
      {blocks.map((b, i) => (
        <g key={b.label}>
          <rect x={b.x} y={30} width={120} height={52} rx={8} className={"blk " + b.kind} />
          <text x={b.x + 60} y={52} textAnchor="middle" className="blk-t">
            {b.label}
          </text>
          <text x={b.x + 60} y={70} textAnchor="middle" className="blk-s">
            {b.sub}
          </text>
          {i < blocks.length - 1 && <line x1={b.x + 120} y1={56} x2={blocks[i + 1].x} y2={56} stroke="#64748b" markerEnd="url(#arr)" />}
        </g>
      ))}
      <path d="M680,56 L692,56 L692,118 L210,118 L210,84" fill="none" stroke="#64748b" markerEnd="url(#arr)" strokeDasharray="4 3" />
      <text x={330} y={112} textAnchor="middle" className="blk-s">
        q, q̇ feedback
      </text>
      <text x={692} y={98} textAnchor="end" className="blk-s">
        {plant ? `load: ${plant.gravity_amplitude_Nm}·sin(q+φ) N·m, d ${plant.damping_Nms_per_rad}, τc ${plant.coulomb_friction_Nm}` : ""}
      </text>
      <g className="lab-legend-svg">
        {[
          ["verified", "URDF verified"],
          ["derived", "derived from URDF"],
          ["assumed", "assumed · tunable"],
        ].map(([k, l], i) => (
          <g key={k} transform={`translate(${12 + i * 150},140)`}>
            <rect width={10} height={10} y={-9} rx={2} className={"blk " + k} />
            <text x={16} y={0} className="blk-s" textAnchor="start">
              {l}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}
