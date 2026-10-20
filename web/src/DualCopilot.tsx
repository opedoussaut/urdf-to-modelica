import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import {
  Plus,
  Search,
  Send,
  Download,
  Pencil,
  Trash2,
  Sparkles,
} from "lucide-react";
import { api } from "./types";
import { request, waitJob, message, type Doc, type Context } from "./studio";
export default function DualCopilot({ context }: { context: Context }) {
  const [items, setItems] = useState<Doc[]>([]),
    [conversation, setConversation] = useState<Doc>(),
    [messages, setMessages] = useState<Doc[]>([]),
    [search, setSearch] = useState(""),
    [question, setQuestion] = useState(""),
    [model, setModel] = useState(""),
    [models, setModels] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [picked, setPicked] = useState<Record<string, number[]>>({}),
    [error, setError] = useState("");
  const refresh = () =>
    request<Doc[]>(
      "/documents/conversation?search=" + encodeURIComponent(search),
    ).then(setItems);
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
  useEffect(() => {
    let disposed = false;
    request<Doc[]>("/documents/conversation").then(async (rows) => {
      if (!disposed && rows[0]) await open(rows[0]);
    });
    return () => {
      disposed = true;
    };
  }, []);
  const propose = async (answer: Doc, indices: number[]) => {
    if (!context.model || !conversation || !indices.length) return;
    setBusy(true);
    setError("");
    try {
      await request("/model/" + context.model + "/propose", "POST", {
        message: answer.id,
        indices,
      });
      setMessages(await request("/conversation/" + conversation.id));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const ask = async () => {
    if (question.trim().length < 3 || busy) return;
    setBusy(true);
    setError("");
    const prompt = question;
    setQuestion("");
    let selected = conversation;
    try {
      if (!selected) selected = await create();
      const job = await request(
        "/conversation/" + selected.id + "/ask",
        "POST",
        { question: prompt, model, context },
      );
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
  const pairIds = [...new Set(messages.map((m) => m.data.pair || m.id))];
  return (
    <div className="wb-workspace">
      <div className="wb-title">
        <div>
          <span className="wb-eyebrow">STEP 5 · DECIDE</span>
          <h1>AI assistant</h1>
          <p>
            One question. The same local model. A visible difference in
            evidence.
          </p>
        </div>
        <span className="wb-badge">
          <Sparkles size={13} /> OLLAMA · LOCAL ONLY
        </span>
      </div>
      <div className="wb-chat-grid">
        <aside className="wb-card wb-history">
          <button
            className="wb-primary"
            disabled={busy}
            onClick={() => create().catch((e) => setError(message(e)))}
          >
            <Plus size={15} />
            New conversation
          </button>
          <label className="wb-search">
            <Search size={14} />
            <input
              aria-label="Search conversation history"
              placeholder="Search history…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          {items.map((item) => (
            <button
              className={conversation?.id === item.id ? "active" : ""}
              key={item.id}
              disabled={busy}
              onClick={() => open(item).catch((e) => setError(message(e)))}
            >
              <strong>{item.name}</strong>
              <small>
                {new Date(item.updated).toLocaleString()}
                {item.data.recovered_from ? " · recovered" : ""}
              </small>
            </button>
          ))}
          <p className="wb-footnote">
            SQLite history persists through refresh and restart. Earlier audit
            answers are recovered where available; missing questions are
            explicitly labeled.
          </p>
        </aside>
        <section className="wb-chat-main">
          <div className="wb-toolbar wb-card">
            <strong>
              {conversation?.name || "New engineering conversation"}
            </strong>
            <select
              aria-label="Shared local model"
              value={model}
              disabled={busy}
              onChange={(e) => setModel(e.target.value)}
            >
              {[...new Set([model, ...models])].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
            {conversation && (
              <>
                <button
                  aria-label="Rename conversation"
                  disabled={busy}
                  onClick={async () => {
                    const name = prompt("Conversation name", conversation.name);
                    if (!name) return;
                    try {
                      setConversation(
                        await request("/record/" + conversation.id, "PATCH", {
                          name,
                          version: conversation.version,
                        }),
                      );
                      refresh();
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                >
                  <Pencil size={14} />
                </button>
                <a
                  className="wb-button"
                  href={
                    "/api/workbench/conversation/" +
                    conversation.id +
                    "/export?format=md"
                  }
                >
                  <Download size={14} />
                  MD
                </a>
                <a
                  className="wb-button"
                  href={
                    "/api/workbench/conversation/" +
                    conversation.id +
                    "/export?format=json"
                  }
                >
                  JSON
                </a>
                <button
                  aria-label="Delete conversation"
                  disabled={busy}
                  onClick={async () => {
                    if (!confirm("Delete this conversation from your history?"))
                      return;
                    try {
                      await request(
                        "/record/" +
                          conversation.id +
                          "?version=" +
                          conversation.version +
                          "&confirmed=true",
                        "DELETE",
                      );
                      setConversation(undefined);
                      setMessages([]);
                      refresh();
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </div>
          <div className="wb-dual-head">
            <div>
              <span className="wb-mode-dot plain" />
              <h2>Without ontology</h2>
              <p>Engineering source + shared context</p>
            </div>
            <div>
              <span className="wb-mode-dot grounded" />
              <h2>With ontology</h2>
              <p>Same foundation + GraphDB evidence</p>
            </div>
          </div>
          {!messages.length && (
            <div className="wb-chat-empty">
              <Sparkles size={28} />
              <h2>Ask an engineering question</h2>
              <p>
                Both sides receive the same source files, selected revision and
                simulation context. Only the right side retrieves ontology
                evidence.
              </p>
              <div className="wb-toolbar">
                {[
                  "Explain the elbow joint axis and limits.",
                  "How can I validate follower tracking error?",
                  "Review the selected Modelica component.",
                ].map((q) => (
                  <button key={q} onClick={() => setQuestion(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="wb-conversation">
            {pairIds.map((id) => {
              const pair = messages.filter((m) => (m.data.pair || m.id) === id),
                user = pair.find((m) => m.data.role === "user");
              return (
                <section key={id}>
                  {user && (
                    <div className="wb-user-message">
                      <span>
                        YOU · {new Date(user.created).toLocaleString()}
                      </span>
                      <p>{String(user.data.content)}</p>
                      <small>
                        Joint: {user.data.context?.selected || "none"} ·
                        revision:{" "}
                        {user.data.context?.model_revision?.slice(0, 8) ||
                          "baseline"}{" "}
                        · trajectory:{" "}
                        {user.data.context?.trajectory?.slice(0, 8) || "none"}
                      </small>
                    </div>
                  )}
                  <div className="wb-dual-answer">
                    {["without", "with"].map((mode) => {
                      const answer = pair.find(
                        (m) =>
                          m.data.role === "assistant" &&
                          (m.data.mode === mode ||
                            (mode === "with" && m.data.mode === "grounded")),
                      );
                      return (
                        <article key={mode} className={mode}>
                          {answer ? (
                            <>
                              <div className="wb-answer-meta">
                                {answer.data.status || "recovered"}{" "}
                                {answer.data.seconds
                                  ? `· ${answer.data.seconds.toFixed(1)} s`
                                  : ""}{" "}
                                ·{" "}
                                {answer.data.settings?.model ||
                                  "historical local model"}
                              </div>
                              {answer.data.status === "pending" ? (
                                <p className="wb-muted">
                                  Local model is generating…
                                </p>
                              ) : answer.data.error ? (
                                <p className="wb-error">{answer.data.error}</p>
                              ) : (
                                <Markdown>
                                  {typeof answer.data.content === "string"
                                    ? answer.data.content
                                        .split("</think>")
                                        .at(-1)!
                                    : JSON.stringify(
                                        answer.data.content,
                                        null,
                                        2,
                                      )}
                                </Markdown>
                              )}
                              {answer.data.review_status && (
                                <p className="wb-footnote">
                                  {answer.data.review_status}
                                </p>
                              )}
                              {answer.data.source_paths?.length > 0 && (
                                <p className="wb-footnote">
                                  Sources:{" "}
                                  {answer.data.source_paths.join(" · ")}
                                </p>
                              )}
                              {answer.data.proposed_change && (
                                <details>
                                  <summary>
                                    Proposed change · review only
                                  </summary>
                                  <pre>{answer.data.proposed_change}</pre>
                                  <p className="wb-footnote">
                                    Copy into a working revision in the Modelica
                                    editor for explicit review, compiler
                                    validation and acceptance.
                                  </p>
                                </details>
                              )}
                              {answer.data.parameter_changes?.length > 0 && (
                                <div className="wb-proposal">
                                  <strong>Structured parameter proposal · select changes to review</strong>
                                  <table className="wb-table">
                                    <thead>
                                      <tr>
                                        <th></th>
                                        <th>Instance.parameter (file)</th>
                                        <th>Current → proposed</th>
                                        <th>Justification</th>
                                        <th>Applicability & bounds</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {answer.data.parameter_changes.map(
                                        (c: any, i: number) => {
                                          const applicable =
                                            c.structurally_valid &&
                                            !String(c.file || "").startsWith("Arms/");
                                          const reason = applicable
                                            ? c.check
                                            : String(c.file || "").startsWith("Arms/") && c.structurally_valid
                                              ? "URDF-derived source fact; only tunable design parameters (Control package) may be proposed"
                                              : c.check;
                                          return (
                                            <tr key={i} className={applicable ? "" : "wb-rejected"}>
                                              <td>
                                                <input
                                                  type="checkbox"
                                                  aria-label={`Select ${c.component}.${c.parameter}`}
                                                  disabled={!applicable || !!answer.data.proposal_revision}
                                                  checked={applicable && (picked[answer.id] ?? []).includes(i)}
                                                  onChange={(e) =>
                                                    setPicked((old) => ({
                                                      ...old,
                                                      [answer.id]: e.target.checked
                                                        ? [...(old[answer.id] ?? []), i]
                                                        : (old[answer.id] ?? []).filter((x) => x !== i),
                                                    }))
                                                  }
                                                />
                                              </td>
                                              <td>
                                                <code>
                                                  {c.component}.{c.parameter}
                                                </code>
                                                <small> {c.file || ""}</small>
                                              </td>
                                              <td>
                                                {c.current ?? "—"} → <strong>{c.value}</strong>
                                              </td>
                                              <td>{c.justification}</td>
                                              <td>
                                                {applicable ? "✓ " : "✗ not applicable: "}
                                                {reason}
                                              </td>
                                            </tr>
                                          );
                                        },
                                      )}
                                    </tbody>
                                  </table>
                                  {answer.data.proposal_revision ? (
                                    <p className="wb-footnote">
                                      Proposal revision{" "}
                                      {answer.data.proposal_revision.slice(0, 8)}{" "}
                                      created (status “AI proposal”, not accepted). Next: Leader–Follower →
                                      Validate candidate → Simulate → compare → accept or roll back.
                                    </p>
                                  ) : (
                                    <button
                                      className="wb-primary"
                                      disabled={
                                        !context.model ||
                                        busy ||
                                        !(picked[answer.id] ?? []).length
                                      }
                                      title={
                                        context.model
                                          ? "Creates an isolated, unaccepted 'AI proposal' revision with the selected changes"
                                          : "Open an editable model in the Modelica editor first"
                                      }
                                      onClick={() => propose(answer, picked[answer.id] ?? [])}
                                    >
                                      Create AI-proposal revision ({(picked[answer.id] ?? []).length} selected)
                                    </button>
                                  )}
                                  <p className="wb-footnote">
                                    Checks: instance exists in the supplied source, numeric parameter, value
                                    differs, within Modelica-declared bounds, and only tunable design parameters.
                                    Engineering correctness still requires your review, OpenModelica validation
                                    and simulation; nothing is accepted automatically.
                                  </p>
                                </div>
                              )}
                              {answer.data.assumptions?.length > 0 && (
                                <details>
                                  <summary>Assumptions & limitations</summary>
                                  <ul>
                                    {answer.data.assumptions.map(
                                      (s: string) => (
                                        <li key={s}>{s}</li>
                                      ),
                                    )}
                                  </ul>
                                </details>
                              )}
                              {answer.data.recovery_note && (
                                <p className="wb-footnote">
                                  {answer.data.recovery_note}
                                </p>
                              )}
                              <details>
                                <summary>
                                  Read-only tool trace & context
                                </summary>
                                <pre>
                                  {JSON.stringify(
                                    {
                                      trace:
                                        answer.data.trace ||
                                        answer.data.evidence,
                                      context: answer.data.context,
                                      settings: answer.data.settings,
                                    },
                                    null,
                                    2,
                                  )}
                                </pre>
                              </details>
                            </>
                          ) : (
                            <p className="wb-muted">
                              {busy
                                ? "Waiting for persisted response…"
                                : "No response recorded for this side."}
                            </p>
                          )}
                        </article>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
          {error && (
            <div className="wb-error" role="alert">
              {error}
            </div>
          )}
          <form
            className="wb-composer wb-card"
            onSubmit={(e) => {
              e.preventDefault();
              ask();
            }}
          >
            <textarea
              aria-label="Shared engineering question"
              placeholder="Ask both copilots about the selected robot, joint, model or run…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              maxLength={1500}
            />
            <div>
              <span>
                Same model · temperature 0 · seed 42 · proposals require review
              </span>
              <button
                className="wb-primary"
                disabled={busy || question.trim().length < 3}
              >
                <Send size={15} />
                {busy ? "Generating both…" : "Ask both"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
