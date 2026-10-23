import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, CircleDashed, ExternalLink, Play, RefreshCw, ShieldAlert, XCircle } from "lucide-react";
import { useAudience } from "../audience";
import { message, waitJob } from "../studio";
import { wf } from "./api";
import "./workflow.css";

type Stage = "input" | "convert" | "check" | "repair" | "review" | "approved" | "simulate";
const STAGES: { id: Stage; label: string; plain: string }[] = [
  { id: "input", label: "URDF input", plain: "The robot's description file and its meshes, fixed (pinned) and fingerprinted (hashed)." },
  { id: "convert", label: "Convert", plain: "The DLR converter turns the file into a Modelica model. No AI, no corrections." },
  { id: "check", label: "OpenModelica check", plain: "OpenModelica and an independent comparison with the robot file list every problem, in order." },
  { id: "repair", label: "AI repair comparison", plain: "Two AI methods try to fix those problems under identical conditions: AI alone, and AI with Modelica knowledge." },
  { id: "review", label: "Engineer review", plain: "A person inspects every proposed change, keeps or rejects each one, and re-checks the result." },
  { id: "approved", label: "Approved model", plain: "Only a person promotes a model. Then, separately, the missing connection lines are drawn." },
  { id: "simulate", label: "Simulation", plain: "The approved model is simulated from here or opened in OMEdit." },
];
const ARM_LABEL: Record<string, string> = { ai_only: "AI only", ai_assets: "AI + Modelica assets" };
const STATE_TONE: Record<string, string> = { validated: "ok", improved: "mid", regressed: "bad", "not improved": "bad", unchanged: "bad", "rejected (integrity)": "bad", "not run": "idle" };

/** URDF → Convert → OpenModelica check → AI repair comparison → Engineer review → Approved model → Simulation. */
export default function Workflow() {
  const expert = useAudience() === "expert";
  const [runs, setRuns] = useState<any[]>([]);
  const [rid, setRid] = useState<string>();
  const [run, setRun] = useState<any>();
  const [stage, setStage] = useState<Stage>("check");
  const [error, setError] = useState("");
  const load = (id = rid) => id && wf("/runs/" + id).then(setRun).catch((e) => setError(message(e)));
  useEffect(() => {
    wf<any[]>("/runs")
      .then((r) => {
        setRuns(r);
        const pick = r.find((x) => x.model?.startsWith("qwen3") && x.validated_cases) || r.find((x) => x.validated_cases) || r[0];
        if (pick) setRid(pick.id);
      })
      .catch((e) => setError(message(e)));
  }, []);
  useEffect(() => {
    setRun(undefined);
    load(rid);
  }, [rid]);

  const done: Record<Stage, boolean> = {
    input: !!run?.stage1,
    convert: !!run?.stage1,
    check: !!run?.stage2,
    repair: !!run && Object.keys(run.repairs || {}).length > 0,
    review: !!run?.reviews?.length,
    approved: !!run?.approvals?.length,
    simulate: false,
  };

  return (
    <div className="lab sx-page wf">
      <span className="lab-eyebrow">ENGINEERING WORKFLOW · URDF → MODELICA</span>
      <h1>Convert, check, let AI repair, and let an engineer decide</h1>
      <p className="lab-plain">
        <b>IN PLAIN WORDS</b> A converter writes the physics model without AI. OpenModelica lists its problems. Two AI methods then try to repair it
        under exactly the same conditions; the only difference is that one also reads Modelica documentation. Every change is checked
        independently and a person decides what is kept. Results are measured, whichever method turns out better.
      </p>
      <div className="wf-bar">
        <label>
          Run{" "}
          <select value={rid || ""} onChange={(e) => setRid(e.target.value)}>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.robot} · {r.model ? "repairs by " + r.model : "conversion and checks"} {r.validated_cases ? `· ${r.validated_cases} cases validated` : ""}
              </option>
            ))}
          </select>
        </label>
        <button className="sx-btn" onClick={() => load()}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>
      {error && <p className="lab-error">{error}</p>}

      <ol className="wf-rail" aria-label="Workflow stages">
        {STAGES.map((s, i) => (
          <li key={s.id}>
            <button className={(stage === s.id ? "on " : "") + (done[s.id] ? "done" : "")} onClick={() => setStage(s.id)} aria-current={stage === s.id ? "step" : undefined}>
              <span className="wf-n">{done[s.id] ? <CheckCircle2 size={15} /> : i + 1}</span>
              {s.label}
            </button>
          </li>
        ))}
      </ol>
      <p className="wf-stage-plain">{STAGES.find((s) => s.id === stage)!.plain}</p>

      {!run ? (
        <p className="sx-muted">{runs.length ? "Loading…" : "No workflow run yet. Run: python -m kkh.workflow.stage1_convert aloha_vx300s, then stage2_check."}</p>
      ) : stage === "input" ? (
        <Input run={run} expert={expert} />
      ) : stage === "convert" ? (
        <Convert run={run} expert={expert} />
      ) : stage === "check" ? (
        <Check run={run} expert={expert} />
      ) : stage === "repair" ? (
        <Repair run={run} expert={expert} />
      ) : stage === "review" ? (
        <Review run={run} reload={() => load()} />
      ) : stage === "approved" ? (
        <Approved run={run} reload={() => load()} />
      ) : (
        <Simulate run={run} />
      )}
    </div>
  );
}

