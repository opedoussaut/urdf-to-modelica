import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Bot, Check, CircleSlash, Download, Eye, EyeOff, FileArchive, Network, Plus, Trash2, User, X } from "lucide-react";
import { useAudience } from "../audience";
import { message, waitJob, type Doc } from "../studio";
import { convert, keyLabel, orderKeys, type LocalModel, type RunSummary } from "./api";
import type { Target } from "./SimpleApp";

type ReviewMode = "manual" | "ai" | "ai_ontology";
type Issue = { entity: string; category: string; evidence: string; confidence: number; correction: { component: string; parameter: string; value: number[] } };
type ReviewScore = {
  defects: number;
  found: number;
  found_type: number;
  recall: number | null;
  precision: number | null;
  false_alarms: number;
  issues_reported: number;
  corrections_proposed: number;
  corrections_fixed: number;
  corrections_with_new_problems: number;
  corrections: { issue: string; applied: boolean; fixed?: boolean; new_problems?: string[]; reason?: string; targets_defect?: string | null }[];
  by_defect: { defect: string; entity: string; category: string; found: boolean; found_type: boolean }[];
  faithfulness: { checked: number; correct: number; rate: number | null };
  brier: number | null;
};
type ReviewRec = { id: string; mode: ReviewMode; created: string; llm_model?: string; seconds?: number; reviewer?: string; report: { summary: string; issues: Issue[] }; score: ReviewScore };
type Targets = { seeded: { id: string; description: string; held_out: boolean }[]; runs: RunSummary[]; modes: Record<ReviewMode, string>; categories: string[]; models: LocalModel[] };
type FileView = { label: string; text: string; omc_messages: string; entities: string[]; graph: boolean };

const MODE_INFO: Record<ReviewMode, { label: string; plain: string; Icon: typeof Bot }> = {
  manual: { label: "Manual review", plain: "You read the file and list the problems you find. The timer measures your effort.", Icon: User },
  ai: { label: "AI-assisted review", plain: "A local AI reads the file and the robot file and lists problems with proposed corrections.", Icon: Bot },
  ai_ontology: { label: "AI + ontologies review", plain: "The same AI, also given the robot's facts from the knowledge graph (ontologies, units, sources).", Icon: Network },
};
const CATEGORY_LABEL: Record<string, string> = {
  axis: "wrong joint axis",
  unit: "wrong unit",
  limit: "wrong limit",
  connectivity: "wrong connection",
  mapping: "name / mapping",
  missing_component: "missing part or joint",
  mimic: "coupling (mimic) not enforced",
  joint_type: "wrong joint type",
  parameter_provenance: "mass / inertia / unsourced value",
  geometry: "wrong position or rotation",
  other: "whole file / other",
};
const pct = (x: number | null | undefined) => (x == null ? "-" : `${Math.round(x * 100)}%`);
const blankIssue = (): Issue => ({ entity: "", category: "other", evidence: "", confidence: 0.7, correction: { component: "", parameter: "", value: [] } });
const targetKey = (t?: Target) => (t ? (t.kind === "seeded" ? `seeded:${t.mutation}` : `${t.run}:${t.mode}`) : "");
const query = (t: Target) => (t.kind === "seeded" ? `kind=seeded&mutation=${encodeURIComponent(t.mutation || "")}` : `kind=conversion&run=${t.run}&mode=${encodeURIComponent(t.mode || "")}`);

