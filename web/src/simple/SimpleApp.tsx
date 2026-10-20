import { lazy, Suspense, useState } from "react";
import { BookOpen, FileSearch, LayoutGrid, Workflow } from "lucide-react";
import { AudienceContext, storeAudience, storedAudience, type Audience } from "../audience";
import "../lab.css";
import "./simple.css";

const Convert = lazy(() => import("./Convert")),
  Understand = lazy(() => import("./Understand")),
  Atlas = lazy(() => import("../Atlas"));

type Page = "convert" | "understand" | "learn";
// Full-studio page index (App tabs) → deep-link key, for the Atlas "See it in the studio" buttons.
const STUDIO_WS = ["robot", "editor", "copilot", "knowledge", "journey", "lab", "pipeline", "reasoning", "home", "atlas"];
export type Target = { run: string; mode: string };

/** Switch to the full studio (all pages) and remember the choice for this browser. */
export function openFullStudio(ws = "home") {
  try {
    localStorage.setItem("kkh.ui", "studio");
  } catch {}
  location.href = "/?ui=studio&ws=" + ws;
}

const PAGES: { id: Page; label: string; sub: string; Icon: typeof Workflow }[] = [
  { id: "convert", label: "Convert & compare", sub: "Robot file → physics model, three ways", Icon: Workflow },
  { id: "understand", label: "Understand & fix", sub: "Read, question and correct a model", Icon: FileSearch },
  { id: "learn", label: "Learn the ideas", sub: "Physical AI Atlas", Icon: BookOpen },
];

/** Simplified studio: two features (conversion comparison, model understanding) plus the Atlas. */
export default function SimpleApp() {
  const params = new URLSearchParams(location.search);
  const [page, setPage] = useState<Page>(() => (["convert", "understand", "learn"].includes(params.get("page") || "") ? (params.get("page") as Page) : "convert"));
  const [target, setTarget] = useState<Target | undefined>(() => (params.get("run") && params.get("mode") ? { run: params.get("run")!, mode: params.get("mode")! } : undefined));
  const [audience, setAudience] = useState<Audience>(storedAudience);
  const go = (p: Page, t?: Target) => {
    setPage(p);
    if (t) setTarget(t);
    const u = new URL(location.href);
    u.searchParams.set("page", p);
    const tt = t || target;
    if (p === "understand" && tt) {
      u.searchParams.set("run", tt.run);
      u.searchParams.set("mode", tt.mode);
    } else {
      u.searchParams.delete("run");
      u.searchParams.delete("mode");
    }
    history.replaceState(null, "", u);
    scrollTo({ top: 0 });
  };
  const switchAudience = (a: Audience) => {
    setAudience(a);
    storeAudience(a);
  };
  return (
    <AudienceContext.Provider value={audience}>
      <div className="sx">
        <header className="sx-top">
          <div className="sx-brand">
            <b>
              HT <span>GEN7</span>
            </b>
            <small>PhysAI Studio</small>
          </div>
          <nav className="sx-tabs" aria-label="Pages">
            {PAGES.map(({ id, label, sub, Icon }) => (
              <button key={id} className={page === id ? "on" : ""} aria-current={page === id ? "page" : undefined} onClick={() => go(id)}>
                <Icon size={17} />
                <span>
                  <b>{label}</b>
                  <small>{sub}</small>
                </span>
              </button>
            ))}
          </nav>
          <div className="sx-right">
            <div className="sx-aud" role="group" aria-label="Level of detail">
              <button className={audience === "simple" ? "on" : ""} onClick={() => switchAudience("simple")} title="Plain words, essentials">
                Overview
              </button>
              <button className={audience === "expert" ? "on" : ""} onClick={() => switchAudience("expert")} title="Numbers, file paths and tool messages">
                Engineering
              </button>
            </div>
            <button className="sx-full" onClick={() => openFullStudio()} title="Open the complete studio with all pages (robot, knowledge graph, simulation…)">
              <LayoutGrid size={14} /> Full studio
            </button>
          </div>
        </header>
        <main>
          <Suspense fallback={<div className="lab">Loading…</div>}>
            {page === "convert" && <Convert openUnderstand={(t) => go("understand", t)} learn={() => go("learn")} />}
            {page === "understand" && <Understand target={target} setTarget={(t) => go("understand", t)} toConvert={() => go("convert")} learn={() => go("learn")} />}
            {page === "learn" && <Atlas open={(i) => openFullStudio(STUDIO_WS[i] || "home")} />}
          </Suspense>
        </main>
        <footer className="sx-foot">Local by design · Ollama · OpenModelica · GraphDB · every score comes from a real OpenModelica run</footer>
      </div>
    </AudienceContext.Provider>
  );
}
