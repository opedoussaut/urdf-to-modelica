import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import { AlertTriangle, BookOpen, Bot, Check, Lightbulb, Network, Pencil, Send, ShieldCheck, Undo2, X } from "lucide-react";
import { useAudience } from "../audience";
import { message, request, waitJob, type Doc } from "../studio";
import { convert, MODE_ORDER, type ModeId, type Report, type RunSummary, type Score } from "./api";
import type { Target } from "./SimpleApp";

const LABEL: Record<string, string> = { llm: "AI only", llm_rag: "AI + library search", urdfmodelica: "URDFModelica" };
const INTENTS = [
  {
    id: "explain",
    Icon: Lightbulb,
    label: "Explain this model",
    q: "Explain this Modelica model in plain language for a non-expert: what the main parts represent in the robot, how they are connected, and what the model can and cannot simulate.",
  },
  {
    id: "errors",
    Icon: AlertTriangle,
    label: "Find possible errors",
    q: "Compare this Modelica model with the URDF and list the possible modelling errors: missing links or joints, wrong joint axes or limits, wrong masses or origins, unit mistakes, mimic joints not enforced. For each, say where it is and how sure you are.",
  },
  {
    id: "fix",
    Icon: Pencil,
    label: "Suggest a fix",
    q: "Propose a concrete correction for the most important problem in this Modelica model, as exact parameter changes (component instance, parameter, value from the URDF) or a short code change. Do not change values that already match the URDF.",
  },
];

type Msg = Doc;

