import { useMemo, useState } from "react";
import { ArrowRight, BookOpen, ChevronRight, Search } from "lucide-react";
import { useAudience } from "../audience";
import { AI_EXAMPLE, AI_HOW, AI_INPUTS, AI_LIMITS, AI_SOURCES, FLOW, GLOSSARY, MEASURED, RATIONALE } from "./guideContent";
import "./guide.css";

const SECTIONS = [
  ["flow", "The flow, step by step"],
  ["ai", "What the AI receives"],
  ["why", "Why it is built this way"],
  ["measured", "What has been measured"],
  ["terms", "Terminology"],
] as const;

/** Guide: what the simplified studio does, in order, the reasons behind each choice, and the words it uses. */
export default function Guide({ go, learn }: { go: (page: "repair") => void; learn: () => void }) {
  const expert = useAudience() === "expert";
  const [q, setQ] = useState("");
  const jump = (id: string) => document.getElementById("gd-" + id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const terms = useMemo(() => {
    const s = q.trim().toLowerCase();
    return GLOSSARY.map((g) => ({ ...g, terms: g.terms.filter(([t, d]) => !s || t.toLowerCase().includes(s) || d.toLowerCase().includes(s)) })).filter((g) => g.terms.length);
  }, [q]);
  const nTerms = GLOSSARY.reduce((n, g) => n + g.terms.length, 0);

  return (
    <div className="lab sx-page gd">
      <aside className="gd-toc" aria-label="Contents">
        <span className="gd-toc-h">Guide</span>
        {SECTIONS.map(([id, label]) => (
          <button key={id} onClick={() => jump(id)}>
            {label}
          </button>
        ))}
        <button className="gd-toc-atlas" onClick={learn}>
          <BookOpen size={14} /> Physical AI Atlas
        </button>
      </aside>

      <div className="gd-main">
        <header className="gd-head">
          <span className="lab-eyebrow">GUIDE · HOW THE STUDIO WORKS</span>
          <h1>From a robot file to an approved physics model</h1>
          <p className="sx-lead">
            A deterministic converter turns a robot's public description file into a Modelica physics model. OpenModelica and independent references list
            what is wrong with it. Two AI methods then try to repair it under identical conditions, one of them with Modelica engineering knowledge,
            and an engineer decides what is kept. This guide explains each stage, why it is done that way, and the words used along the way.
          </p>
          <ol className="gd-strip" aria-label="The flow">
            {FLOW.map((s, i) => (
              <li key={s.id}>
                <button onClick={() => jump(s.id)}>
                  <span className="sx-n">{s.n}</span>
                  {s.title}
                </button>
                {i < FLOW.length - 1 && <ChevronRight size={16} className="gd-strip-arrow" />}
              </li>
            ))}
          </ol>
        </header>

        <section id="gd-flow" className="gd-section">
          <h2>The flow, step by step</h2>
          {FLOW.map((s) => (
            <article key={s.id} id={"gd-" + s.id} className="gd-step">
              <header>
                <span className="sx-n">{s.n}</span>
                <h3>{s.title}</h3>
                <button className="sx-link" onClick={() => go(s.page)}>
                  Open the pipeline <ArrowRight size={14} />
                </button>
              </header>
              <dl>
                <div>
                  <dt>You do</dt>
                  <dd>{s.doWhat}</dd>
                </div>
                <div>
                  <dt>What happens</dt>
                  <dd>{s.happens}</dd>
                </div>
                <div>
                  <dt>You get</dt>
                  <dd>{s.get}</dd>
                </div>
                <div className="gd-why">
                  <dt>Why</dt>
                  <dd>{s.why}</dd>
                </div>
              </dl>
              {expert && s.code && <p className="gd-code">Under the hood: {s.code}</p>}
            </article>
          ))}
        </section>

        <section id="gd-ai" className="gd-section">
          <h2>What the AI receives, and how it uses it</h2>
          <p className="gd-intro">
            In the repair stage, the AI never sees the whole project and never learns anything permanently. For each repair it receives one request
            containing the items below, answers with proposed edits, and those edits are checked. The two methods differ in one thing only: the
            Modelica reference material.
          </p>
          <table className="gd-table">
            <thead>
              <tr>
                <th>In the request</th>
                <th>AI only</th>
                <th>AI + Modelica knowledge</th>
                <th>What it is</th>
              </tr>
            </thead>
            <tbody>
              {AI_INPUTS.map((r) => (
                <tr key={r.what} className={r.aiOnly !== r.aiAssets ? "gd-diff" : ""}>
                  <td>
                    <b>{r.what}</b>
                  </td>
                  <td>{r.aiOnly ? "yes" : "no"}</td>
                  <td>{r.aiAssets ? "yes" : "no"}</td>
                  <td>{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Where the reference material comes from</h3>
          <p className="gd-intro">Only sources with a known version and licence, all already on this computer (nothing downloaded). The converter's own library and the project's generated models are excluded on purpose, so the AI cannot copy an answer.</p>
          <div className="gd-why-grid">
            {AI_SOURCES.map((x) => (
              <div key={x.name} className="gd-card">
                <b>{x.name}</b>
                <p>{x.what}</p>
                <small>
                  Version {x.version} · licence {x.licence}
                </small>
              </div>
            ))}
          </div>

          <h3>How the AI uses it, in simple terms</h3>
          <ol className="gd-how">
            {AI_HOW.map((x) => (
              <li key={x.title}>
                <b>{x.title}</b>
                <p>{x.text}</p>
              </li>
            ))}
          </ol>

          <div className="gd-card gd-example">
            <b>A real example</b>
            <p>
              <i>Finding:</i> {AI_EXAMPLE.finding}
            </p>
            <p>
              <i>Retrieved:</i> {AI_EXAMPLE.retrieved}
            </p>
            <p>
              <i>How it helps:</i> {AI_EXAMPLE.use}
            </p>
          </div>

          <h3>Limits to keep in mind</h3>
          <ul className="gd-limits">
            {AI_LIMITS.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>

        <section id="gd-why" className="gd-section">
          <h2>Why it is built this way</h2>
          <div className="gd-why-grid">
            {RATIONALE.map((r) => (
              <div key={r.title} className="gd-card">
                <b>{r.title}</b>
                <p>{r.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="gd-measured" className="gd-section">
          <h2>What has been measured so far</h2>
          <p className="gd-intro">Results from real runs, dated. They describe the robots, models and settings used then; they are not general claims.</p>
          <ul className="gd-measured">
            {MEASURED.map((m) => (
              <li key={m.text}>
                <span className="gd-date">{m.date}</span>
                <span>
                  {m.text}
                  {expert && <small>{m.source}</small>}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section id="gd-terms" className="gd-section">
          <h2>Terminology</h2>
          <label className="gd-search">
            <Search size={15} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${nTerms} terms`} aria-label="Search the terminology" />
          </label>
          {terms.map((g) => (
            <div key={g.group} className="gd-group">
              <h3>{g.group}</h3>
              <dl className="gd-terms">
                {g.terms.map(([t, d]) => (
                  <div key={t}>
                    <dt>{t}</dt>
                    <dd>{d}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
          {!terms.length && <p className="sx-muted">No term matches “{q}”.</p>}
          <p className="gd-intro">
            For the wider ideas (what Physical AI is, digital twins, the sim-to-real gap), see the{" "}
            <button className="sx-link" onClick={learn}>
              Physical AI Atlas <ArrowRight size={14} />
            </button>
          </p>
        </section>
      </div>
    </div>
  );
}
