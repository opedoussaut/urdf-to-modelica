import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, Play, BookOpen, Check, CircleSlash, Clock, Loader2, FileArchive, FileCode2, FileSearch, Move3d, Pause, Trophy, Upload, Wrench, X } from "lucide-react";
import { useAudience } from "../audience";
import { message, waitJob, type Doc } from "../studio";
import { baseOf, convert, keyLabel, MODE_ORDER, orderKeys, type LocalModel, type ModeId, type Report, type RunSummary } from "./api";
import type { Target } from "./SimpleApp";
import RobotView, { type Clash, type Hover, type Replay, type ReplayFrame } from "./RobotView";

type Source = {
  id: string;
  label: string;
  kind: string;
  links: number;
  joints: number;
  movable: number;
  mimic?: number;
  mass_kg: number;
  bytes: number;
  graph?: boolean;
  provenance: string;
  sha256: string;
  what?: string;
  sources?: string[];
  license?: string;
  repo?: string | null;
  default?: boolean;
  demo?: boolean;
};

const MODE_ICON: Record<ModeId, typeof Bot> = { llm: Bot, llm_rag: BookOpen, urdfmodelica: Wrench };
const MODE_NEEDS: Record<ModeId, string> = {
  llm: "Local AI model(s) chosen below · a few minutes per model",
  llm_rag: "Same local model(s) + keyword search in the Modelica Standard Library · a few minutes per model",
  urdfmodelica: "DLR URDFModelica converter (open source) · about 20 seconds",
};
const CRITERION_HELP: Record<string, string> = {
  produced: "Did the method give us a Modelica file at all?",
  loads: "OpenModelica reads the file: no syntax errors, no unknown building blocks.",
  checks: "OpenModelica checks the model is complete: as many equations as unknowns, every part connected.",
  simulates: "The model actually runs for 2 seconds (the arm moves under gravity or a test motion).",
  coverage: "Each part (link) and moving joint of the robot file can be found in the model by its name.",
  kinematics:
    "We move every joint through most of its range, compute from the robot file alone where each part must be, and compare with where the simulation put it (position and orientation). The first wrong joint on a chain is named as the suspect.",
  parameters: "Joint axes, part masses, centres of mass and inertias in the model are the ones written in the robot file (compared in each part's own frame).",
  dynamics:
    "For the same motion, the motor torque each joint needs in the model is compared with an independent physics engine (MuJoCo) reading the robot file. Friction and damping are left out on both sides.",
};