export default function Review({ target, setTarget, toConvert, learn }: { target?: Target; setTarget: (t: Target) => void; toConvert: () => void; learn: () => void }) {
  const expert = useAudience() === "expert";
  const [targets, setTargets] = useState<Targets>(),
    [source, setSource] = useState<"conversion" | "seeded">(target?.kind === "seeded" ? "seeded" : "conversion"),
    [file, setFile] = useState<FileView>(),
    [reviews, setReviews] = useState<ReviewRec[]>([]),
    [truth, setTruth] = useState<{ entity: string; category: string; title: string }[] | null>(null),
    [findings, setFindings] = useState<{ title: string; basis: string; defect: boolean }[]>([]),
    [spoil, setSpoil] = useState(false),
    [mode, setMode] = useState<ReviewMode>("ai"),
    [model, setModel] = useState(""),
    [issues, setIssues] = useState<Issue[]>([blankIssue()]),
    [reviewer, setReviewer] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const startedAt = useRef<number>(Date.now());

  useEffect(() => {
    convert<Targets>("/review/targets")
      .then((t) => {
        setTargets(t);
        setModel((m) => m || t.models.find((x) => x.default)?.name || t.models[0]?.name || "");
      })
      .catch((e) => setError(message(e)));
  }, []);
  const refresh = (t: Target) =>
    convert(`/review/list?${query(t)}`)
      .then((r) => {
        setReviews(r.reviews);
        setTruth(r.ground_truth);
      })
      .catch((e) => setError(message(e)));
  useEffect(() => {
    if (!target) return;
    setError("");
    setFile(undefined);
    setSpoil(false);
    setIssues([blankIssue()]);
    startedAt.current = Date.now();
    convert<FileView>(`/review/file?${query(target)}`).then(setFile).catch((e) => setError(message(e)));
    refresh(target);
    if (target.kind !== "seeded")
      convert(`/runs/${target.run}/findings?mode=${encodeURIComponent(target.mode || "")}`)
        .then(setFindings)
        .catch(() => setFindings([]));
    else setFindings([]);
  }, [targetKey(target)]);
  useEffect(() => {
    if (mode === "manual") startedAt.current = Date.now();
  }, [mode]);

  const run = async () => {
    if (!target) return;
    setBusy(true);
    setError("");
    try {
      const body: any = { ...target, kind: target.kind || "conversion", review_mode: mode, model: mode === "manual" ? "" : model };
      if (mode === "manual") {
        body.manual = { summary: "", issues: issues.filter((i) => i.entity), claims: [] };
        body.manual_seconds = (Date.now() - startedAt.current) / 1000;
        body.reviewer = reviewer;
      }
      await waitJob(await convert<Doc>("/review/run", "POST", body));
      await refresh(target);
      setIssues([blankIssue()]);
      setTimeout(() => document.querySelector(".sx-compare")?.scrollIntoView({ behavior: "smooth" }), 80);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  const convTargets = useMemo(
    () => (targets?.runs || []).slice(0, 8).flatMap((r) => orderKeys(Object.keys(r.modes)).map((m) => ({ r, m }))),
    [targets],
  );

  return (
    <div className="lab sx-page">
      <div className="lab-plain">
        <b>IN PLAIN WORDS</b> A generated model can hide mistakes. Here a person, an AI, or an AI given the robot's knowledge graph reviews a file and proposes
        corrections. Each review is then scored against the problems we know are there, so you can see which way of reviewing works best.
      </div>
      <span className="lab-eyebrow">REVIEW</span>
      <h1>Review a model: by hand, with AI, or with AI + ontologies</h1>

      <section className="sx-step">
        <h2>
          <span className="sx-n">1</span> Choose a file
        </h2>
        <div className="sx-seg" role="tablist">
          <button role="tab" aria-selected={source === "conversion"} className={source === "conversion" ? "on" : ""} onClick={() => setSource("conversion")}>
            From your comparisons
          </button>
          <button role="tab" aria-selected={source === "seeded"} className={source === "seeded" ? "on" : ""} onClick={() => setSource("seeded")}>
            Test files with one known error
          </button>
        </div>
        {source === "conversion" ? (
          convTargets.length === 0 ? (
            <p className="sx-note">
              No comparison yet.{" "}
              <button className="sx-link" onClick={toConvert}>
                Convert a robot first
              </button>
            </p>
          ) : (
            <div className="sx-picker">
              {convTargets.map(({ r, m }) => (
                <button key={r.id + m} className={target?.run === r.id && target.mode === m ? "on" : ""} onClick={() => setTarget({ kind: "conversion", run: r.id, mode: m })}>
                  <b>{keyLabel(m)}</b>
                  <small>
                    {r.source} · {new Date(r.started).toLocaleString([], { dateStyle: "short", timeStyle: "short" })} · {r.modes[m].passed} checks passed
                  </small>
                </button>
              ))}
            </div>
          )
        ) : (
          <>
            <p className="sx-note">
              The studio's own model of the ViperX follower arm, copied with exactly one deliberate error (or none, for the control file). Because we know the
              error, these files measure how good each review mode is. Files marked "held out" were written after the studio's rules were frozen.
            </p>
            <div className="sx-picker">
              {(targets?.seeded || []).map((s) => (
                <button key={s.id} className={target?.mutation === s.id ? "on" : ""} onClick={() => setTarget({ kind: "seeded", mutation: s.id })}>
                  <b>
                    {s.id}
                    {s.held_out ? " · held out" : ""}
                  </b>
                  <small>{expert || s.id.startsWith("M0") ? s.description : "One hidden error (revealed after reviews, in the comparison)"}</small>
                </button>
              ))}
            </div>
          </>
        )}
      </section>

      {target && file && (
        <section className="sx-step">
          <h2>
            <span className="sx-n">2</span> Read it · {file.label}
          </h2>
          <div className="sx-downloads">
            <a className="sx-btn" href={`/api/convert/download?${query(target)}&what=package`} download>
              <FileArchive size={15} /> Download package for OMEdit / Dymola (.zip)
            </a>
            <a className="sx-btn" href={`/api/convert/download?${query(target)}&what=file`} download>
              <Download size={15} /> Download this file (.mo)
            </a>
            <small>The package opens as is: the README inside says which file to open and which model to simulate.</small>
          </div>
          {target.kind !== "seeded" && findings.length > 0 && (
            <div className={"sx-findings" + (spoil ? "" : " hidden")}>
              <button className="sx-link" onClick={() => setSpoil(!spoil)}>
                {spoil ? <EyeOff size={14} /> : <Eye size={14} />} {spoil ? "Hide" : "Show"} what the automatic checks found (measured, no AI){!spoil && " · reveals the answers"}
              </button>
              {spoil && (
                <ul>
                  {findings.map((f, i) => (
                    <li key={i}>
                      {f.title}
                      {f.basis !== "measured" && <em> ({f.basis})</em>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {file.omc_messages && (
            <details className="sx-omc">
              <summary>OpenModelica's messages for this file</summary>
              <pre>{file.omc_messages}</pre>
            </details>
          )}
          <Code text={file.text} />
        </section>
      )}

      {target && file && (
        <section className="sx-step">
          <h2>
            <span className="sx-n">3</span> Review it
          </h2>
          <div className="sx-modes">
            {(Object.keys(MODE_INFO) as ReviewMode[]).map((m) => {
              const { label, plain, Icon } = MODE_INFO[m];
              const off = m === "ai_ontology" && !file.graph;
              return (
                <label key={m} className={"sx-mode" + (mode === m ? " on" : "") + (off ? " off" : "")}>
                  <input type="radio" name="review-mode" checked={mode === m} disabled={busy || off} onChange={() => setMode(m)} />
                  <Icon size={22} />
                  <b>{label}</b>
                  <p>{off ? "Not available: this robot is not in the knowledge graph (uploaded URDF)." : plain}</p>
                </label>
              );
            })}
          </div>
          {mode !== "manual" ? (
            <div className="sx-models">
              <b>AI model</b>
              <div>
                {(targets?.models || []).map((m) => (
                  <label key={m.name} className={"sx-model" + (model === m.name ? " on" : "")}>
                    <input type="radio" name="review-model" checked={model === m.name} disabled={busy} onChange={() => setModel(m.name)} />
                    <span>
                      <b>{m.name}</b>
                      <small>
                        {m.parameters} · {m.size_gb} GB
                      </small>
                    </span>
                  </label>
                ))}
              </div>
              <small>The AI sees the file, the robot file and OpenModelica's messages, never the known errors. Same settings for both AI modes.</small>
            </div>
          ) : (
            <ManualForm issues={issues} setIssues={setIssues} entities={file.entities} categories={targets?.categories || []} reviewer={reviewer} setReviewer={setReviewer} />
          )}
          <button className="lab-primary sx-run" disabled={busy || (mode === "manual" && !issues.some((i) => i.entity)) || (mode !== "manual" && !model)} onClick={run}>
            {busy ? "Reviewing…" : mode === "manual" ? "Submit my review" : `Run the ${MODE_INFO[mode].label.toLowerCase()}`}
          </button>
          {busy && mode !== "manual" && <p className="sx-note">Usually under a minute with the small models; several minutes with the 30B model. Proposed corrections are then re-checked on copies.</p>}
          {error && <p className="lab-error">{error}</p>}
          {mode === "manual" && (
            <p className="sx-note">
              No problem found? Add one line with entity "model", category "whole file / other" and say so in the note: an empty review cannot be submitted.
            </p>
          )}
        </section>
      )}

      {target && reviews.length > 0 && <Compare reviews={reviews} truth={truth || []} expert={expert} learn={learn} />}
      <p className="sx-note sx-export">
        All scores, for reports and spreadsheets: <a href="/api/convert/scores?table=reviews&format=csv">reviews (CSV)</a> ·{" "}
        <a href="/api/convert/scores?table=conversions&format=csv">conversions (CSV)</a> · <a href="/api/convert/scores?table=reviews">JSON</a>
      </p>
    </div>
  );
}

function ManualForm({
  issues,
  setIssues,
  entities,
  categories,
  reviewer,
  setReviewer,
}: {
  issues: Issue[];
  setIssues: (i: Issue[]) => void;
  entities: string[];
  categories: string[];
  reviewer: string;
  setReviewer: (s: string) => void;
}) {
  const set = (k: number, patch: Partial<Issue>) => setIssues(issues.map((x, i) => (i === k ? { ...x, ...patch } : x)));
  return (
    <div className="sx-manual">
      <label className="sx-reviewer">
        Your name (optional)
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
      </label>
      {issues.map((it, k) => (
        <div key={k} className="sx-issue">
          <select value={it.entity} onChange={(e) => set(k, { entity: e.target.value })} aria-label="Where">
            <option value="">Where? (joint or part)</option>
            {entities.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
          <select value={it.category} onChange={(e) => set(k, { category: e.target.value })} aria-label="Kind of problem">
            {categories.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c] || c}
              </option>
            ))}
          </select>
          <input placeholder="What is wrong? (note)" value={it.evidence} onChange={(e) => set(k, { evidence: e.target.value })} />
          <label className="sx-conf">
            Sure? {Math.round(it.confidence * 100)}%
            <input type="range" min={0} max={1} step={0.05} value={it.confidence} onChange={(e) => set(k, { confidence: +e.target.value })} />
          </label>
          <details>
            <summary>Proposed correction (optional)</summary>
            <div className="sx-corr">
              <input placeholder="component, e.g. j_elbow" value={it.correction.component} onChange={(e) => set(k, { correction: { ...it.correction, component: e.target.value } })} />
              <input placeholder="parameter, e.g. n or axis.xyz" value={it.correction.parameter} onChange={(e) => set(k, { correction: { ...it.correction, parameter: e.target.value } })} />
              <input
                placeholder="value(s), e.g. 0, 1, 0"
                value={it.correction.value.join(", ")}
                onChange={(e) =>
                  set(k, {
                    correction: {
                      ...it.correction,
                      value: e.target.value
                        .split(",")
                        .map((v) => parseFloat(v))
                        .filter((v) => !Number.isNaN(v))
                        .slice(0, 3),
                    },
                  })
                }
              />
            </div>
          </details>
          <button className="sx-icon" title="Remove this line" onClick={() => setIssues(issues.filter((_, i) => i !== k))} disabled={issues.length === 1}>
            <Trash2 size={15} />
          </button>
        </div>
      ))}
      <button className="sx-btn" onClick={() => setIssues([...issues, blankIssue()])}>
        <Plus size={14} /> Add a problem
      </button>
    </div>
  );
}

function Compare({ reviews, truth, expert, learn }: { reviews: ReviewRec[]; truth: { entity: string; category: string; title: string }[]; expert: boolean; learn: () => void }) {
  const head = (r: ReviewRec) => MODE_INFO[r.mode].label.replace(" review", "") + (r.llm_model ? ` · ${r.llm_model}` : r.reviewer ? ` · ${r.reviewer}` : "");
  return (
    <section className="sx-step sx-compare">
      <h2>
        <span className="sx-n">4</span> Compare the reviews
      </h2>
      <p className="sx-note">
        The known problems are now revealed. Each review is scored the same way, automatically.{" "}
        <button className="sx-link" onClick={learn}>
          <BookOpen size={13} /> How are reviews scored?
        </button>
      </p>
      <div className="sx-table-wrap">
        <table className="sx-table">
          <thead>
            <tr>
              <th>Known problem</th>
              {reviews.map((r) => (
                <th key={r.id}>
                  {head(r)}
                  <small className="sx-th-sub">{new Date(r.created).toLocaleTimeString([], { timeStyle: "short" })}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {truth.length === 0 && (
              <tr>
                <td>
                  <b>No known problem</b>
                  <small>Control file: the best review reports nothing.</small>
                </td>
                {reviews.map((r) => (
                  <td key={r.id}>{r.score.issues_reported === 0 ? <Check size={17} className="sx-ok" /> : <X size={17} className="sx-ko" />}</td>
                ))}
              </tr>
            )}
            {truth.map((d, k) => (
              <tr key={k}>
                <td>
                  <b>{d.title}</b>
                  <small>
                    {d.entity} · {CATEGORY_LABEL[d.category] || d.category}
                  </small>
                </td>
                {reviews.map((r) => {
                  const b = r.score.by_defect[k];
                  const fixed = r.score.corrections.some((c) => c.fixed && c.targets_defect === d.title);
                  return (
                    <td key={r.id}>
                      {b?.found_type ? <Check size={17} className="sx-ok" /> : b?.found ? <CircleSlash size={16} className="sx-warn" /> : <X size={17} className="sx-ko" />}
                      <small>{b?.found_type ? "found" : b?.found ? "right place, wrong kind" : "missed"}{fixed ? " · correction works" : ""}</small>
                    </td>
                  );
                })}
              </tr>
            ))}
            <Row label="Recall" help="Share of the known problems found (right place and kind)." reviews={reviews} f={(s) => pct(s.recall)} />
            <Row label="Precision" help="Share of the reported problems that are real (false alarms cost engineering time)." reviews={reviews} f={(s) => pct(s.precision)} />
            <Row label="False alarms" help="Problems reported that are not there." reviews={reviews} f={(s) => String(s.false_alarms)} />
            <Row
              label="Corrections that work"
              help="Each proposed correction is applied to a copy and re-checked: does the problem disappear without breaking anything else?"
              reviews={reviews}
              f={(s) => `${s.corrections_fixed} of ${s.corrections_proposed}` + (s.corrections_with_new_problems ? ` · ${s.corrections_with_new_problems} broke something` : "")}
            />
            <Row label="Facts stated correctly" help="Numbers the review quoted (axes, limits, masses…) checked against the robot file." reviews={reviews} f={(s) => (s.faithfulness.checked ? `${s.faithfulness.correct} of ${s.faithfulness.checked}` : "-")} />
            <Row
              label="Confidence calibration"
              help="Brier score: 0 = the stated confidence was always right, 0.25 = no better than a coin flip, 1 = always confidently wrong."
              reviews={reviews}
              f={(s) => (s.brier == null ? "-" : s.brier.toFixed(2))}
            />
            <tr className="sx-cost">
              <td>
                <b>Time</b>
                <small>AI answer time, or the person's time on the form.</small>
              </td>
              {reviews.map((r) => (
                <td key={r.id}>
                  <small>{r.seconds != null ? `${Math.round(r.seconds)} s` : "-"}</small>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {expert && (
        <details className="sx-omc">
          <summary>What each review reported</summary>
          {reviews.map((r) => (
            <div key={r.id} className="sx-rev">
              <b>{head(r)}</b>
              {r.report.summary && <p>{r.report.summary}</p>}
              <ul>
                {r.report.issues.map((i, k) => (
                  <li key={k}>
                    <code>{i.entity}</code> · {CATEGORY_LABEL[i.category] || i.category} · {Math.round(i.confidence * 100)}% · {i.evidence}
                    {i.correction.component && (
                      <>
                        {" "}
                        → <code>{`${i.correction.component}.${i.correction.parameter} = ${i.correction.value.join(", ")}`}</code>
                      </>
                    )}
                  </li>
                ))}
                {r.report.issues.length === 0 && <li>No problem reported.</li>}
              </ul>
            </div>
          ))}
        </details>
      )}
    </section>
  );
}

function Row({ label, help, reviews, f }: { label: string; help: string; reviews: ReviewRec[]; f: (s: ReviewScore) => string }) {
  return (
    <tr className="sx-metric">
      <td>
        <b>{label}</b>
        <small>{help}</small>
      </td>
      {reviews.map((r) => (
        <td key={r.id}>
          <b>{f(r.score)}</b>
        </td>
      ))}
    </tr>
  );
}

function Code({ text }: { text: string }) {
  return (
    <pre className="sx-code" tabIndex={0}>
      {text.split("\n").map((l, i) => (
        <div key={i}>
          <span className="sx-ln">{i + 1}</span>
          {l || " "}
        </div>
      ))}
    </pre>
  );
}
