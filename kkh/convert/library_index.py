"""Mode 2 retrieval: a local BM25 keyword index over Modelica library classes (no embedding model, no download).

Indexed: the Modelica Standard Library actually used by OpenModelica (MultiBody, Rotational, Translational,
Blocks.Sources). Never indexed: the URDFModelica library (mode 3), generated/modelica (the project's own
deterministic answer) and third_party/ref (reference models that must not be an input to generation).
One chunk per class: kind, full name, description string, parameters, connectors and component declarations,
with annotations removed. Deterministic: same library + same query = same result.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from .sources import ROOT, RUNS

INDEX = RUNS / "index" / "library_index.json"
URDFMODELICA = ROOT / "third_party" / "urdfmodelica" / "URDFModelica"
MSL_PARTS = ["Mechanics/MultiBody", "Mechanics/Rotational", "Mechanics/Translational", "Blocks/Sources"]
UMO_PARTS = ["Joints", "Links", "Robot", "Records", "Functions", "Types"]
CLASS_RE = re.compile(r"^\s*(?:(?:partial|encapsulated|replaceable|final|redeclare|expandable)\s+)*"
                      r"(model|block|record|connector|function|type|package)\s+(\w+)\s*(\"[^\"]*\")?", re.M)
STOP = {"the", "of", "and", "a", "an", "to", "in", "is", "for", "with", "on", "by", "be", "if", "or", "as", "at", "it"}


def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOP]


def msl_dir() -> Path:
    """Directory of the MSL OpenModelica loads (asked from OpenModelica itself, not guessed)."""
    from kkh.engineering.omc import OMCService
    omc = OMCService(RUNS / "index" / "omc")
    try:
        return Path(omc.send("getSourceFile(Modelica)")).parent
    finally:
        omc.close()


def _strip(body: str) -> str:
    out, depth, i = [], 0, 0
    # drop annotation(...) blocks (balanced parentheses)
    for m in re.finditer(r"annotation\s*\(", body):
        if m.start() < i:
            continue
        out.append(body[i:m.start()])
        depth, j = 0, m.end() - 1
        while j < len(body):
            depth += {"(": 1, ")": -1}.get(body[j], 0)
            if depth == 0:
                break
            j += 1
        i = j + 1
    out.append(body[i:])
    return re.sub(r"\n\s*\n+", "\n", "".join(out))


def chunks_from(file: Path, base: Path, prefix: str) -> list[dict]:
    text = file.read_text(encoding="utf-8", errors="replace")
    rel = file.relative_to(base).with_suffix("")
    pkg = ".".join([prefix, *rel.parts[:-1]]) if rel.name == "package" else ".".join([prefix, *rel.parts[:-1]])
    out = []
    for m in CLASS_RE.finditer(text):
        kind, name, doc = m.group(1), m.group(2), (m.group(3) or "").strip('"')
        end = re.search(r"^\s*end\s+" + name + r"\s*;", text[m.end():], re.M)
        body = text[m.end(): m.end() + end.start()] if end else text[m.end(): m.end() + 4000]
        if kind == "package" and len(body) > 3000:
            body = ""  # package headers only; their classes are indexed separately
        body = _strip(body)
        decl = [l.strip() for l in body.splitlines()
                if re.match(r"\s*(parameter|input|output|Interfaces\.|Modelica\.|Frames|SI\.|replaceable|extends|outer|inner|[A-Z]\w*\.\w)", l)
                and len(l.strip()) < 220]
        signature = "\n".join(decl[:24])
        full = f"{pkg}.{name}" if pkg and not pkg.endswith("." + name) else (pkg or name)
        out.append({"class": full, "kind": kind, "doc": doc, "file": file.as_posix(), "signature": signature,
                    "text": f"{kind} {full} \"{doc}\"\n{signature}"[:1300]})
    return out


def build(force: bool = False) -> dict:
    if INDEX.exists() and not force:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    msl = msl_dir()
    docs: list[dict] = []
    for part in MSL_PARTS:
        for f in sorted((msl / part).rglob("*.mo")):
            docs += chunks_from(f, msl, "Modelica")
    # URDFModelica classes are not indexed: the LLM's file must load with the MSL alone, and mode 3 already
    # measures that library; mixing it into mode 2 would blur the comparison.
    for d in docs:
        assert "generated/modelica" not in d["file"] and "third_party/ref" not in d["file"]
    # the short class name counts three times: a query naming a class should find that class first
    toks = [tokens((d["class"].rsplit(".", 1)[-1] + " ") * 3 + d["class"].replace(".", " ") + " " + d["doc"] + " " + d["signature"])
            for d in docs]
    df = Counter(t for ts in toks for t in set(ts))
    index = {"msl_dir": msl.as_posix(), "documents": docs, "tokens": toks, "df": df, "n": len(docs),
             "avgdl": sum(map(len, toks)) / max(1, len(toks))}
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index), encoding="utf-8")
    return index


def search(query: str, k: int = 8, index: dict | None = None, k1: float = 1.5, b: float = 0.75) -> list[dict]:
    index = index or build()
    q = tokens(query)
    n, avgdl, df = index["n"], index["avgdl"], index["df"]
    scored = []
    for i, ts in enumerate(index["tokens"]):
        tf = Counter(ts)
        s = 0.0
        for t in set(q):
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(ts) / avgdl))
        if s > 0:
            scored.append((round(s, 6), i))
    scored.sort(key=lambda x: (-x[0], index["documents"][x[1]]["class"]))
    return [{**index["documents"][i], "score": s} for s, i in scored[:k]]


MB = "Modelica.Mechanics.MultiBody."


def queries_for(robot) -> tuple[list[str], list[str]]:
    """(class names looked up exactly, keyword queries), derived only from the URDF element types present."""
    types = {j.type for j in robot.joints.values()}
    exact = [MB + "World", MB + "Parts.Body", MB + "Parts.FixedTranslation", MB + "Parts.FixedRotation"]
    if types & {"revolute", "continuous"}:
        exact.append(MB + "Joints.Revolute")
    if "prismatic" in types:
        exact.append(MB + "Joints.Prismatic")
    keyword = ["double pendulum example revolute body world"]
    if any(j.mimic for j in robot.joints.values()):
        keyword.append("ideal gear ratio coupling two flanges")
    return exact, keyword


def retrieve_for(robot, budget_chars: int = 12000) -> list[dict]:
    index = build()
    seen, out, used = set(), [], 0
    exact, keyword = queries_for(robot)
    by_class = {d["class"]: d for d in index["documents"]}
    for name in exact:
        if name in by_class and used + len(by_class[name]["text"]) <= budget_chars:
            d = by_class[name]
            out.append({"query": "class lookup: " + name, "class": name, "doc": d["doc"], "score": None,
                        "file": d["file"], "text": d["text"]})
            seen.add(name)
            used += len(d["text"])
    for q in keyword:
        for hit in search(q, k=2, index=index):
            if hit["class"] in seen or hit["kind"] == "package":
                continue
            item = {"query": q, "class": hit["class"], "doc": hit["doc"], "score": hit["score"],
                    "file": hit["file"], "text": hit["text"]}
            if used + len(item["text"]) > budget_chars:
                continue
            seen.add(hit["class"])
            out.append(item)
            used += len(item["text"])
    return out
