import { lazy, Suspense, useEffect, useState } from "react";
import { BookOpen, FileText, GitPullRequestArrow, LayoutGrid, RotateCcw } from "lucide-react";
import { convert } from "./api";
import { AudienceContext, storeAudience, storedAudience, type Audience } from "../audience";
import "../lab.css";
import "./simple.css";
import "./theme.css";

const Convert = lazy(() => import("./Convert")),
  Review = lazy(() => import("./Review")),
  Guide = lazy(() => import("./Guide")),
  RepairWorkflow = lazy(() => import("./Workflow")),
  Atlas = lazy(() => import("../Atlas"));

type Page = "convert" | "repair" | "review" | "guide" | "learn";
// Full-studio page index (App tabs) → deep-link key, for the Atlas "See it in the studio" buttons.
const STUDIO_WS = ["robot", "editor", "copilot", "lab", "pipeline", "home", "atlas"];
export type Target = { kind?: "conversion" | "seeded"; run?: string; mode?: string; mutation?: string };

/** Switch to the full studio (all pages) and remember the choice for this browser. */
export function openFullStudio(ws = "home") {
  try {
    localStorage.setItem("kkh.ui", "studio");
  } catch {}
  location.href = "/?ui=studio&ws=" + ws;
}

const PAGES: { id: Page; label: string; sub: string; Icon: typeof FileText }[] = [
  { id: "repair", label: "Engineering pipeline", sub: "Convert → check → AI repair → engineer decides", Icon: GitPullRequestArrow },
// The earlier comparison (AI writes the model) and its reviews are kept in the code and reachable by their old
// ?page= links, but are no longer in the navigation: the studio focuses on the engineering pipeline.
  { id: "guide", label: "Guide", sub: "The flow, why, and the words", Icon: FileText },
  { id: "learn", label: "Learn the ideas", sub: "Physical AI Atlas", Icon: BookOpen },
];

/** Simplified studio: two features (conversion comparison, reviews of the converted files) plus the Atlas. */
export default function SimpleApp() {
  const params = new URLSearchParams(location.search);
  const [page, setPage] = useState<Page>(() => {
    const p = params.get("page") === "understand" ? "review" : params.get("page");
    return ["convert", "repair", "review", "guide", "learn"].includes(p || "") ? (p as Page) : "repair";
  });
  const [target, setTarget] = useState<Target | undefined>(() =>
    params.get("mutation")
      ? { kind: "seeded", mutation: params.get("mutation")! }
      : params.get("run") && params.get("mode")
        ? { kind: "conversion", run: params.get("run")!, mode: params.get("mode")! }
        : undefined,
  );
  const [audience, setAudience] = useState<Audience>(storedAudience);
  const [resetOpen, setResetOpen] = useState(false);
  const go = (p: Page, t?: Target, topic?: string) => {
    setPage(p);
    if (t) setTarget(t);
    const u = new URL(location.href);
    if (p === "learn" && topic) u.searchParams.set("topic", topic);
    else if (p !== "learn") u.searchParams.delete("topic");
    u.searchParams.set("page", p);
    const tt = t || target;
    for (const k of ["run", "mode", "mutation"]) u.searchParams.delete(k);
    if (p === "review" && tt) {
      if (tt.kind === "seeded") u.searchParams.set("mutation", tt.mutation || "");
      else {
        u.searchParams.set("run", tt.run || "");
        u.searchParams.set("mode", tt.mode || "");
      }
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
            {(page === "convert" || page === "review") && (
              <button className="sx-full" onClick={() => setResetOpen(true)} title="Delete uploaded robots, comparisons and reviews, and start again">
                <RotateCcw size={14} /> Reset
              </button>
            )}
            <button className="sx-full" onClick={() => openFullStudio()} title="Open the complete studio with all pages (robot, editor, simulation)">
              <LayoutGrid size={14} /> Full studio
            </button>
          </div>
        </header>
        <main>
          <Suspense fallback={<div className="lab">Loading…</div>}>
            {page === "convert" && <Convert openUnderstand={(t) => go("review", t)} learn={() => go("learn", undefined, "three-ways")} />}
            {page === "review" && <Review target={target} setTarget={(t) => go("review", t)} toConvert={() => go("convert")} learn={() => go("learn", undefined, "scoring")} />}
            {page === "repair" && <RepairWorkflow />}
            {page === "guide" && <Guide go={() => go("repair")} learn={() => go("learn")} />}
            {page === "learn" && <Atlas open={(i) => openFullStudio(STUDIO_WS[i] || "home")} />}
          </Suspense>
        </main>
        {resetOpen && <ResetDialog close={() => setResetOpen(false)} />}
        <footer className="sx-foot">Local by design · Ollama · OpenModelica · every score comes from a real OpenModelica run</footer>
      </div>
    </AudienceContext.Provider>
  );
}

/** Start over: deletes what this app created (uploads, comparisons, reviews). Typed confirmation, cannot be undone. */
function ResetDialog({ close }: { close: () => void }) {
  const [counts, setCounts] = useState<{ uploads: number; runs: number }>();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([convert("/sources"), convert<any[]>("/runs")])
      .then(([s, r]) => setCounts({ uploads: s.sources.filter((x: any) => x.kind === "upload").length, runs: r.length }))
      .catch(() => setCounts({ uploads: 0, runs: 0 }));
  }, []);
  const go = async () => {
    setBusy(true);
    setError("");
    try {
      await convert("/reset", "POST", { confirm: text });
      location.href = "/?ui=simple&page=convert";
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };
  return (
    <div className="sx-modal" role="dialog" aria-modal="true" aria-labelledby="sx-reset-title" onClick={(e) => e.target === e.currentTarget && !busy && close()}>
      <div className="sx-modal-box">
        <h2 id="sx-reset-title">Start over?</h2>
        <p>This permanently deletes:</p>
        <ul>
          <li>{counts ? counts.uploads : "…"} uploaded robot file(s)</li>
          <li>{counts ? counts.runs : "…"} comparison(s), with their generated Modelica files, scores and edited versions</li>
          <li>the AI review conversations about those files</li>
        </ul>
        <p className="sx-muted">Kept: the two pinned ALOHA arms, the Modelica library search index, and everything in the full studio.</p>
        <label>
          <span>
            Type <b>RESET</b> to confirm
          </span>
          <input value={text} onChange={(e) => setText(e.target.value)} autoFocus disabled={busy} />
        </label>
        {error && <p className="lab-error">{error}</p>}
        <div className="sx-modal-actions">
          <button className="sx-btn" onClick={close} disabled={busy}>
            Cancel
          </button>
          <button className="sx-btn danger" onClick={go} disabled={busy || text !== "RESET"}>
            {busy ? "Deleting…" : "Delete everything and start over"}
          </button>
        </div>
      </div>
    </div>
  );
}
