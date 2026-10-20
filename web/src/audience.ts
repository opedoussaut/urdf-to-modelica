import { createContext, useContext } from "react";

/** Who is looking: "simple" explains in plain words, "expert" shows identifiers, revisions and technical terms. */
export type Audience = "simple" | "expert";
export const AudienceContext = createContext<Audience>("simple");
export const useAudience = () => useContext(AudienceContext);

export function storedAudience(): Audience {
  try {
    return localStorage.getItem("kkh.audience") === "expert" ? "expert" : "simple";
  } catch {
    return "simple";
  }
}
export function storeAudience(a: Audience) {
  try {
    localStorage.setItem("kkh.audience", a);
  } catch {
    /* per-viewer convenience only */
  }
}