export default function Understand({ target, setTarget, toConvert, learn }: { target?: Target; setTarget: (t: Target) => void; toConvert: () => void; learn: () => void }) {
  const expert = useAudience() === "expert";
  const [runs, setRuns] = useState<RunSummary[]>([]),
    [report, setReport] = useState<Report>(),
    [version, setVersion] = useState(0),
    [file, setFile] = useState<{ path: string; text: string; versions: number }>(),
    [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(""),
    [checking, setChecking] = useState(false),
    [checkResult, setCheckResult] = useState<{ verdict: string; score: Score; version: number }>(),
    [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [conversation, setConversation] = useState<Doc>(),
    [messages, setMessages] = useState<Msg[]>([]),
    [error, setError] = useState(""),
    [findings, setFindings] = useState<{ title: string; detail: string; basis: string }[]>([]);

  useEffect(() => {
    convert<RunSummary[]>("/runs").then(setRuns).catch(() => {});
  }, []);
  useEffect(() => {
    if (!target) return;
    setError("");
    setConversation(undefined);
    setMessages([]);
    setCheckResult(undefined);
    setEditing(false);
    convert<Report>("/runs/" + target.run)
      .then((r) => {
        setReport(r);
        setVersion((r.modes[target.mode as ModeId]?.edits || []).length);
      })
      .catch((e) => setError(message(e)));
  }, [target?.run, target?.mode]);
  useEffect(() => {
    if (!target || !report) return;
    convert(`/runs/${target.run}/findings?mode=${target.mode}&version=${version}`)
      .then(setFindings)
      .catch(() => setFindings([]));
    convert(`/runs/${target.run}/file?mode=${target.mode}&version=${version}`)
      .then((f) => {
        setFile(f);
        setDraft(f.text);
      })
      .catch((e) => setError(message(e)));
  }, [report, version]);

  const mode = target && report ? report.modes[target.mode as ModeId] : undefined;
  const score: Score | undefined = version && mode?.edits?.[version - 1] ? mode.edits[version - 1].score : mode?.score;
  const graph = report?.source.kind === "pinned";
  const context = useMemo(() => (target ? { conversion: target.run, mode: target.mode } : {}), [target]);

  const ask = async (text: string) => {
    if (!target || !text.trim()) return;
    setBusy(true);
    setError("");
    setQuestion("");
    try {
      let conv = conversation;
      if (!conv) {
        conv = await request<Doc>("/documents/conversation", "POST", {
          name: `Understand: ${report?.source.label} · ${LABEL[target.mode]}`.slice(0, 150),
          data: { context },
        });
        setConversation(conv);
      }
      const job = await request<Doc>("/conversation/" + conv.id + "/ask", "POST", { question: text, context });
      const poll = setInterval(() => request<Msg[]>("/conversation/" + conv!.id).then(setMessages).catch(() => {}), 1500);
      try {
        await waitJob(job);
      } finally {
        clearInterval(poll);
      }
      setMessages(await request<Msg[]>("/conversation/" + conv.id));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    if (!target) return;
    setChecking(true);
    setError("");
    try {
      const job = await convert<Doc>(`/runs/${target.run}/edit`, "POST", { mode: target.mode, text: draft, note: "edited in Understand & fix" });
      const edit = await waitJob(job);
      setCheckResult({ verdict: edit.verdict, score: edit.score, version: edit.version });
      const r = await convert<Report>("/runs/" + target.run);
      setReport(r);
      setVersion(edit.version);
      setEditing(false);
    } catch (e) {
      setError(message(e));
    } finally {
      setChecking(false);
    }
  };

  const pairs = useMemo(() => {
    const out: { user: Msg; without?: Msg; with?: Msg }[] = [];
    for (const m of messages) {
      if (m.data.role === "user") out.push({ user: m });
      else {
        const p = out.find((x) => x.user.data.pair === m.data.pair);
        if (p) p[m.data.mode as "with" | "without"] = m;
      }
    }
    return out.reverse();
  }, [messages]);

  return (
    <div className="lab sx-page">
      <div className="lab-plain">
        <b>IN PLAIN WORDS</b> A physics model is code. Here you can read it, ask a local AI what it means and what might be wrong, and correct it. Each question gets
        two answers side by side: the AI on its own, and the AI backed by the studio's robot knowledge graph, so you can see what grounding changes.
      </div>
      <span className="lab-eyebrow">UNDERSTAND &amp; FIX</span>
      <h1>Understand a model, find its errors, fix it</h1>

      <section className="sx-step">
        <h2>
          <span className="sx-n">1</span> Choose a model
        </h2>
        {runs.length === 0 ? (
          <p className="sx-note">
            No models yet.{" "}
            <button className="sx-link" onClick={toConvert}>
              Convert a robot first
            </button>
          </p>
        ) : (
          <div className="sx-picker">
            {runs.slice(0, 8).map((r) =>
              MODE_ORDER.filter((m) => r.modes[m]).map((m) => (
                <button key={r.id + m} className={target?.run === r.id && target.mode === m ? "on" : ""} onClick={() => setTarget({ run: r.id, mode: m })}>
                  <b>{LABEL[m]}</b>
                  <small>
                    {r.source} · {new Date(r.started).toLocaleString([], { dateStyle: "short", timeStyle: "short" })} · {r.modes[m].passed}/7 checks
                  </small>
                </button>
              )),
            )}
          </div>
        )}
      </section>

      {target && mode && (
        <>
          <section className="sx-step">
            <h2>
              <span className="sx-n">2</span> The model · {LABEL[target.mode]} · {report?.source.label}
            </h2>
            <p className="sx-verdict">{version && mode.edits?.[version - 1] ? mode.edits[version - 1].verdict : mode.verdict}</p>
            {score && (
              <div className="sx-chips">
                {score.criteria.map((c) => (
                  <span key={c.id} className={c.ok ? "ok" : "ko"} title={report?.criteria[c.id]}>
                    {c.ok ? <Check size={13} /> : <X size={13} />} {report?.criteria[c.id]}
                  </span>
                ))}
              </div>
            )}
            <div className={"sx-findings" + (findings.length ? "" : " clean")}>
              <b>{findings.length ? "What the checks found" : "The checks found no problem"}</b>
              <small>Measured by OpenModelica and compared with the robot file. No AI involved, so you can rely on this part.</small>
              {findings.length > 0 && (
                <ul>
                  {findings.map((f, i) => (
                    <li key={i}>
                      {f.title}
                      {f.basis !== "measured" && <em> ({f.basis})</em>}
                      {expert && f.detail && <code>{f.detail}</code>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {!mode.main_file ? (
              <p className="sx-note">This method produced no file, so there is nothing to read. {mode.error}</p>
            ) : (
              <>
                <div className="sx-codebar">
                  <span>
                    {(mode.edits || []).length > 0 && (
                      <select value={version} onChange={(e) => setVersion(+e.target.value)} aria-label="Version">
                        <option value={0}>Original (as generated)</option>
                        {(mode.edits || []).map((e) => (
                          <option key={e.version} value={e.version}>
                            Your edit {e.version} · {e.score.passed}/7 checks
                          </option>
                        ))}
                      </select>
                    )}
                    {expert && file && <code>{file.path}</code>}
                  </span>
                  {!editing ? (
                    <button className="lab-ghost" onClick={() => setEditing(true)}>
                      <Pencil size={14} /> Edit
                    </button>
                  ) : (
                    <span className="sx-edit-actions">
                      <button
                        className="lab-ghost"
                        onClick={() => {
                          setEditing(false);
                          setDraft(file?.text || "");
                        }}
                      >
                        <Undo2 size={14} /> Cancel
                      </button>
                      <button className="lab-primary" disabled={checking || draft === file?.text} onClick={check}>
                        <ShieldCheck size={14} /> {checking ? "Checking with OpenModelica…" : "Save as a new version and check"}
                      </button>
                    </span>
                  )}
                </div>
                {editing ? (
                  <textarea className="sx-code sx-editor" value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false} />
                ) : (
                  <Code text={file?.text || ""} />
                )}
                <p className="sx-note">
                  Edits are saved as a new version beside the original (never overwritten) and checked with the same seven checks as the comparison. Nothing
                  changes unless you click.
                </p>
                {checkResult && (
                  <div className={"sx-checked" + (checkResult.score.simulates ? " ok" : "")}>
                    <b>Version {checkResult.version} checked:</b> {checkResult.verdict}
                  </div>
                )}
              </>
            )}
          </section>

          {mode.main_file && (
            <section className="sx-step">
              <h2>
                <span className="sx-n">3</span> Ask about it
              </h2>
              <div className="sx-intents">
                {INTENTS.map(({ id, Icon, label, q }) => (
                  <button key={id} disabled={busy} onClick={() => ask(q)}>
                    <Icon size={18} /> {label}
                  </button>
                ))}
              </div>
              <form
                className="sx-ask"
                onSubmit={(e) => {
                  e.preventDefault();
                  ask(question);
                }}
              >
                <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Or ask your own question about this model…" rows={2} disabled={busy} />
                <button className="lab-primary" disabled={busy || question.trim().length < 3}>
                  <Send size={15} /> Ask
                </button>
              </form>
              {!graph && (
                <p className="sx-note">
                  This robot was uploaded, so it is not in the knowledge graph yet: only the "AI only" answer is available. The grounded side will say so instead of
                  guessing.
                </p>
              )}
              {busy && <p className="sx-note">The local AI is answering both sides (usually under a minute each)…</p>}
              {error && <p className="lab-error">{error}</p>}
              {pairs.map((p) => (
                <div key={p.user.id} className="sx-pair">
                  <div className="sx-q">{p.user.data.content}</div>
                  <div className="sx-answers">
                    <Answer m={p.without} title="AI on its own" Icon={Bot} expert={expert} />
                    <Answer m={p.with} title="AI + robot knowledge graph" Icon={Network} expert={expert} grounded />
                  </div>
                </div>
              ))}
              <p className="sx-note">
                Answers are explanations, not verdicts: check them against the sources shown. Suggested changes are never applied for you; edit the file above and let
                OpenModelica check it.{" "}
                <button className="sx-link" onClick={learn}>
                  <BookOpen size={13} /> Why compare with and without a knowledge graph?
                </button>
              </p>
            </section>
          )}
        </>
      )}
      {error && !mode && <p className="lab-error">{error}</p>}
    </div>
  );
}

function Code({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <pre className="sx-code" tabIndex={0}>
      {lines.map((l, i) => (
        <div key={i}>
          <span className="sx-ln">{i + 1}</span>
          {l || " "}
        </div>
      ))}
    </pre>
  );
}

function Answer({ m, title, Icon, expert, grounded }: { m?: Msg; title: string; Icon: typeof Bot; expert: boolean; grounded?: boolean }) {
  const d = m?.data || {};
  return (
    <div className={"sx-answer" + (grounded ? " grounded" : "")}>
      <header>
        <Icon size={16} /> {title}
        {d.seconds != null && <small>{Math.round(d.seconds)} s</small>}
      </header>
      {!m || d.status === "pending" ? (
        <p className="sx-muted">Thinking…</p>
      ) : d.status === "error" ? (
        <p className="sx-muted">{d.error}</p>
      ) : (
        <>
          <div className="sx-md">
            <Markdown>{String(d.content || "")}</Markdown>
          </div>
          {d.proposed_change && (
            <div className="sx-proposal">
              <b>Suggested change (review only)</b>
              <p>{d.proposed_change}</p>
            </div>
          )}
          {Array.isArray(d.parameter_changes) && d.parameter_changes.length > 0 && (
            <ul className="sx-params">
              {d.parameter_changes.map((c: any, i: number) => (
                <li key={i}>
                  <code>
                    {c.component}.{c.parameter} = {String(c.value)}
                  </code>{" "}
                  {c.justification}
                </li>
              ))}
            </ul>
          )}
          {(d.source_paths || []).length > 0 && (
            <small className="sx-src">
              Sources: {(d.source_paths as string[]).map((s) => (expert ? s : s.split("/").pop())).join(" · ")}
            </small>
          )}
        </>
      )}
    </div>
  );
}
