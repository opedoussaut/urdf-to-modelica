import React, { lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const App = lazy(() => import("./App")),
  SimpleApp = lazy(() => import("./simple/SimpleApp"));

// The simplified app is the default. The full studio opens with ?ui=studio, any studio deep link (?ws=…), or when the
// person chose it last time ("Full studio" link); "Simple view" in the studio switches back.
const params = new URLSearchParams(location.search);
let stored = "";
try {
  stored = localStorage.getItem("kkh.ui") || "";
} catch {}
const ui = params.get("ui") === "simple" ? "simple" : params.get("ui") === "studio" || params.has("ws") || stored === "studio" ? "studio" : "simple";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Suspense fallback={null}>{ui === "studio" ? <App /> : <SimpleApp />}</Suspense>
  </React.StrictMode>,
);