function Stat({ k, v, tone }: { k: string; v: any; tone?: string }) {
  return (
    <div className={"wf-stat " + (tone || "")}>
      <b>{v}</b>
      <span>{k}</span>
    </div>
  );
}

function Input({ run, expert }: { run: any; expert: boolean }) {
  const s = run.stage1.source;
  return (
    <section className="wf-card">
      <h2>{s.label}</h2>
      <div className="wf-stats">
        <Stat k="links" v={s.links} />
        <Stat k="joints" v={s.joints} />
        <Stat k="moving joints" v={s.movable_joints} />
        <Stat k="mesh files hashed" v={`${run.stage1.assets.resolved}/${run.stage1.assets.count}`} />
      </div>
      <p>
        Source: {s.provenance} · licence {s.license}
      </p>
      {expert && (
        <p className="wf-mono">
          {s.urdf} · sha256 {s.urdf_sha256}
        </p>
      )}
    </section>
  );
}

function Convert({ run, expert }: { run: any; expert: boolean }) {
  const st = run.stage1;
  return (
    <section className="wf-card">
      <h2>DLR URDFModelica, no AI</h2>
      <div className="wf-stats">
        <Stat k="reproducible (second run identical)" v={st.reproducibility?.identical ? "yes" : "no"} tone={st.reproducibility?.identical ? "ok" : "bad"} />
        <Stat k="links / joints mapped" v={`${st.summary.mapped_links} / ${st.summary.mapped_joints}`} />
        <Stat k="URDF values copied unchanged" v={`${st.summary.physical_values_compared - st.summary.physical_mismatches}/${st.summary.physical_values_compared}`} tone="ok" />
        <Stat k="ignored, rewritten or unused URDF content" v={st.summary.unsupported_items} tone="mid" />
      </div>
      <h3>What the converter drops or rewrites</h3>
      <ul className="wf-list">
        {Object.entries(
          (run.unsupported || []).reduce((acc: any, u: any) => ({ ...acc, [u.feature + ": " + u.effect]: [...(acc[u.feature + ": " + u.effect] || []), u] }), {}),
        ).map(([k, us]: any) => (
          <li key={k}>
            <b>{k}</b> {us.length > 1 ? `(${us.length}×)` : us[0].entity ? `· ${us[0].entity}` : ""}
            {expert && <small>{us[0].evidence}</small>}
          </li>
        ))}
      </ul>
      {expert && (
        <p className="wf-mono">
          converter {st.converter.commit.slice(0, 8)} · {st.converter.args?.join(" ")} · pre-processing {st.converter.preprocessing.join(", ")} · {st.versions.openmodelica}
        </p>
      )}
    </section>
  );
}

