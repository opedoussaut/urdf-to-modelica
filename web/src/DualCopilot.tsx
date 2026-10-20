import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import {
  Plus,
  Search,
  ArrowUp,
  Download,
  Pencil,
  Trash2,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquare,
  Network,
  Cpu,
  Eraser,
  ChevronDown,
  Gauge,
  Ruler,
  FileCode2,
  Activity,
} from "lucide-react";
import { api } from "./types";
import { request, waitJob, message, type Doc, type Context } from "./studio";
import { useAudience } from "./audience";
import { partOfJoint } from "./robotParts";
import "./copilot.css";

const HISTORY_KEY = "kkh.chatHistoryOpen";
const storedHistoryOpen = () => {
  try {
    return localStorage.getItem(HISTORY_KEY) !== "0";
  } catch {
    return true;
  }
};

const SUGGESTIONS = [
  { icon: Ruler, simple: "How far can the elbow bend, and where does that number come from?", expert: "Explain the elbow joint axis and limits, with sources." },
  { icon: Activity, simple: "How do I know the arm follows its target well?", expert: "How can I validate follower tracking error?" },
  { icon: FileCode2, simple: "What does the computer model of the shoulder contain?", expert: "Review the selected Modelica component." },
  { icon: Gauge, simple: "Which settings are safe to change, and which are facts?", expert: "Which parameters are tunable design assumptions vs URDF-derived facts?" },
];

/** Groups conversations by recency for the history panel. */
function bucket(iso: string) {
  const d = new Date(iso),
    now = new Date();
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86400000);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : days < 7 ? "This week" : "Earlier";
}

