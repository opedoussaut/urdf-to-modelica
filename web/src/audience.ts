import { createContext, useContext } from "react";

/**
 * Level of detail, labelled "Overview" ("simple": plain words, essentials) and "Engineering" ("expert": identifiers,
 * revisions, tool views). Stored values keep their original names so saved preferences carry over.
 */
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
