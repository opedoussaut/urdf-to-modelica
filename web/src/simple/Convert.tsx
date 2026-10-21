import { useEffect, useRef, useState } from "react";
import { Bot, BookOpen, Check, CircleSlash, Clock, FileArchive, FileCode2, FileSearch, Trophy, Upload, Wrench, X } from "lucide-react";
import { useAudience } from "../audience";
import { message, waitJob, type Doc } from "../studio";
import { baseOf, convert, keyLabel, MODE_ORDER, orderKeys, type LocalModel, type ModeId, type Report, type RunSummary } from "./api";
import type { Target } from "./SimpleApp";

type Source = { id: string; label: string; kind: string; links: number; joints: number; movable: number; mass_kg: number; bytes: number; graph?: boolean; provenance: string; sha256: string };

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
    [source, setSource] = useState("aloha_wx250s"),
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
          <span className="sx-n">1</span> Choose the robot
        </h2>
        <div className="sx-sources">
          {sources.map((s) => (
            <button key={s.id} className={"sx-source" + (s.id === source ? " on" : "")} onClick={() => setSource(s.id)} disabled={busy}>
              <b>{s.label}</b>
              <small>
                {s.links} parts · {s.movable} moving joints · {s.mass_kg} kg
              </small>
              <small className="sx-tag">{s.kind === "pinned" ? "Pinned public file · knowledge graph available" : "Your upload · no knowledge graph yet"}</small>
              {expert && <code>{s.sha256.slice(0, 16)}…</code>}
            </button>
          ))}
          <button className="sx-source sx-upload" onClick={() => file.current?.click()} disabled={busy}>
            <Upload size={18} />
            <b>Upload a URDF</b>
            <small>Plain .urdf file, up to 300 kB. Meshes are not needed.</small>
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
        <button className="lab-primary sx-run" disabled={busy || !modes.length || !chosen || (modes.some((m) => m !== "urdfmodelica") && !models.length)} onClick={run}>
          {busy ? (
            <>
              <Clock size={16} /> Running… {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
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
                  {new Date(r.started).toLocaleString()} · {r.finished ? "best: " + (r.ranking?.[0] ? keyLabel(r.ranking[0]) : "-") : "unfinished"}
                </small>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

type LiveMode = { status: "waiting" | "running" | "done" | "failed"; started?: number; finished?: number; phase?: string | null; phase_started?: number; attempt?: number; attempts?: number; passed?: number };
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
              {s.status === "done" && `Finished · ${s.passed} checks passed`}
              {s.status === "failed" && "Finished · no usable file"}
            </small>
          </div>
        );
      })}
      <small className="sx-muted">Times are exact. Inside a step the bar is an estimate: the local AI does not report how far it has written.</small>
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
  return (
    <section className="sx-step sx-results">
      <h2>
        <span className="sx-n">3</span> Results · {report.source.label}
      </h2>
      {bestRes && (
        <div className="sx-winner">
          <Trophy size={22} />
          <div>
            <b>
              {bestTie.length ? `Tied: ${[best!, ...bestTie].map((m) => LABEL[m]).join(" and ")}` : `Best result: ${LABEL[best!]}`}
            </b>
            <p>{bestRes.verdict}</p>
            {bestRes.score.passed < bestRes.score.criteria.length && (
              <small>
                Best is not the same as correct: it still fails {bestRes.score.criteria.length - bestRes.score.passed} of the {bestRes.score.criteria.length} checks below.
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
                  {LABEL[m]}
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
            <div key={m} className={"sx-card" + (m === best ? " best" : "")}>
              <b>{LABEL[m]}</b>
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