export default function DualCopilot({ context }: { context: Context }) {
  const simple = useAudience() === "simple";
  const [items, setItems] = useState<Doc[]>([]),
    [conversation, setConversation] = useState<Doc>(),
    [messages, setMessages] = useState<Doc[]>([]),
    [search, setSearch] = useState(""),
    [question, setQuestion] = useState(""),
    [model, setModel] = useState(""),
    [models, setModels] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [picked, setPicked] = useState<Record<string, number[]>>({}),
    [historyOpen, setHistoryOpen] = useState(storedHistoryOpen),
    [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null),
    input = useRef<HTMLTextAreaElement>(null);
  const toggleHistory = () =>
    setHistoryOpen((o) => {
      try {
        localStorage.setItem(HISTORY_KEY, o ? "0" : "1");
      } catch {}
      return !o;
    });
  const refresh = () => request<Doc[]>("/documents/conversation?search=" + encodeURIComponent(search)).then(setItems);
  useEffect(() => {
    refresh().catch((e) => setError(message(e)));
  }, [search]);
  useEffect(() => {
    api<any>("/api/health")
      .then((h) => {
        setModels(h.ollama.models || []);
        setModel((m) => m || h.ollama.default_model || "");
      })
      .catch((e) => setError(message(e)));
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy]);
  const open = async (item: Doc) => {
    setConversation(item);
    setMessages(await request("/conversation/" + item.id));
  };
  const create = async () => {
    const item = await request<Doc>("/documents/conversation", "POST", {
      name: "Engineering conversation",
      data: { context },
    });
    await open(item);
    await refresh();
    return item;
  };
  const startNew = () => {
    // A conversation is only stored once the first question is asked.
    setConversation(undefined);
    setMessages([]);
    setError("");
    input.current?.focus();
  };
  useEffect(() => {
    let disposed = false;
    request<Doc[]>("/documents/conversation").then(async (rows) => {
      if (!disposed && rows[0]) await open(rows[0]);
    });
    return () => {
      disposed = true;
    };
  }, []);
  const remove = async (item: Doc) => {
    await request("/record/" + item.id + "?version=" + item.version + "&confirmed=true", "DELETE");
    if (conversation?.id === item.id) {
      setConversation(undefined);
      setMessages([]);
    }
  };
  const removeOne = async (item: Doc) => {
    if (!confirm(`Delete “${item.name}” from your history?`)) return;
    try {
      await remove(item);
      await refresh();
    } catch (e) {
      setError(message(e));
    }
  };
  const clearAll = async () => {
    const all = await request<Doc[]>("/documents/conversation");
    if (!all.length) return;
    if (!confirm(`Clear the whole conversation history (${all.length} conversation${all.length > 1 ? "s" : ""})? They disappear from the list; exports you already saved are not affected.`))
      return;
    setBusy(true);
    setError("");
    try {
      for (const item of all) await remove(item);
      setConversation(undefined);
      setMessages([]);
      setSearch("");
      await refresh();
    } catch (e) {
      setError(message(e));
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  };
  const propose = async (answer: Doc, indices: number[]) => {
    if (!context.model || !conversation || !indices.length) return;
    setBusy(true);
    setError("");
    try {
      await request("/model/" + context.model + "/propose", "POST", { message: answer.id, indices });
      setMessages(await request("/conversation/" + conversation.id));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const ask = async (text = question) => {
    if (text.trim().length < 3 || busy) return;
    setBusy(true);
    setError("");
    const prompt = text;
    setQuestion("");
    let selected = conversation;
    try {
      if (!selected) {
        selected = await request<Doc>("/documents/conversation", "POST", {
          name: prompt.length > 60 ? prompt.slice(0, 57).trimEnd() + "…" : prompt,
          data: { context },
        });
        setConversation(selected);
        setMessages([]);
      }
      const job = await request("/conversation/" + selected.id + "/ask", "POST", { question: prompt, model, context });
      const interval = setInterval(
        () =>
          request<Doc[]>("/conversation/" + selected!.id)
            .then(setMessages)
            .catch(() => {}),
        1500,
      );
      try {
        await waitJob(job);
      } finally {
        clearInterval(interval);
      }
      setMessages(await request("/conversation/" + selected.id));
      await refresh();
    } catch (e) {
      setError(message(e));
      if (selected) setMessages(await request("/conversation/" + selected.id));
    } finally {
      setBusy(false);
    }
  };

  const sides = simple
    ? {
        without: { title: "AI on its own", sub: "Reads the robot files only" },
        with: { title: "AI + engineering knowledge", sub: "Also checks the knowledge graph" },
      }
    : {
        without: { title: "Without ontology", sub: "Engineering sources + shared context" },
        with: { title: "With ontology", sub: "Same foundation + GraphDB evidence" },
      };
  const pairIds = [...new Set(messages.map((m) => m.data.pair || m.id))];
  const groups: [string, Doc[]][] = [];
  for (const item of items) {
    const b = bucket(item.updated);
    const g = groups.find(([k]) => k === b);
    g ? g[1].push(item) : groups.push([b, [item]]);
  }
  const part = partOfJoint(context.selected);

  return (
    <div className="lab cp">
      <header className="cp-head">
        <div>
          <span className="lab-eyebrow">STEP 5 · DECIDE</span>
          <h1>AI assistant</h1>
          <p>
            {simple
              ? "Ask anything about the arm. You get two answers side by side - one from the AI alone, one backed by the studio's engineering knowledge - so you can see the difference."
              : "One question, the same local model, two answers: without and with ontology grounding. Compare the evidence."}
          </p>
        </div>
        <div className="cp-head-actions">
          <span className="cp-local">
            <Cpu size={13} /> Runs on this computer
          </span>
          <button className="cp-btn" onClick={toggleHistory} aria-pressed={historyOpen} title={historyOpen ? "Hide history" : "Show history"}>
            {historyOpen ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
            {historyOpen ? "Hide history" : "History"}
            {!historyOpen && items.length > 0 && <span className="cp-count">{items.length}</span>}
          </button>
          <button className="lab-primary" disabled={busy} onClick={startNew}>
            <Plus size={15} /> New conversation
          </button>
        </div>
      </header>

      <div className={"cp-grid" + (historyOpen ? "" : " closed")}>
        {historyOpen && (
          <aside className="cp-history" aria-label="Conversation history">
            <div className="cp-history-top">
              <b>History</b>
              <button className="cp-icon" onClick={toggleHistory} aria-label="Hide history" title="Hide history">
                <PanelLeftClose size={15} />
              </button>
            </div>
            <label className="cp-search">
              <Search size={14} />
              <input aria-label="Search conversation history" placeholder="Search conversations" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <div className="cp-history-list">
              {groups.map(([label, rows]) => (
                <div key={label}>
                  <span className="cp-bucket">{label}</span>
                  {rows.map((item) => (
                    <div key={item.id} className={"cp-item" + (conversation?.id === item.id ? " active" : "")}>
                      <button disabled={busy} onClick={() => open(item).catch((e) => setError(message(e)))} title={item.name}>
                        <MessageSquare size={14} />
                        <span>
                          <strong>{item.name}</strong>
                          <small>
                            {new Date(item.updated).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
                            {item.data.recovered_from ? " · recovered" : ""}
                          </small>
                        </span>
                      </button>
                      <button className="cp-item-del" disabled={busy} aria-label={`Delete ${item.name}`} title="Delete" onClick={() => removeOne(item)}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              ))}
              {!items.length && <p className="cp-none">{search ? "No conversation matches." : "No conversations yet."}</p>}
            </div>
            <button className="cp-clear" disabled={busy || !items.length} onClick={clearAll}>
              <Eraser size={14} /> Clear history
            </button>
          </aside>
        )}

        <section className="cp-main">
          <div className="cp-bar">
            <div className="cp-bar-title">
              <strong>{conversation?.name || "New conversation"}</strong>
              <span>
                Context: {simple ? part?.name || context.selected : `joint ${context.selected}`}
                {context.model ? (simple ? " · your edited model" : ` · revision ${context.model_revision?.slice(0, 8) || "-"}`) : simple ? " · reference model" : " · generated baseline"}
              </span>
            </div>
            <label className="cp-model" title="Local language model used for both answers">
              <Cpu size={13} />
              <select aria-label="Local model" value={model} disabled={busy} onChange={(e) => setModel(e.target.value)}>
                {[...new Set([model, ...models])].filter(Boolean).map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
              <ChevronDown size={13} />
            </label>
            {conversation && (
              <div className="cp-bar-tools">
                <button
                  className="cp-icon"
                  aria-label="Rename conversation"
                  title="Rename"
                  disabled={busy}
                  onClick={async () => {
                    const name = prompt("Conversation name", conversation.name);
                    if (!name) return;
                    try {
                      setConversation(await request("/record/" + conversation.id, "PATCH", { name, version: conversation.version }));
                      refresh();
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                >
                  <Pencil size={14} />
                </button>
                <a className="cp-icon" title="Export as Markdown" href={"/api/workbench/conversation/" + conversation.id + "/export?format=md"}>
                  <Download size={14} />
                </a>
                <button className="cp-icon danger" aria-label="Delete conversation" title="Delete" disabled={busy} onClick={() => removeOne(conversation)}>
                  <Trash2 size={14} />
                </button>
              </div>
            )}
          </div>

          <div className="cp-thread">
            {!messages.length && !busy && (
              <div className="cp-empty">
                <div className="cp-empty-icon">
                  <Sparkles size={22} />
                </div>
                <h2>What would you like to know about the arm?</h2>
                <p>Every question gets two answers from the same local AI, so you can judge what the engineering knowledge adds.</p>
                <div className="cp-legend">
                  <div className="without">
                    <MessageSquare size={16} />
                    <span>
                      <b>{sides.without.title}</b>
                      {sides.without.sub}
                    </span>
                  </div>
                  <div className="with">
                    <Network size={16} />
                    <span>
                      <b>{sides.with.title}</b>
                      {sides.with.sub}
                    </span>
                  </div>
                </div>
                <div className="cp-suggest">
                  {SUGGESTIONS.map((s) => {
                    const q = simple ? s.simple : s.expert;
                    return (
                      <button key={q} onClick={() => ask(q)} disabled={busy}>
                        <s.icon size={16} />
                        <span>{q}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {pairIds.map((id) => {
              const pair = messages.filter((m) => (m.data.pair || m.id) === id),
                user = pair.find((m) => m.data.role === "user");
              return (
                <section key={id} className="cp-turn">
                  {user && (
                    <div className="cp-q">
                      <div className="cp-q-bubble">
                        <p>{String(user.data.content)}</p>
                        <small>
                          {new Date(user.created).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
                          {user.data.context?.selected && ` · ${simple ? partOfJoint(user.data.context.selected)?.name || user.data.context.selected : `joint ${user.data.context.selected}`}`}
                          {!simple && ` · revision ${user.data.context?.model_revision?.slice(0, 8) || "baseline"} · trajectory ${user.data.context?.trajectory?.slice(0, 8) || "none"}`}
                        </small>
                      </div>
                      <span className="cp-avatar">You</span>
                    </div>
                  )}
                  <div className="cp-answers">
                    {(["without", "with"] as const).map((mode) => {
                      const answer = pair.find((m) => m.data.role === "assistant" && (m.data.mode === mode || (mode === "with" && m.data.mode === "grounded")));
                      return (
                        <article key={mode} className={"cp-answer " + mode}>
                          <header>
                            <span className="cp-side">
                              {mode === "with" ? <Network size={14} /> : <MessageSquare size={14} />}
                              {sides[mode].title}
                            </span>
                            {answer && answer.data.status !== "pending" && (
                              <span className="cp-meta">
                                {answer.data.seconds ? `${answer.data.seconds.toFixed(1)} s` : answer.data.status || "recovered"}
                                {!simple && ` · ${answer.data.settings?.model || "historical model"}`}
                              </span>
                            )}
                          </header>
                          {answer ? (
                            <Answer answer={answer} simple={simple} context={context} busy={busy} picked={picked} setPicked={setPicked} propose={propose} />
                          ) : (
                            <Thinking busy={busy} />
                          )}
                        </article>
                      );
                    })}
                  </div>
                </section>
              );
            })}
            <div ref={bottom} />
          </div>

          {error && (
            <div className="cp-error" role="alert">
              {error}
            </div>
          )}
          <form
            className="cp-composer"
            onSubmit={(e) => {
              e.preventDefault();
              ask();
            }}
          >
            <textarea
              ref={input}
              aria-label="Your question"
              placeholder={simple ? "Ask about the arm, a part, the model or a simulation…" : "Ask both copilots about the selected robot, joint, model or run…"}
              value={question}
              rows={2}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask();
                }
              }}
              maxLength={1500}
            />
            <div className="cp-composer-foot">
              <span>{simple ? "Enter to send · Shift+Enter for a new line · the AI suggests, you decide" : "Enter to send · same model · temperature 0 · seed 42 · proposals require review"}</span>
              <button className="cp-send" disabled={busy || question.trim().length < 3} aria-label="Ask both">
                {busy ? <span className="cp-dots"><i /><i /><i /></span> : <ArrowUp size={17} />}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

function Thinking({ busy }: { busy: boolean }) {
  return busy ? (
    <p className="cp-thinking">
      <span className="cp-dots">
        <i />
        <i />
        <i />
      </span>
      Thinking locally…
    </p>
  ) : (
    <p className="cp-muted">No answer was recorded for this side.</p>
  );
}

function Answer({
  answer,
  simple,
  context,
  busy,
  picked,
  setPicked,
  propose,
}: {
  answer: Doc;
  simple: boolean;
  context: Context;
  busy: boolean;
  picked: Record<string, number[]>;
  setPicked: React.Dispatch<React.SetStateAction<Record<string, number[]>>>;
  propose: (answer: Doc, indices: number[]) => void;
}) {
  const d = answer.data;
  if (d.status === "pending") return <Thinking busy />;
  if (d.error) return <p className="cp-error">{d.error}</p>;
  const chosen = picked[answer.id] ?? [];
  return (
    <>
      <div className="cp-md">
        <Markdown>{typeof d.content === "string" ? d.content.split("</think>").at(-1)! : JSON.stringify(d.content, null, 2)}</Markdown>
      </div>
      {d.review_status && <p className="cp-note">{d.review_status}</p>}
      {d.source_paths?.length > 0 && (
        <div className="cp-sources">
          <span>Sources</span>
          {d.source_paths.map((p: string) => (
            <code key={p}>{p}</code>
          ))}
        </div>
      )}
      {d.proposed_change && (
        <details className="cp-details">
          <summary>Proposed change · review only</summary>
          <pre>{d.proposed_change}</pre>
          <p className="cp-note">Copy into a working revision in the Model editor for explicit review, compiler validation and acceptance.</p>
        </details>
      )}
      {d.parameter_changes?.length > 0 && (
        <div className="cp-proposal">
          <strong>{simple ? "Suggested setting changes · tick the ones to try" : "Structured parameter proposal · select changes to review"}</strong>
          <table className="cp-table">
            <thead>
              <tr>
                <th></th>
                <th>{simple ? "Setting" : "Instance.parameter (file)"}</th>
                <th>Current → proposed</th>
                <th>Why</th>
                <th>{simple ? "Allowed?" : "Applicability & bounds"}</th>
              </tr>
            </thead>
            <tbody>
              {d.parameter_changes.map((c: any, i: number) => {
                const applicable = c.structurally_valid && !String(c.file || "").startsWith("Arms/");
                const reason = applicable
                  ? c.check
                  : String(c.file || "").startsWith("Arms/") && c.structurally_valid
                    ? "URDF-derived source fact; only tunable design parameters (Control package) may be proposed"
                    : c.check;
                return (
                  <tr key={i} className={applicable ? "" : "rejected"}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${c.component}.${c.parameter}`}
                        disabled={!applicable || !!d.proposal_revision}
                        checked={applicable && chosen.includes(i)}
                        onChange={(e) =>
                          setPicked((old) => ({
                            ...old,
                            [answer.id]: e.target.checked ? [...(old[answer.id] ?? []), i] : (old[answer.id] ?? []).filter((x) => x !== i),
                          }))
                        }
                      />
                    </td>
                    <td>
                      <code>
                        {c.component}.{c.parameter}
                      </code>
                      {!simple && <small> {c.file || ""}</small>}
                    </td>
                    <td>
                      {c.current ?? "-"} → <strong>{c.value}</strong>
                    </td>
                    <td>{c.justification}</td>
                    <td>
                      {applicable ? "✓ " : "✗ not applicable: "}
                      {reason}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {d.proposal_revision ? (
            <p className="cp-note">
              Proposal revision {d.proposal_revision.slice(0, 8)} created (status “AI proposal”, not accepted). Next: validate → simulate → compare → accept or roll back.
            </p>
          ) : (
            <button
              className="lab-primary"
              disabled={!context.model || busy || !chosen.length}
              title={context.model ? "Creates an isolated, unaccepted 'AI proposal' revision with the selected changes" : "Open an editable model in the Model editor first"}
              onClick={() => propose(answer, chosen)}
            >
              Create AI-proposal revision ({chosen.length} selected)
            </button>
          )}
          <p className="cp-note">
            Checks: instance exists in the supplied source, numeric parameter, value differs, within Modelica-declared bounds, and only tunable design parameters.
            Nothing is accepted automatically.
          </p>
        </div>
      )}
      {d.assumptions?.length > 0 && (
        <details className="cp-details">
          <summary>Assumptions & limitations</summary>
          <ul>
            {d.assumptions.map((s: string) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </details>
      )}
      {d.recovery_note && <p className="cp-note">{d.recovery_note}</p>}
      {!simple && (
        <details className="cp-details">
          <summary>Read-only tool trace & context</summary>
          <pre>{JSON.stringify({ trace: d.trace || d.evidence, context: d.context, settings: d.settings }, null, 2)}</pre>
        </details>
      )}
    </>
  );
}