export default function Convert({ openUnderstand, learn }: { openUnderstand: (t: Target) => void; learn: () => void }) {
  const expert = useAudience() === "expert";
  const [sources, setSources] = useState<Source[]>([]),
    [source, setSource] = useState(""),
    [modes, setModes] = useState<ModeId[]>(["llm", "llm_rag", "urdfmodelica"]),
    [busy, setBusy] = useState(false),
    [started, setStarted] = useState(0),
    [now, setNow] = useState(Date.now()),
    [error, setError] = useState(""),
    [report, setReport] = useState<Report>(),
    [runs, setRuns] = useState<RunSummary[]>([]),
    [installed, setInstalled] = useState<LocalModel[]>([]),
    [models, setModels] = useState<string[]>([]);
  const file = useRef<HTMLInputElement>(null);
  const load = () => {
    convert("/sources")
      .then((r) => {
        setSources(r.sources);
        setSource((cur) => cur || r.sources.find((x: Source) => x.default)?.id || r.sources[0]?.id || "");
        setInstalled(r.models || []);
        setModels((cur) => (cur.length ? cur.filter((m) => r.models.some((x: LocalModel) => x.name === m)) : r.models.filter((x: LocalModel) => x.default).map((x: LocalModel) => x.name)));
      })
      .catch((e) => setError(message(e)));
    convert<RunSummary[]>("/runs").then(setRuns).catch(() => {});
  };
  useEffect(load, []);
  // live progress: polled while a comparison runs (also one started before this page was opened)
  const [live, setLive] = useState<Live>();
  const [polledAt, setPolledAt] = useState(Date.now());
  useEffect(() => {
    let stop = false;
    const tick = () =>
      convert<Live>("/active")
        .then((s) => {
          if (stop) return;
          setLive(s);
          setPolledAt(Date.now());
        })
        .catch(() => {});
    tick();
    const t = setInterval(() => (busy || live?.running) && tick(), 1000);
    return () => {
      stop = true;
      clearInterval(t);
    };
  }, [busy, live?.running]);
  useEffect(() => {
    if (!busy && !live?.running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [busy, live?.running]);

  const upload = async (f?: File) => {
    if (!f) return;
    setError("");
    try {
      const meta = await convert("/upload", "POST", { filename: f.name, content: await f.text() });
      load();
      setSource(meta.id);
    } catch (e) {
      setError(message(e));
    } finally {
      if (file.current) file.current.value = "";
    }
  };
  const run = async () => {
    setBusy(true);
    setError("");
    setReport(undefined);
    setStarted(Date.now());
    try {
      const job = await convert<Doc>("/run", "POST", { source, modes, models });
      setReport(await waitJob(job));
      load();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const openRun = async (id: string) => {
    setError("");
    try {
      setReport(await convert<Report>("/runs/" + id));
      setTimeout(() => document.querySelector(".sx-results")?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e) {
      setError(message(e));
    }
  };
  const chosen = sources.find((s) => s.id === source);
  const pinned = sources.filter((s) => s.kind === "pinned"),
    uploads = sources.filter((s) => s.kind !== "pinned");
  const elapsed = Math.round((now - started) / 1000);

  return (
    <div className="lab sx-page">
      <div className="lab-plain">
        <b>IN PLAIN WORDS</b> A robot comes with a description file (URDF): its parts, joints, sizes and masses. To simulate it, that file must become a
        physics model (Modelica). Here three methods do the conversion, and the studio measures which result is best, with real OpenModelica runs.
      </div>
      <span className="lab-eyebrow">CONVERT &amp; COMPARE</span>
      <h1>Which method builds the best physics model?</h1>
      <p className="sx-lead">
        Pick a robot, run the three methods side by side, and read the score card. Nothing is accepted automatically: you decide what to keep.{" "}
        <button className="sx-link" onClick={learn}>
          New to URDF or Modelica? Read the Atlas
        </button>
      </p>

      <section className="sx-step">
        <h2>
          <span className="sx-n">1</span> Choose a robot
        </h2>
        <p className="sx-muted sx-intro">
          Five real robots described by public files from their makers. The SO-101 is small enough for a complete comparison in a few minutes. What you see is drawn from the very file that will be converted: every part, every
          joint, where it sits and how it turns. That is what the physics model has to reproduce.
        </p>
        <div className="sx-robots">
          {pinned.map((s) => (
            <button key={s.id} className={"sx-source sx-robot" + (s.id === source ? " on" : "")} onClick={() => setSource(s.id)} disabled={busy}>
              <RobotView source={s.id} lod="low" autoRotate height={170} />
              {s.demo && <span className="sx-demo-tag">Quick demo · a few minutes</span>}
              <b>{s.label}</b>
              <small>{s.what}</small>
              <small>
                {s.links} parts · {s.movable} moving joints · {s.mass_kg} kg
              </small>
              <small className="sx-tag">
                {s.license} · {s.graph ? "knowledge graph available" : "not yet in the knowledge graph"}
              </small>
              {expert && <code>{s.sha256.slice(0, 16)}…</code>}
            </button>
          ))}
        </div>
        {chosen && <RobotStage source={chosen} />}
      </section>

      <section className="sx-step">
        <h2>
          <span className="sx-n">
            <Upload size={14} />
          </span>{" "}
          Or upload your own URDF
        </h2>
        <p className="sx-muted sx-intro">
          Any robot description file (.urdf, up to 300 kB). Meshes are not needed: the studio draws it as a skeleton of joints and bars, and the
          conversion works from the numbers in the file.
        </p>
        <div className="sx-sources">
          {uploads.map((s) => (
            <button key={s.id} className={"sx-source" + (s.id === source ? " on" : "")} onClick={() => setSource(s.id)} disabled={busy}>
              <b>{s.label}</b>
              <small>
                {s.links} parts · {s.movable} moving joints · {s.mass_kg} kg
              </small>
              <small className="sx-tag">Your upload · no knowledge graph</small>
              {expert && <code>{s.sha256.slice(0, 16)}…</code>}
            </button>
          ))}
          <button className="sx-source sx-upload" onClick={() => file.current?.click()} disabled={busy}>
            <Upload size={18} />
            <b>Upload a URDF</b>
            <small>Plain .urdf file, up to 300 kB. Expand xacro files first.</small>
          </button>
          <input ref={file} type="file" accept=".urdf" hidden onChange={(e) => upload(e.target.files?.[0])} />
        </div>
      </section>

      <section className="sx-step">
        <h2>
          <span className="sx-n">2</span> Choose the methods
        </h2>
        <div className="sx-modes">
          {MODE_ORDER.map((m, k) => {
            const Icon = MODE_ICON[m];
            const on = modes.includes(m);
            return (
              <label key={m} className={"sx-mode" + (on ? " on" : "")}>
                <input type="checkbox" checked={on} disabled={busy} onChange={() => setModes(on ? modes.filter((x) => x !== m) : [...modes, m])} />
                <span className="sx-mode-n">Method {k + 1}</span>
                <Icon size={22} />
                <b>{m === "llm" ? "AI only" : m === "llm_rag" ? "AI + Modelica library search" : "URDFModelica converter"}</b>
                <p>
                  {m === "llm"
                    ? "The local AI reads the robot file and writes the model on its own."
                    : m === "llm_rag"
                      ? "The same AI, but first handed the matching building blocks found in the Modelica Standard Library."
                      : "A published, rule-based converter from DLR translates the file. No AI involved."}
                </p>
                <small>{MODE_NEEDS[m]}</small>
              </label>
            );
          })}
        </div>
        {modes.some((m) => m !== "urdfmodelica") && (
          <div className="sx-models">
            <b>AI models</b>
            <small>Each AI method runs once with every model you tick. All run locally through Ollama.</small>
            <div>
              {installed.map((m) => {
                const on = models.includes(m.name);
                return (
                  <label key={m.name} className={"sx-model" + (on ? " on" : "")}>
                    <input type="checkbox" checked={on} disabled={busy} onChange={() => setModels(on ? models.filter((x) => x !== m.name) : [...models, m.name])} />
                    <span>
                      <b>{m.name}</b>
                      <small>
                        {m.parameters ? m.parameters + " parameters · " : ""}
                        {m.size_gb} GB{m.default ? " · studio default" : ""}
                      </small>
                    </span>
                  </label>
                );
              })}
              {installed.length === 0 && <span className="sx-muted">No local model found: is Ollama running?</span>}
            </div>
          </div>
        )}
        <p className="sx-note">
          Fair comparison: both AI methods get the same robot file, the same model and settings, and the same two chances to repair their file using
          OpenModelica's error messages. They never see the expected answer.
        </p>
        <button className="lab-primary sx-run" disabled={busy || !!live?.running || !modes.length || !chosen || (modes.some((m) => m !== "urdfmodelica") && !models.length)} onClick={run}>
          {busy ? (
            <>
              <Clock size={16} /> Running… {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
            </>
          ) : live?.running ? (
            <>
              <Clock size={16} /> A comparison on {live.source} is running: wait for it to finish
            </>
          ) : (
            <>Run the comparison on {chosen ? chosen.label : "…"}</>
          )}
        </button>
        {(busy || live?.running) && live && <LiveProgress live={live} polledAt={polledAt} now={now} />}
        {busy && <p className="sx-note">The converter takes seconds; each AI method can take several minutes on this laptop (it writes the whole file, then OpenModelica checks it). You can leave this page open.</p>}
        {error && <p className="lab-error">{error}</p>}
      </section>

      {report && <Results report={report} expert={expert} openUnderstand={openUnderstand} />}

      {runs.length > 0 && (
        <section className="sx-step">
          <h2>Earlier comparisons</h2>
          <p className="sx-note sx-export">
            All scores: <a href="/api/convert/scores?table=conversions&format=csv">download CSV</a> · <a href="/api/convert/scores?table=conversions">JSON</a>
          </p>
          <div className="sx-runs">
            {runs.slice(0, 12).map((r) => (
              <button key={r.id} onClick={() => openRun(r.id)} className={report?.id === r.id ? "on" : ""}>
                <b>{r.source}</b>
                <small>
                  {new Date(r.started).toLocaleString()} · {r.finished ? "highest: " + (r.ranking?.[0] ? keyLabel(r.ranking[0]) : "-") : "unfinished"}
                </small>
                {r.ranking?.[0] && r.modes[r.ranking[0]] && (
                  <span className={"sx-pill " + tone(Math.round((r.modes[r.ranking[0]].passed * 100) / 8))}>
                    {Math.round((r.modes[r.ranking[0]].passed * 100) / 8)} %
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

type LiveCheck = { id: string; state: "pass" | "fail" | "running" | "pending" | "skipped"; detail?: string | null };
type LiveMode = {
  status: "waiting" | "running" | "done" | "failed";
  started?: number;
  finished?: number;
  phase?: string | null;
  phase_started?: number;
  attempt?: number;
  attempts?: number;
  passed?: number;
  checks?: LiveCheck[];
  activity?: string | null;
  tokens?: number;
  chars?: number;
  max_tokens?: number;
};

/** Overall completion: share of the 8 checks passed. Colour follows the number, never the rank. */
export const completion = (s: { passed?: number; criteria?: unknown[] }) => Math.round((100 * (s.passed || 0)) / (s.criteria?.length || 8));
export const tone = (pct: number) => (pct >= 100 ? "good" : pct >= 50 ? "mid" : "bad");
const SHORT: Record<string, string> = {
  produced: "File produced",
  loads: "Readable",
  checks: "Complete",
  simulates: "Runs",
  coverage: "All parts present",
  kinematics: "Geometry in motion",
  parameters: "Axes, masses, inertias",
  dynamics: "Torques vs MuJoCo",
};
type Live = { id?: string; source?: string; running: boolean; started?: number; now?: number; modes?: Record<string, LiveMode> };

// Typical durations on this laptop (seconds), used only to move the bar inside a phase; phases and times are exact.
const TYPICAL = { converting: 3, checking: 25, writing_first: 220, writing_repair: 90 };
const PHASE: Record<string, string> = { converting: "Converter translating the file", checking: "OpenModelica checking the model", writing: "AI writing the file" };

function fmt(sec: number) {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function LiveProgress({ live, polledAt, now }: { live: Live; polledAt: number; now: number }) {
  const serverNow = (live.now || 0) + (now - polledAt) / 1000;
  return (
    <div className="sx-live" aria-live="polite">
      {orderKeys(Object.keys(live.modes || {})).map((m) => {
        const s = live.modes![m];
        const elapsed = s.started ? (s.finished || serverNow) - s.started : 0;
        const inPhase = s.phase_started ? serverNow - s.phase_started : 0;
        let pct = 0;
        if (s.status === "done" || s.status === "failed") pct = 100;
        else if (s.status === "running") {
          const frac = (e: number, typ: number) => Math.min(e / typ, 0.95);
          if (baseOf(m) === "urdfmodelica") pct = s.phase === "converting" ? 10 * frac(inPhase, TYPICAL.converting) : 10 + 90 * frac(inPhase, TYPICAL.checking);
          else {
            const k = s.attempt || 1,
              n = s.attempts || 3;
            const typ = k === 1 ? TYPICAL.writing_first : TYPICAL.writing_repair;
            const w = s.phase === "checking" ? 0.85 + 0.15 * frac(inPhase, TYPICAL.checking) : 0.85 * frac(inPhase, typ);
            pct = (100 * (k - 1 + w)) / n;
          }
        }
        return (
          <div key={m} className={"sx-live-row " + s.status}>
            <b>{keyLabel(m)}</b>
            <div className="sx-bar" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
              <i style={{ width: pct + "%" }} />
            </div>
            <span className="sx-live-time">{s.status === "waiting" ? "waiting" : fmt(elapsed)}</span>
            <small>
              {s.status === "waiting" && "Starts when the previous method finishes"}
              {s.status === "running" &&
                (PHASE[s.phase || ""] || s.phase) +
                  (baseOf(m) !== "urdfmodelica" && s.attempt ? ` · attempt ${s.attempt} of ${s.attempts} (stops early once the model runs)` : "") +
                  ` · ${fmt(inPhase)} in this step`}
              {s.status === "running" && s.phase === "writing" && s.tokens != null &&
                ` · ${s.tokens.toLocaleString()} tokens written so far (limit ${(s.max_tokens || 0).toLocaleString()})`}
              {s.status === "done" && `Finished · ${s.passed} of 8 checks passed (${Math.round(((s.passed || 0) * 100) / 8)} %)`}
              {s.status === "failed" && "Finished · no usable file"}
            </small>
            {s.checks && s.status !== "waiting" && (
              <div className="sx-live-checks">
                {s.checks.map((c) => (
                  <span key={c.id} className={"sx-lc " + c.state} title={c.detail || undefined}>
                    {c.state === "pass" && <Check size={13} />}
                    {c.state === "fail" && <X size={13} />}
                    {c.state === "running" && <Loader2 size={13} className="sx-spin" />}
                    {c.state === "skipped" && <CircleSlash size={12} />}
                    {c.state === "pending" && <i className="sx-lc-dot" />}
                    {SHORT[c.id] || c.id}
                  </span>
                ))}
                {s.status === "running" && s.activity && <em>{s.activity}</em>}
              </div>
            )}
            {baseOf(m) !== "urdfmodelica" && s.status !== "waiting" && <LiveText mode={m} active={s.status === "running"} />}
          </div>
        );
      })}
      <small className="sx-muted">
        Times and checks are live. Inside a step the bar is an estimate: the local AI does not report how far it has written. An AI method is
        tested after each attempt, so its checks start again when it repairs its file.
      </small>
    </div>
  );
}


function Mark({ ok, na }: { ok: boolean; na?: boolean }) {
  if (na) return <CircleSlash size={16} className="sx-na" aria-label="not reached" />;
  return ok ? <Check size={17} className="sx-ok" aria-label="yes" /> : <X size={17} className="sx-ko" aria-label="no" />;
}

function Results({ report, expert, openUnderstand }: { report: Report; expert: boolean; openUnderstand: (t: Target) => void }) {
  const order = orderKeys(Object.keys(report.modes));
  const LABEL = Object.fromEntries(order.map((m) => [m, keyLabel(m, report.modes[m])]));
  const best = report.ranking?.[0];
  const tiedWith = (m: string) => (report.ties || []).filter((t) => t.includes(m)).map((t) => (t[0] === m ? t[1] : t[0]));
  const bestTie = best ? tiedWith(best) : [];
  const bestRes = best ? report.modes[best] : undefined;
  const ids = Object.keys(report.criteria);
  const [watch, setWatch] = useState<string | null>(null);
  useEffect(() => setWatch(null), [report.id]);
  return (
    <section className="sx-step sx-results">
      <h2>
        <span className="sx-n">3</span> Results · {report.source.label}
      </h2>
      {bestRes && (
        <div className={"sx-winner " + tone(completion(bestRes.score))}>
          <div className="sx-pct">{completion(bestRes.score)} %</div>
          <div>
            <b>
              {completion(bestRes.score) >= 100 ? <Trophy size={17} /> : <AlertTriangle size={17} />}{" "}
              {bestTie.length
                ? `Tied highest score: ${[best!, ...bestTie].map((m) => LABEL[m]).join(" and ")}`
                : completion(bestRes.score) >= 100
                  ? `Passes every check: ${LABEL[best!]}`
                  : `Highest score of this run: ${LABEL[best!]}`}
            </b>
            <p>{bestRes.verdict}</p>
            {bestRes.score.passed < bestRes.score.criteria.length && (
              <small>
                Highest is not the same as good: it passes {bestRes.score.passed} of the {bestRes.score.criteria.length} checks and fails{" "}
                {bestRes.score.criteria.length - bestRes.score.passed}. Colours follow the percentage: red below 50 %, amber from 50 %, green only at 100 %.
              </small>
            )}
          </div>
        </div>
      )}
      <div className="sx-table-wrap">
        <table className="sx-table">
          <thead>
            <tr>
              <th>Check</th>
              {order.map((m) => (
                <th key={m} className={m === best ? "best" : ""}>
                  <span className={"sx-pill " + tone(completion(report.modes[m].score))}>{completion(report.modes[m].score)} %</span> {LABEL[m]}
                  {m === best && <span className="sx-best">{bestTie.length ? "tied" : "best"}</span>}
                  {m !== best && tiedWith(m).length > 0 && !tiedWith(m).includes(best!) && <span className="sx-best sx-tied">tied</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ids.map((id, row) => (
              <tr key={id}>
                <td>
                  <b>{report.criteria[id]}</b>
                  <small>{CRITERION_HELP[id]}</small>
                </td>
                {order.map((m) => {
                  const s = report.modes[m].score;
                  const c = s.criteria.find((x) => x.id === id);
                  const reached = s.criteria.slice(0, row).every((x, i) => i > 3 || x.ok) || row <= 0;
                  return (
                    <td key={m}>
                      <Mark ok={!!c?.ok} na={!c?.ok && !reached} />
                      {c?.detail && (expert || ["coverage", "kinematics"].includes(id)) && <small>{c.detail}</small>}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="sx-cost">
              <td>
                <b>Effort</b>
                <small>Time on this computer, AI calls, automatic repair rounds.</small>
              </td>
              {order.map((m) => {
                const r = report.modes[m];
                return (
                  <td key={m}>
                    <small>
                      {r.wall_seconds != null ? `${Math.round(r.wall_seconds)} s` : "-"} · {r.llm_calls ?? 0} AI call{r.llm_calls === 1 ? "" : "s"} · {r.repair_attempts ?? 0} repair{r.repair_attempts === 1 ? "" : "s"}
                    </small>
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="sx-cards">
        {order.map((m) => {
          const r = report.modes[m];
          return (
            <div key={m} className={"sx-card " + tone(completion(r.score))}>
              <b>
                <span className={"sx-pill " + tone(completion(r.score))}>{completion(r.score)} %</span> {LABEL[m]}
              </b>
              <p>{r.verdict}</p>
              {r.error && <p className="lab-error">{r.error}</p>}
              {expert && r.retrieved && r.retrieved.length > 0 && (
                <details>
                  <summary>Library classes given to the AI ({r.retrieved.length})</summary>
                  <ul>
                    {r.retrieved.map((x) => (
                      <li key={x.class}>
                        <code>{x.class}</code>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {expert && (r.score.check_messages || r.score.load_messages) && !r.score.simulates && (
                <details>
                  <summary>OpenModelica messages</summary>
                  <pre>{(r.score.check_messages || r.score.load_messages || "").slice(-1500)}</pre>
                </details>
              )}
              {r.score.simulates && (
                <button className={"lab-ghost" + (watch === m ? " on" : "")} onClick={() => setWatch(watch === m ? null : m)}>
                  <Play size={15} /> {watch === m ? "Hide the simulation" : "Watch the simulation"}
                </button>
              )}
              {r.main_file ? (
                <>
                <button className="lab-ghost" onClick={() => openUnderstand({ kind: "conversion", run: report.id, mode: m })}>
                  <FileSearch size={15} /> Review this file
                </button>
                <a className="sx-btn" href={`/api/convert/download?kind=conversion&run=${report.id}&mode=${encodeURIComponent(m)}&what=package`} download>
                  <FileArchive size={14} /> Download (.zip for OMEdit / Dymola)
                </a>
                </>
              ) : (
                <small className="sx-muted">
                  <FileCode2 size={13} /> No file to open
                </small>
              )}
            </div>
          );
        })}
      </div>
      {watch && report.modes[watch] && (
        <ReplayPanel key={report.id + watch} run={report.id} mode={watch} label={LABEL[watch]} source={report.source.id} />
      )}
      <div className="sx-proves">
        <div>
          <b>What these checks show</b>
          <p>That a model can be read, is complete, runs, contains every part, and puts each part where the robot file says, with the right axes and masses.</p>
        </div>
        <div>
          <b>What they do not show</b>
          <p>
            That the model behaves like the real robot: motors, friction and controllers are not part of the robot file, and nothing here was measured on hardware. A
            model that runs is a starting point, not a validated twin.
          </p>
        </div>
      </div>
    </section>
  );
}

/** Large interactive view of the chosen robot: orbit, zoom, sweep the joints, hover a part for its name and mass. */
function RobotStage({ source }: { source: Source }) {
  const [moving, setMoving] = useState(false),
    [showCom, setShowCom] = useState(false),
    [speed, setSpeed] = useState(0.25),
    [mode, setMode] = useState<"all" | "one">("all"),
    [clashOn, setClashOn] = useState(true),
    [clash, setClash] = useState<Clash>({ now: [], seen: [] }),
    [active, setActive] = useState<string | null>(null),
    [hover, setHover] = useState<Hover>(null),
    [meshInfo, setMeshInfo] = useState("");
  useEffect(() => {
    setMoving(false);
    setHover(null);
    setClash({ now: [], seen: [] });
    setMeshInfo("");
  }, [source.id]);
  return (
    <div className="sx-stage">
      <div className="sx-stage-view">
        <RobotView
          source={source.id}
          interactive
          moving={moving}
          showCom={showCom}
          speed={speed}
          mode={mode}
          clashes={clashOn}
          onClash={setClash}
          onActiveJoint={setActive}
          height={420}
          onHover={setHover}
          onInfo={(r, l) =>
            setMeshInfo(
              l.total
                ? `${l.meshes}/${l.total} part shapes loaded from the maker's files`
                : Object.values(r.links).some((k) => k.visuals.some((v) => v.shape))
                  ? "Simple shapes (boxes) written in the robot file itself"
                  : "No part shapes in this file: skeleton view",
            )
          }
        />
        {moving && (active || (clashOn && clash.now.length > 0)) && (
          <div className="sx-stage-live">
            {active && (
              <span>
                Moving now: <b>{active}</b>
              </span>
            )}
            {clashOn && clash.now.length > 0 && <span className="sx-clash-now">Passing through each other: {clash.now.join(", ")}</span>}
          </div>
        )}
        <div className="sx-stage-hover">
          {hover ? (
            <>
              <b>{hover.link}</b>
              <span>{hover.mass != null ? `${hover.mass.toPrecision(3)} kg` : "no mass in the file"}</span>
              {hover.shapeless && <span>no shape in the file: a sensor (IMU = motion sensor, camera, lidar) or a reference point</span>}
              {hover.joint && (
                <span>
                  moved by joint <b>{hover.joint}</b> ({hover.jointType})
                </span>
              )}
            </>
          ) : (
            <span>Point at a part to see its name, mass and joint · drag to turn · scroll to zoom</span>
          )}
        </div>
      </div>
      <div className="sx-stage-side">
        <h3>{source.label}</h3>
        {source.what && <p>{source.what}</p>}
        <button className={"btn" + (moving ? "" : " primary")} onClick={() => setMoving((m) => !m)}>
          {moving ? <Pause size={15} /> : <Move3d size={15} />} {moving ? "Stop" : "Move the joints"}
        </button>
        <div className="sx-speed" role="group" aria-label="Motion speed">
          <span>Speed</span>
          {[
            [0.25, "¼ slow motion"],
            [0.5, "½"],
            [1, "1× real test"],
          ].map(([v, l]) => (
            <button key={v} className={speed === v ? "on" : ""} onClick={() => setSpeed(v as number)}>
              {l}
            </button>
          ))}
        </div>
        <div className="sx-speed" role="group" aria-label="Motion">
          <span>Motion</span>
          <button className={mode === "all" ? "on" : ""} onClick={() => setMode("all")}>
            All joints together (the test)
          </button>
          <button className={mode === "one" ? "on" : ""} onClick={() => setMode("one")}>
            One joint at a time
          </button>
        </div>
        <label className="sx-check">
          <input type="checkbox" checked={clashOn} onChange={(e) => setClashOn(e.target.checked)} /> Show parts passing through each other (red)
        </label>
        {clashOn && clash.seen.length > 0 && (
          <small className="sx-clash">
            <b>
              {clash.seen.length} pair{clash.seen.length > 1 ? "s" : ""} of parts passed through each other since the motion started
            </b>
            {": "}
            {clash.seen.slice(0, 8).join(", ")}
            {clash.seen.length > 8 ? ", …" : ""}. The robot file limits each joint on its own; nothing in it stops one part from
            reaching another. The converted models and the MuJoCo reference have no contacts either, so the comparison stays fair,
            but this motion is a consistency test, not one the real robot could perform.
          </small>
        )}
        <label className="sx-check">
          <input type="checkbox" checked={showCom} onChange={(e) => setShowCom(e.target.checked)} /> Show the centre of mass
        </label>
        {showCom && (
          <small className="sx-muted">
            <span className="sx-com-dot" /> The point where the robot's whole weight acts, computed from each part's mass and centre of mass written in
            the file. The dashed line drops it to the lowest point: a standing robot stays balanced while this line falls between its feet.
          </small>
        )}
        <small className="sx-muted">
          Each joint swings through most of its range, as written in the file. At 1× this is exactly the motion used later to test the converted models (geometry and torque checks); slow motion makes it easier to follow.
        </small>
        <dl>
          <dt>Parts · moving joints</dt>
          <dd>
            {source.links} · {source.movable}
            {source.mimic ? ` (${source.mimic} copy another joint)` : ""}
          </dd>
          <dt>Total mass in the file</dt>
          <dd>{source.mass_kg} kg</dd>
          {source.sources && (
            <>
              <dt>Sources</dt>
              <dd>
                <ul>
                  {source.sources.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </dd>
            </>
          )}
          <dt>{source.license ? "Licence · pinned version" : "Origin"}</dt>
          <dd>
            {source.license && source.license + " · "}
            {source.repo ? (
              <a href={source.repo} target="_blank" rel="noreferrer">
                {source.provenance}
              </a>
            ) : (
              source.provenance
            )}
          </dd>
        </dl>
        {meshInfo && <small className="sx-muted">{meshInfo}</small>}
      </div>
    </div>
  );
}

/** The Modelica file an AI method is writing, streamed from the local model (toggle; polled while open). */
function LiveText({ mode, active }: { mode: string; active: boolean }) {
  const [open, setOpen] = useState(false),
    [text, setText] = useState(""),
    [unavailable, setUnavailable] = useState(false),
    [follow, setFollow] = useState(true);
  const box = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (!open) return;
    let stop = false;
    const tick = () =>
      convert<{ text: string }>("/active/text?mode=" + encodeURIComponent(mode))
        .then((r) => {
          if (stop) return;
          setText(r.text);
          setUnavailable(false);
        })
        .catch(() => !stop && setUnavailable(true));
    tick();
    const t = active ? setInterval(tick, 1500) : undefined;
    return () => {
      stop = true;
      if (t) clearInterval(t);
    };
  }, [open, mode, active]);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [text, follow]);
  return (
    <div className="sx-livetext">
      <button className="sx-link" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "Show"} what the AI is writing
      </button>
      {open && (
        <>
          <pre
            ref={box}
            onScroll={(e) => {
              const el = e.currentTarget;
              setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
            }}
          >
            {text ||
              (unavailable
                ? "The live text is not available for this run (it was started before the studio was updated). The AI is still working: its result appears when it finishes."
                : "Waiting for the first words from the local model…")}
            {active && <span className="sx-caret" />}
          </pre>
          <small className="sx-muted">
            Raw output of the local model, word by word, for the current attempt. It is not checked yet: OpenModelica tests it once the AI has
            finished.
          </small>
        </>
      )}
    </div>
  );
}

/** Replay of the simulation OpenModelica ran while scoring: solid = the converted model, faint = the robot file. */
function ReplayPanel({ run, mode, label, source }: { run: string; mode: string; label: string; source: string }) {
  const [data, setData] = useState<Replay | null>(null),
    [error, setError] = useState(""),
    [playing, setPlaying] = useState(true),
    [speed, setSpeed] = useState(0.5),
    [ghost, setGhost] = useState(true),
    [frame, setFrame] = useState<ReplayFrame | null>(null),
    [seek, setSeek] = useState<{ t: number } | null>(null);
  useEffect(() => {
    convert<Replay>(`/runs/${run}/replay?mode=${encodeURIComponent(mode)}`)
      .then(setData)
      .catch((e) => setError(message(e)));
  }, [run, mode]);
  const duration = data ? data.times[data.times.length - 1] : 0;
  return (
    <div className="sx-replay">
      <div className="sx-replay-head">
        <b>Simulation of {label}</b>
        <small className="sx-muted">
          {data ? `${data.motion} · ${duration.toFixed(1)} s computed by OpenModelica (${data.result_file})` : "Loading the stored result…"}
        </small>
      </div>
      {error && <p className="lab-error">{error}</p>}
      {data && (
        <div className="sx-stage">
          <div className="sx-stage-view">
            <RobotView source={source} interactive moving={playing} speed={speed} replay={data} ghost={ghost} seek={seek} onReplayFrame={setFrame} height={420} />
            {frame && (
              <div className="sx-stage-live">
                <span>t = {frame.t.toFixed(2)} s</span>
                {frame.off > 0 ? (
                  <span className="sx-clash-now">
                    {frame.off} part{frame.off > 1 ? "s" : ""} away from the robot file · largest gap {frame.worst!.mm.toFixed(1)} mm ({frame.worst!.link})
                  </span>
                ) : (
                  <span>Every part where the robot file says (within {data.tolerance_mm} mm)</span>
                )}
              </div>
            )}
          </div>
          <div className="sx-stage-side">
            <button className={"btn" + (playing ? "" : " primary")} onClick={() => setPlaying((p) => !p)}>
              {playing ? <Pause size={15} /> : <Play size={15} />} {playing ? "Pause" : "Play"}
            </button>
            <input
              type="range"
              min={0}
              max={duration}
              step={0.01}
              value={frame?.t ?? 0}
              onChange={(e) => {
                setPlaying(false);
                setSeek({ t: Number(e.target.value) });
              }}
              aria-label="Time in the simulation"
            />
            <div className="sx-speed" role="group" aria-label="Replay speed">
              <span>Speed</span>
              {[
                [0.25, "¼"],
                [0.5, "½"],
                [1, "1× real time"],
              ].map(([v, l]) => (
                <button key={v} className={speed === v ? "on" : ""} onClick={() => setSpeed(v as number)}>
                  {l}
                </button>
              ))}
            </div>
            <label className="sx-check">
              <input type="checkbox" checked={ghost} onChange={(e) => setGhost(e.target.checked)} /> Show where the robot file puts each part (grey ghost)
            </label>
            <small className="sx-muted">
              Solid parts are placed exactly where OpenModelica computed them while scoring this file; nothing is re-simulated or smoothed. The grey
              ghost is the robot file at the same joint angles. A part turns red when it is more than {data.tolerance_mm} mm from its ghost: that
              is the geometry check, frame by frame.
            </small>
            {data.missing_links.length > 0 && (
              <small className="sx-clash">
                <b>Not in the model:</b> {data.missing_links.join(", ")}. These parts of the robot file have no counterpart in the converted model, so
                only their ghost is drawn.
              </small>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
