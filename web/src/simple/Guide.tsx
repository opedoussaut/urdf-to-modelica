import { useMemo, useState } from "react";
import { ArrowRight, BookOpen, CheckCircle2, ChevronRight, CircleDashed, Loader2, Search } from "lucide-react";
import { useAudience } from "../audience";
import { FLOW, GLOSSARY, MEASURED, NEXT, RATIONALE } from "./guideContent";
import "./guide.css";

const SECTIONS = [
  ["flow", "The flow, step by step"],
  ["why", "Why it is built this way"],
  ["measured", "What has been measured"],
  ["next", "Where it is going"],
  ["terms", "Terminology"],
] as const;

/** Guide: what the simplified studio does, in order, the reasons behind each choice, and the words it uses. */
export default function Guide({ go, learn }: { go: (page: "convert" | "review") => void; learn: () => void }) {
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
          <h1>From a robot file to a physics model you can trust</h1>
          <p className="sx-lead">
            The studio takes a robot's public description file, turns it into a Modelica physics model, and checks the result against that same file
            with real simulations. It then lets people and AI review the model under identical, scored conditions. This guide explains each step, why it
            is done that way, and the words used along the way.
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
                  Open {s.page === "convert" ? "Convert & compare" : "Review"} <ArrowRight size={14} />
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

        <section id="gd-next" className="gd-section">
          <h2>The repair workflow: AI that repairs, not AI that writes</h2>
          <p className="gd-intro">
            The next version changes the order of the work. The deterministic converter writes the model, OpenModelica lists its problems, and two
            AI methods then try to repair it under identical conditions: AI only, and AI with a governed collection of Modelica knowledge. The
            question is whether that knowledge measurably helps. The experiment stays valid if it does not.
          </p>
          <ol className="gd-stages">
            {NEXT.map((s, i) => (
              <li key={s.title} className={"gd-stage " + s.status.replace(" ", "-")}>
                <span className="gd-stage-n">{i + 1}</span>
                <b>{s.title}</b>
                <p>{s.text}</p>
                <span className="gd-badge">
                  {s.status === "built" ? <CheckCircle2 size={13} /> : s.status === "in progress" ? <Loader2 size={13} /> : <CircleDashed size={13} />}
                  {s.status}
                </span>
              </li>
            ))}
          </ol>
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