const STEP_LABEL: Record<string, string> = {
  load: "Load and parse",
  structure: "Structure",
  balance_translation: "Balance and translation",
  simulation: "Baseline simulation",
  urdf_consistency: "Matches the URDF (motion, parameters, torques)",
  records: "Record values = URDF",
  graphics: "Diagram graphics (separate)",
};

function Check({ run, expert }: { run: any; expert: boolean }) {
  const d = run.stage2;
  const [cat, setCat] = useState("");
  const filtered = d.findings.filter((f: any) => (!cat || f.category === cat) && (expert || f.severity !== "info"));
  // Overview: identical messages (e.g. one rewritten mesh path per link) become one row with a count
  const shown = expert
    ? filtered
    : Object.values(
        filtered.reduce((acc: any, f: any) => {
          const k = f.step + "|" + f.message;
          acc[k] = acc[k] ? { ...acc[k], entity: `${(acc[k]._n || 1) + 1} places`, _n: (acc[k]._n || 1) + 1 } : { ...f };
          return acc;
        }, {}),
      );
  return (
    <section className="wf-card">
      <h2>
        Verdict: <span className={"wf-verdict " + (d.verdict === "validated" ? "ok" : "bad")}>{d.verdict}</span>
      </h2>
      <p className="sx-note">{d.verdict_rule}</p>
      <ol className="wf-steps">
        {Object.entries(STEP_LABEL).map(([k, label]) => {
          const s = d.steps[k] || {};
          return (
            <li key={k} className={s.state}>
              {s.state === "pass" ? <CheckCircle2 size={15} /> : s.state === "fail" ? <XCircle size={15} /> : <CircleDashed size={15} />}
              <b>{label}</b>
              <span>{s.state}</span>
              {k === "graphics" && s.totals && <small>{s.totals.connections_without_line} of {s.totals.connections} connections without a drawn line</small>}
              {k === "balance_translation" && s.equations && <small>{s.equations} equations = {s.variables} unknowns</small>}
            </li>
          );
        })}
      </ol>
      <h3>Findings ({shown.length})</h3>
      <div className="wf-chips">
        {["", ...Object.keys(d.counts.by_category)].map((c) => (
          <button key={c} className={cat === c ? "on" : ""} onClick={() => setCat(c)}>
            {c || "all"} {c && <small>{d.counts.by_category[c]}</small>}
          </button>
        ))}
      </div>
      <table className="wf-table">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Step</th>
            <th>Category</th>
            <th>Where</th>
            <th>Finding</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((f: any) => (
            <tr key={f.id} className={f.severity}>
              <td>{f.severity}</td>
              <td>{f.step}</td>
              <td>{f.category}</td>
              <td>{f.entity || "—"}{expert && f.file ? <small> {f.file}:{f.line}</small> : null}</td>
              <td>
                {f.message}
                {expert && f.evidence && <small className="wf-ev">{String(f.evidence).slice(0, 300)}</small>}
                {f.related && <small className="wf-ev">related: {f.related.join(", ")}</small>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Repair({ run, expert }: { run: any; expert: boolean }) {
  const cases = run.validation?.cases || [];
  const [sel, setSel] = useState<string>(cases[0]?.case || "natural");
  const [detail, setDetail] = useState<Record<string, any>>({});
  useEffect(() => {
    if (!run.repairs?.[sel]) return;
    Promise.all(
      ["ai_only", "ai_assets"].map((arm) =>
        run.repairs[sel][arm] ? wf(`/runs/${run.id}/repair/${sel}/${arm}`).then((x) => [arm, x]).catch(() => [arm, null]) : Promise.resolve([arm, null]),
      ),
    ).then((pairs) => setDetail(Object.fromEntries(pairs)));
  }, [sel, run.id]);
  if (!cases.length && !Object.keys(run.repairs || {}).length)
    return <p className="sx-muted">No repair has been run on this run yet. Choose a run made by a repair campaign (python -m kkh.workflow.campaign).</p>;
  const summ = run.validation?.summary || {};
  const c = cases.find((x: any) => x.case === sel);
  const ch = (run.faults.characterisation || []).find((r: any) => r.id === sel);
  return (
    <>
      <section className="wf-card">
        <h2>Summary over {cases.length} case(s) · model {run.campaign?.model}</h2>
        <div className="wf-arms">
          {["ai_only", "ai_assets"].map((arm) => {
            const s = summ[arm] || {};
            return (
              <div key={arm} className={"wf-arm " + arm}>
                <h3>{ARM_LABEL[arm]}</h3>
                <div className="wf-stats">
                  <Stat k="validated" v={`${s.validated ?? 0}/${s.cases ?? 0}`} tone={s.validated ? "ok" : "bad"} />
                  <Stat k="improved" v={s.improved ?? 0} />
                  <Stat k="regressed" v={s.regressed ?? 0} tone={s.regressed ? "bad" : ""} />
                  <Stat k="rejected (integrity)" v={s.rejected_integrity ?? 0} tone={s.rejected_integrity ? "bad" : ""} />
                  <Stat k="faults undone" v={s.faults_reverted ?? 0} />
                  <Stat k="findings resolved / new" v={`${s.findings_resolved ?? 0} / ${s.findings_new ?? 0}`} />
                  <Stat k="seconds" v={s.seconds ?? 0} />
                </div>
              </div>
            );
          })}
        </div>
        <p className="sx-note">{run.validation?.rule}</p>
      </section>
      <section className="wf-card">
        <h2>Case</h2>
        <div className="wf-chips">
          {cases.map((x: any) => (
            <button key={x.case} className={sel === x.case ? "on" : ""} onClick={() => setSel(x.case)}>
              {x.case === "natural" ? "natural findings" : `${x.case} ${x.fault?.title}`}
              {x.fault?.held_out && <small>held out</small>}
            </button>
          ))}
        </div>
        {ch && (
          <p className="sx-note">
            Seeded fault ({ch.category}). Caught by the deterministic checks at: {ch.caught_by.join(", ")} · verdict with the fault: {ch.verdict}
          </p>
        )}
        <div className="wf-arms">
          {["ai_only", "ai_assets"].map((arm) => {
            const a = c?.arms?.[arm] || { state: "not run" };
            const det = detail[arm];
            return (
              <div key={arm} className={"wf-arm " + arm}>
                <h3>
                  {ARM_LABEL[arm]} <span className={"wf-pill " + (STATE_TONE[a.state] || "")}>{a.state}</span>
                </h3>
                {a.state !== "not run" && (
                  <>
                    <p>
                      {a.verdict_before} → <b>{a.verdict_after}</b>
                    </p>
                    <div className="wf-stats small">
                      <Stat k="resolved" v={a.findings.resolved} />
                      <Stat k="new" v={a.findings.new} tone={a.findings.new ? "bad" : ""} />
                      <Stat k="attempts" v={a.attempts} />
                      <Stat k="edits applied / proposed" v={`${a.edits_applied}/${a.edits_proposed}`} />
                      {arm === "ai_assets" && <Stat k="knowledge chunks given" v={a.chunks_supplied} />}
                      <Stat k="tokens out" v={a.tokens_out} />
                    </div>
                    {a.fault_text_reverted !== null && a.fault_text_reverted !== undefined && <p>Seeded fault undone: {a.fault_text_reverted ? "yes" : "no"}</p>}
                    {a.integrity_flags?.length > 0 && (
                      <div className="wf-flags">
                        <ShieldAlert size={15} /> Integrity flags:
                        <ul>
                          {a.integrity_flags.map((f: any, i: number) => (
                            <li key={i}>
                              {f.flag} {f.file || f.entity || ""} {f.evidence ? `(${f.evidence})` : ""}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {a.citation_flags > 0 && <p className="wf-bad">{a.citation_flags} edit(s) cited sources that were not supplied</p>}
                  </>
                )}
                {det?.edits?.length > 0 && (
                  <details>
                    <summary>{det.edits.length} applied edit(s) and their evidence</summary>
                    {det.edits.map((e: any) => (
                      <div key={e.id} className="wf-edit">
                        <b>
                          {e.id} · {e.file}
                        </b>
                        <p>{e.explanation}</p>
                        {e.cited_sources?.length > 0 && (
                          <ul className="wf-cites">
                            {e.cited_sources.map((s: any) => (
                              <li key={s.id} className={s.unknown ? "bad" : ""}>
                                {s.id} {s.unknown ? "(not supplied)" : `· ${s.version} · ${s.licence} · ${s.source_path}:${s.line_start}`}
                              </li>
                            ))}
                          </ul>
                        )}
                        {expert && (
                          <pre>
                            - {e.search}
                            {"\n"}+ {e.replace}
                          </pre>
                        )}
                      </div>
                    ))}
                  </details>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

function useJob() {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const go = async (label: string, fn: () => Promise<any>) => {
    setBusy(label);
    setErr("");
    try {
      const r = await fn();
      return r && r.data?.status ? await waitJob(r) : r;
    } catch (e) {
      setErr(message(e));
    } finally {
      setBusy("");
    }
  };
  return { busy, err, go };
}

function Review({ run, reload }: { run: any; reload: () => void }) {
  const cases = Object.keys(run.repairs || {});
  const [cs, setCs] = useState(cases[0] || "natural");
  const [arm, setArm] = useState("ai_assets");
  const [edits, setEdits] = useState<any[]>([]);
  const [keep, setKeep] = useState<Set<string>>(new Set());
  const [reviewer, setReviewer] = useState(() => localStorage.getItem("kkh.reviewer") || "");
  const [note, setNote] = useState("");
  const [key, setKey] = useState("");
  const [diff, setDiff] = useState<any[]>([]);
  const [file, setFile] = useState("");
  const [text, setText] = useState("");
  const { busy, err, go } = useJob();
  useEffect(() => {
    if (!run.repairs?.[cs]?.[arm]) return setEdits([]);
    wf(`/runs/${run.id}/repair/${cs}/${arm}`).then((x) => {
      setEdits(x.edits);
      setKeep(new Set());
    });
  }, [cs, arm, run.id]);
  const candidates = useMemo(
    () => [
      ...cases.flatMap((c) => Object.keys(run.repairs[c]).map((a) => ({ key: `repair/${c}/${a}`, label: `${c} · ${ARM_LABEL[a]} (as proposed)`, v: null }))),
      ...(run.reviews || []).map((r: any) => ({ key: r.key, label: `${r.key} · by ${r.reviewer}`, v: r.validation })),
    ],
    [run],
  );
  useEffect(() => {
    if (key) wf(`/runs/${run.id}/candidate/diff?key=${encodeURIComponent(key)}`).then(setDiff).catch(() => setDiff([]));
  }, [key, run.id]);
  const who = () => {
    localStorage.setItem("kkh.reviewer", reviewer);
    return reviewer;
  };
  const cand = candidates.find((c: any) => c.key === key);
  return (
    <>
      <section className="wf-card">
        <h2>1. Keep or reject each proposed change</h2>
        <div className="wf-bar">
          <select value={cs} onChange={(e) => setCs(e.target.value)}>
            {cases.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <select value={arm} onChange={(e) => setArm(e.target.value)}>
            <option value="ai_only">AI only</option>
            <option value="ai_assets">AI + Modelica assets</option>
          </select>
          <input placeholder="Your name (recorded)" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
        </div>
        {!edits.length && <p className="sx-muted">This arm applied no edit for this case.</p>}
        {edits.map((e) => (
          <label key={e.id} className="wf-edit pick">
            <input type="checkbox" checked={keep.has(e.id)} onChange={(x) => setKeep((s) => { const n = new Set(s); x.target.checked ? n.add(e.id) : n.delete(e.id); return n; })} />
            <span>
              <b>
                {e.id} · {e.file}
              </b>
              <p>{e.explanation}</p>
              {e.cites?.length > 0 && <small>cites: {e.cites.join(", ")}</small>}
              <pre>
                - {e.search}
                {"\n"}+ {e.replace}
              </pre>
            </span>
          </label>
        ))}
        {edits.length > 0 && (
          <div className="wf-bar">
            <input placeholder="Note (why)" value={note} onChange={(e) => setNote(e.target.value)} />
            <button
              className="sx-btn primary"
              disabled={!reviewer || !!busy}
              onClick={async () => {
                const r = await go("Building", () => wf(`/runs/${run.id}/review/accept`, "POST", { case: cs, arm, edits: [...keep], reviewer: who(), note }));
                if (r) {
                  setKey(r.key);
                  reload();
                }
              }}
            >
              Build a candidate from the {keep.size} kept change(s)
            </button>
          </div>
        )}
      </section>
      <section className="wf-card">
        <h2>2. Inspect, amend, re-check a candidate</h2>
        <div className="wf-bar">
          <select value={key} onChange={(e) => setKey(e.target.value)}>
            <option value="">Choose a candidate…</option>
            {candidates.map((c: any) => (
              <option key={c.key} value={c.key}>
                {c.label}
                {c.v ? ` · ${c.v.verdict}` : ""}
              </option>
            ))}
          </select>
          <button className="sx-btn" disabled={!key || !!busy} onClick={() => go("Validating", () => wf(`/runs/${run.id}/validate`, "POST", { key })).then(reload)}>
            <Play size={14} /> {busy === "Validating" ? "Validating…" : "Re-check (independent)"}
          </button>
          <button className="sx-btn" disabled={!key} onClick={() => go("OMEdit", () => wf(`/runs/${run.id}/omedit`, "POST", { key }))}>
            <ExternalLink size={14} /> Open in OMEdit
          </button>
        </div>
        {cand?.v && (
          <p className={cand.v.verdict === "validated" && !cand.v.integrity_flags.length ? "wf-ok" : "wf-bad"}>
            Last check: {cand.v.verdict} · resolved {cand.v.findings.resolved}, new {cand.v.findings.new} · integrity flags {cand.v.integrity_flags.length}
          </p>
        )}
        {diff.map((d) => (
          <details key={d.file} open>
            <summary>{d.file}</summary>
            <pre className="wf-diff">{d.diff}</pre>
          </details>
        ))}
        {key && !key.startsWith("repair/") && (
          <div className="wf-amend">
            <select value={file} onChange={async (e) => { setFile(e.target.value); setText(e.target.value ? (await wf(`/runs/${run.id}/candidate/file?key=${encodeURIComponent(key)}&path=${encodeURIComponent(e.target.value)}`)).text : ""); }}>
              <option value="">Amend a file by hand…</option>
              {diff.map((d) => (
                <option key={d.file}>{d.file}</option>
              ))}
            </select>
            {file && (
              <>
                <textarea value={text} onChange={(e) => setText(e.target.value)} rows={14} spellCheck={false} />
                <button className="sx-btn" disabled={!reviewer || !!busy} onClick={async () => { const r = await go("Saving", () => wf(`/runs/${run.id}/review/amend`, "POST", { key, path: file, text, reviewer: who(), note })); if (r) { setKey(r.key); reload(); } }}>
                  Save as a new version
                </button>
              </>
            )}
          </div>
        )}
        {busy && <p className="sx-muted">{busy}…</p>}
        {err && <p className="lab-error">{err}</p>}
      </section>
    </>
  );
}

function Approved({ run, reload }: { run: any; reload: () => void }) {
  const cands = (run.reviews || []).filter((r: any) => r.validation);
  const [key, setKey] = useState(cands[0]?.key || "");
  const [reviewer, setReviewer] = useState(() => localStorage.getItem("kkh.reviewer") || "");
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(false);
  const { busy, err, go } = useJob();
  const v = cands.find((c: any) => c.key === key)?.validation;
  const clean = v && v.verdict === "validated" && !v.integrity_flags.length;
  return (
    <>
      <section className="wf-card">
        <h2>Decide</h2>
        {!cands.length ? (
          <p className="sx-muted">Build and re-check a candidate in “Engineer review” first.</p>
        ) : (
          <>
            <div className="wf-bar">
              <select value={key} onChange={(e) => setKey(e.target.value)}>
                {cands.map((c: any) => (
                  <option key={c.key} value={c.key}>
                    {c.key} · {c.validation.verdict}
                  </option>
                ))}
              </select>
              <input placeholder="Your name (recorded)" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
            </div>
            {v && (
              <p className={clean ? "wf-ok" : "wf-bad"}>
                {clean ? <CheckCircle2 size={14} /> : <CircleAlert size={14} />} {v.verdict}; {v.open_findings.length} open finding(s); {v.integrity_flags.length} integrity flag(s)
              </p>
            )}
            <textarea placeholder="Justification (required to approve with open findings)" value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
            {!clean && (
              <label className="wf-check">
                <input type="checkbox" checked={open} onChange={(e) => setOpen(e.target.checked)} /> Approve with the open findings listed above (recorded)
              </label>
            )}
            <div className="wf-bar">
              <button className="sx-btn primary" disabled={!reviewer || !!busy || (!clean && (!open || note.trim().length < 15))}
                onClick={() => go("Approving", () => wf(`/runs/${run.id}/decide`, "POST", { key, decision: "approve", reviewer, note, accept_open_findings: open })).then(reload)}>
                Approve and promote
              </button>
              <button className="sx-btn" disabled={!reviewer || !!busy} onClick={() => go("Rejecting", () => wf(`/runs/${run.id}/decide`, "POST", { key, decision: "reject", reviewer, note })).then(reload)}>
                Reject
              </button>
            </div>
          </>
        )}
        {busy && <p className="sx-muted">{busy}… (includes the separate layout pass)</p>}
        {err && <p className="lab-error">{err}</p>}
      </section>
      {(run.approvals || []).map((a: any) => (
        <section key={a.approved} className="wf-card">
          <h2>
            {a.approved} <span className={"wf-pill " + (a.status === "approved" ? "ok" : "mid")}>{a.status}</span>
          </h2>
          <p>
            by {a.reviewer} at {a.at} · from {a.key}
          </p>
          <p>{a.note}</p>
          <p className="sx-note">
            Layout pass (after approval, annotations only): connections without a line {a.layout_pass.before.connections_without_line} → {a.layout_pass.after.connections_without_line}
          </p>
          {a.open_findings?.length > 0 && (
            <details>
              <summary>{a.open_findings.length} open finding(s) accepted</summary>
              <ul className="wf-list">{a.open_findings.map((f: any) => <li key={f.id}>{f.category}: {f.message}</li>)}</ul>
            </details>
          )}
        </section>
      ))}
    </>
  );
}

function Simulate({ run }: { run: any }) {
  const [res, setRes] = useState<Record<string, any>>({});
  const { busy, err, go } = useJob();
  if (!run.approvals?.length) return <p className="sx-muted">Approve a model first.</p>;
  return (
    <section className="wf-card">
      <h2>Simulate an approved model</h2>
      {run.approvals.map((a: any) => (
        <div key={a.approved} className="wf-bar">
          <b>{a.approved}</b>
          <button className="sx-btn primary" disabled={!!busy} onClick={async () => { const r = await go("Simulating", () => wf(`/runs/${run.id}/simulate`, "POST", { key: a.approved })); if (r) setRes((x) => ({ ...x, [a.approved]: r })); }}>
            <Play size={14} /> Simulate (standard excitation)
          </button>
          <button className="sx-btn" onClick={() => go("OMEdit", () => wf(`/runs/${run.id}/omedit`, "POST", { key: a.approved }))}>
            <ExternalLink size={14} /> Open in OMEdit
          </button>
          {res[a.approved] && (
            <span>
              {res[a.approved].verdict} ·{" "}
              {(res[a.approved].consistency || []).map((c: any) => `${c.id} ${c.ok ? "✓" : "✗"}`).join(" · ")}
            </span>
          )}
        </div>
      ))}
      {busy && <p className="sx-muted">{busy}… (OpenModelica, about a minute)</p>}
      {err && <p className="lab-error">{err}</p>}
    </section>
  );
}
