"""Governed Modelica engineering knowledge collection for the "AI + Modelica assets" repair arm (increment 3).

Sources (v1, all local, no download):
  msl-4.1.0                Modelica Standard Library 4.1.0: MultiBody (incl. Examples), Rotational, Translational,
                           Blocks, Units, UsersGuide (conventions, connectors, release notes). Modelica 3-Clause BSD.
  modelicareference-4.1.0  ModelicaReference 4.1.0: language keywords, operators and annotations (Placement, Line,
                           Icon, Diagram, connect, ...). Modelica 3-Clause BSD.
  project-patterns         validated project conventions (kkh/workflow/patterns/*.md, front matter with source,
                           commit and evidence). Project-internal: the repository has no licence file.
Added in v2 (26 Oct 2026, approved by the user):
  mls-3.7                  Modelica Language Specification 3.7 (May 2026), LaTeX chapters pinned in
                           config/public_sources.json; one passage per section. CC BY-SA 4.0 (read from LICENSE.md).
  omc-errors-1.27.1        OpenModelica 1.27.1 compiler error-message catalog (OMCompiler/Compiler/Util/Error.mo), one
                           passage per message. OSMC-PL 1.8 or AGPL 3 (read from OSMC-License.txt).
  msl-conversion-4.0.0     the MSL's own conversion script 3.2.3 -> 4.0.0 (local, part of MSL 4.1.0), one passage per
                           old package with its renames. Modelica 3-Clause BSD.
  omc-guide-1.27           OpenModelica User's Guide 1.27 (local, installed with OpenModelica), one passage per
                           section. OSMC-PL 1.8 or AGPL 3 (read from the installation's OSMC-License.txt).
Library locations and versions are asked from OpenModelica (getSourceFile / getVersion), never guessed; licences are
read from each library's own package.mo and an asset without a verified licence is refused.

Excluded by design (asserted): the URDFModelica library (its output is what is repaired), generated/ (the project's
own answer) and third_party/ref (a reference model that must never be an input).

Every chunk: {id, asset_id, version, licence, class, kind, source_path, line_start, line_end, file_sha256, text}.
Retrieval: BM25 (kkh.convert.library_index.tokens / search), deterministic, ties broken by chunk id. The index is
cached under runs/workflow/assets/ keyed by the manifest hash (source specs + every indexed file's SHA-256).

    PYTHONPATH=. python -m kkh.workflow.assets build|search "<query>"
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

from kkh.convert import library_index

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "runs" / "workflow" / "assets"
PATTERNS = Path(__file__).resolve().parent / "patterns"
SCHEMA = "kkh.workflow.assets/1"
EXCLUDED = ("URDFModelica", "urdfmodelica", "generated/modelica", "third_party/ref")
BSD_MARK = "modelica-3-clause-bsd"
DOC_CHARS, TEXT_CHARS, EXAMPLE_CHARS = 1500, 3000, 1400

SOURCES = [
    {"id": "msl-4.1.0", "library": "Modelica", "version": "4.1.0",
     "title": "Modelica Standard Library 4.1.0 (Modelica Association)",
     "scope": ["Mechanics/MultiBody", "Mechanics/Rotational", "Mechanics/Translational", "Blocks", "Units.mo",
               "UsersGuide"]},
    {"id": "modelicareference-4.1.0", "library": "ModelicaReference", "version": "4.1.0",
     "title": "ModelicaReference 4.1.0: Modelica language and annotation reference (Modelica Association)",
     "scope": ["package.mo"]},
    {"id": "project-patterns", "library": None, "version": None,
     "title": "Validated project Modelica patterns (kkh/workflow/patterns)", "scope": ["*.md"]},
    {"id": "mls-3.7", "library": None, "version": "3.7", "type": "latex",
     "title": "Modelica Language Specification 3.7 (Modelica Association, May 2026)",
     "root": "third_party/modelica_specification", "licence_file": "LICENSE.md", "licence_mark": "Attribution-ShareAlike 4.0",
     "licence_name": "CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)",
     "scope": ["chapters/*.tex"], "skip": ["abstract.tex", "copyright.tex", "preface.tex", "titlepage.tex", "revisions.tex"]},
    {"id": "omc-errors-1.27.1", "library": None, "version": "1.27.1", "type": "omc-errors",
     "title": "OpenModelica 1.27.1 compiler error messages (Error.mo)",
     "root": "third_party/openmodelica_errors", "licence_file": "OSMC-License.txt", "licence_mark": "OSMC Public License",
     "licence_name": "OSMC-PL 1.8 or AGPL 3 (Open Source Modelica Consortium)",
     "scope": ["OMCompiler/Compiler/Util/Error.mo"]},
    {"id": "msl-conversion-4.0.0", "library": "Modelica", "version": "4.1.0", "type": "mos",
     "title": "Modelica Standard Library conversion script 3.2.3 -> 4.0.0 (shipped with MSL 4.1.0)",
     "scope": ["Resources/Scripts/Conversion/ConvertModelica_from_3.2.3_to_4.0.0.mos"]},
    {"id": "omc-guide-1.27", "library": None, "version": "1.27", "type": "html",
     "title": "OpenModelica User's Guide 1.27 (installed with OpenModelica)",
     "root": "@OMHOME/share/doc/omc/OpenModelicaUsersGuide", "licence_file": "@OMHOME/bin/OSMC-License.txt",
     "licence_mark": "OSMC Public License", "licence_name": "OSMC-PL 1.8 or AGPL 3 (Open Source Modelica Consortium)",
     # only the pages about checking, solving, initialization, debugging, compiler flags and porting
     "scope": ["solving.html", "debugger.html", "simulationflags.html", "faq.html", "porting.html", "compiler.html",
               "backwardscompatibility.html", "technical_details.html", "omchelptext.html"]},
]


# ---------------------------------------------------------------- sources

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _excluded(p: Path) -> bool:
    s = p.as_posix()
    return any(x in s for x in EXCLUDED)


def locate(libraries: list[tuple[str, str]], cache: Path = CACHE) -> dict[str, dict]:
    """Root directory and version of each library, asked from OpenModelica once and cached (re-asked if a cached
    path disappears)."""
    f = cache / "locations.json"
    known = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if all(n in known and Path(known[n]["root"]).is_dir() and known[n]["version"] == v for n, v in libraries):
        return known
    from kkh.engineering.omc import OMCService
    omc = OMCService(cache / "omc")
    try:
        for name, version in libraries:
            if name != "Modelica" and not omc.send(f'loadModel({name}, {{"{version}"}})'):
                raise RuntimeError(f"OpenModelica cannot load {name} {version}: {omc.errors()}")
            known[name] = {"root": Path(omc.send(f"getSourceFile({name})")).parent.as_posix(),
                           "version": omc.send(f"getVersion({name})")}
    finally:
        omc.close()
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(known, indent=1), encoding="utf-8")
    return known


def _licence(root: Path) -> str:
    text = (root / "package.mo").read_text(encoding="utf-8", errors="replace")
    if BSD_MARK not in text:
        raise ValueError(f"no verified licence in {root / 'package.mo'}: asset refused")
    return "Modelica 3-Clause BSD (https://modelica.org/licenses/modelica-3-clause-bsd)"


def _files(root: Path, scope: list[str]) -> list[Path]:
    out = []
    for s in scope:
        p = root / s
        if "*" in s:
            out += sorted(root.glob(s))
        elif p.is_dir():
            out += sorted(p.rglob("*.mo"))
        elif p.is_file():
            out.append(p)
        else:
            raise FileNotFoundError(f"scope entry missing: {p}")
    return [f for f in out if not _excluded(f)]


def manifest(cache: Path = CACHE) -> dict:
    """Sources with root, verified version and licence, and the SHA-256 of every file in scope."""
    libs = [(s["library"], s["version"]) for s in SOURCES if s["library"]]
    loc = locate(libs, cache)
    assets = []
    for s in SOURCES:
        if s.get("root"):  # a pinned or installed document set with its own licence file
            from kkh.engineering.omc import DEFAULT_OMHOME
            def where(x):
                return Path(x.replace("@OMHOME", DEFAULT_OMHOME)) if x.startswith("@OMHOME") else ROOT / x
            root = where(s["root"])
            lf = where(s["licence_file"]) if s["licence_file"].startswith("@OMHOME") else root / s["licence_file"]
            if not lf.exists() or s["licence_mark"] not in lf.read_text(encoding="utf-8", errors="replace"):
                raise ValueError(f"{s['id']}: licence not verified in {lf}: asset refused")
            licence = s["licence_name"]
        elif s["library"]:
            root = Path(loc[s["library"]]["root"])
            if loc[s["library"]]["version"] != s["version"]:
                raise ValueError(f"{s['library']}: OpenModelica reports {loc[s['library']]['version']}, expected {s['version']}")
            licence = _licence(root)
        else:
            root, licence = PATTERNS, "project-internal (authored in this repository; the repository has no licence file)"
        if _excluded(root):
            raise ValueError(f"excluded source root: {root}")
        files = [f for f in _files(root, s["scope"]) if f.name not in s.get("skip", [])]
        assets.append({**s, "root": root.as_posix(), "licence": licence,
                       "files": {f.relative_to(root).as_posix(): sha256_file(f) for f in files}})
    code = sha256_file(Path(__file__))  # the chunker is part of the key: changed code never reuses a stale index
    body = json.dumps({"code": code, "assets": [{k: a[k] for k in ("id", "version", "scope", "files")} for a in assets]},
                      sort_keys=True)
    return {"schema": SCHEMA, "hash": hashlib.sha256(body.encode()).hexdigest()[:16], "code_sha256": code,
            "assets": assets}


# ---------------------------------------------------------------- Modelica chunker

_HEADER = re.compile(r"^[ \t]*(?:(?:partial|encapsulated|replaceable|final|redeclare|expandable|impure|pure|operator)\s+)*"
                     r"(model|block|record|connector|function|type|package|class|operator)\s+(\w+)", re.M)
_END = re.compile(r"\bend\s+(\w+)\s*;")
_NOT_CLASS_END = {"if", "for", "when", "while"}


def mask_strings(text: str) -> str:
    """Same length, string literals blanked (newlines kept): structure scanning never sees code inside documentation."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            seg = text[i:j + 1]
            out.append('"' + re.sub(r"[^\n]", " ", seg[1:-1]) + '"' if len(seg) >= 2 else seg)
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _annotation_spans(masked: str, start: int, end: int) -> list[tuple[int, int]]:
    spans, i = [], start
    for m in re.finditer(r"\bannotation\s*\(", masked[start:end]):
        a = start + m.start()
        if a < i:
            continue
        depth, j = 0, start + m.end() - 1
        while j < end:
            depth += {"(": 1, ")": -1}.get(masked[j], 0)
            if depth == 0:
                break
            j += 1
        spans.append((a, j + 1))
        i = j + 1
    return spans


def _cut(text: str, start: int, end: int, holes: list[tuple[int, int]]) -> str:
    out, i = [], start
    for a, b in sorted(holes):
        if b <= start or a >= end:
            continue
        out.append(text[i:max(a, start)])
        i = max(i, min(b, end))
    out.append(text[i:end])
    return "".join(out)


def html_text(s: str) -> str:
    s = s.replace('\\"', '"').replace("\\n", "\n")
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</tr>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def classes(text: str) -> tuple[list[dict], str]:
    """Class spans with nesting, from string/comment-masked text. Short definitions (`type X = ...;`) have no end."""
    masked = mask_strings(text)
    within = re.search(r"^\s*within\s*([\w.]*)\s*;", masked, re.M)
    prefix = within.group(1) if within else ""
    events = [(m.start(), "h", m) for m in _HEADER.finditer(masked)] + \
             [(m.start(), "e", m) for m in _END.finditer(masked) if m.group(1) not in _NOT_CLASS_END]
    stack, out = [], []
    for pos, kind, m in sorted(events, key=lambda e: e[0]):
        if kind == "h":
            if stack and pos < stack[-1]["head_end"]:
                continue
            after = masked[m.end():m.end() + 400]
            desc = re.match(r'\s*"', after)
            rest = after[desc.end():] if desc else after
            rest = rest[rest.find('"') + 1:] if desc else rest
            short = re.match(r"\s*=", rest) is not None
            path = [c["name"] for c in stack] + [m.group(2)]
            item = {"kind": m.group(1), "name": m.group(2), "full": ".".join([p for p in [prefix] if p] + path),
                    "start": pos, "head_end": m.end(), "children": []}
            if short:
                semi = masked.find(";", m.end())
                item["end"] = len(masked) if semi < 0 else semi + 1
                out.append(item)
                if stack:
                    stack[-1]["children"].append((item["start"], item["end"]))
            else:
                stack.append(item)
        else:
            name = m.group(1)
            if not any(c["name"] == name for c in stack):
                continue
            while stack:
                c = stack.pop()
                c["end"] = m.end()
                out.append(c)
                if stack:
                    stack[-1]["children"].append((c["start"], c["end"]))
                if c["name"] == name:
                    break
    return sorted(out, key=lambda c: c["start"]), masked


def chunks_of_file(path: Path, root: Path, asset: dict, file_sha: str, keep=lambda full: True) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    found, masked = classes(text)
    out = []
    for c in found:
        if not keep(c["full"]):
            continue
        holes = c["children"] + _annotation_spans(masked, c["head_end"], c["end"])
        own = _cut(text, c["head_end"], c["end"], c["children"])
        desc = re.match(r'\s*"((?:[^"\\]|\\.)*)"', text[c["head_end"]:c["head_end"] + 400])
        info = re.search(r'\binfo\s*=\s*"((?:[^"\\]|\\.)*)"', own, re.S)
        body = _cut(text, c["head_end"], c["end"], holes)
        body = re.sub(r"\s+;", ";", body)  # where an annotation was removed
        body = "\n".join(l for l in body.splitlines() if l.strip() not in ("", ";"))
        decl = [l.strip() for l in body.splitlines()
                if re.match(r"\s*(parameter|constant|input|output|replaceable|extends|outer|inner|flow|stream|"
                            r"discrete|Real|Integer|Boolean|String|[A-Z][\w]*\.[\w.]+|[A-Z]\w*\s+\w)", l)
                and len(l.strip()) < 240][:28]
        parts = [f"{c['kind']} {c['full']}" + (f' "{desc.group(1)}"' if desc else "")]
        if decl and c["kind"] != "package":
            parts.append("\n".join(decl))
        if ".Examples." in c["full"] + "." and c["kind"] in ("model", "block"):
            eq = re.search(r"\bequation\b(.*)", body, re.S)
            if eq:
                parts.append("equation" + re.sub(r"\s*end\s+\w+\s*;\s*$", "", eq.group(1))[:EXAMPLE_CHARS])
            # graphical annotation examples: a few genuine connect statements with their Line annotation, verbatim
            lines = [re.sub(r"\s+", " ", m.group(0)) for m in
                     re.finditer(r"connect\s*\([^;]*?\)\s*annotation\s*\(\s*Line\s*\([^;]*?\)\s*\)\s*;", own, re.S)][:3]
            if lines:
                parts.append("connection drawing (Line annotation) examples:\n" + "\n".join(lines))
        if info:
            parts.append(html_text(info.group(1))[:DOC_CHARS])
        out.append({"id": f"{asset['id']}:{c['full']}", "asset_id": asset["id"], "version": asset["version"],
                    "licence": asset["licence"], "class": c["full"], "kind": c["kind"],
                    "source_path": path.relative_to(root).as_posix(),
                    "line_start": text.count("\n", 0, c["start"]) + 1, "line_end": text.count("\n", 0, c["end"]) + 1,
                    "file_sha256": file_sha, "text": "\n".join(parts)[:TEXT_CHARS]})
    return out


def pattern_chunk(path: Path, asset: dict, file_sha: str) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise ValueError(f"pattern without front matter: {path}")
    meta = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))
    for k in ("id", "title", "source", "commit", "evidence"):
        if not meta.get(k):
            raise ValueError(f"pattern {path.name} lacks '{k}'")
    return {"id": f"{asset['id']}:{meta['id']}", "asset_id": asset["id"], "version": meta["commit"],
            "licence": asset["licence"], "class": meta["id"], "kind": "pattern", "source_path": path.name,
            "line_start": 1, "line_end": text.count("\n") + 1, "file_sha256": file_sha,
            "provenance": {k: meta[k] for k in ("source", "commit", "evidence")},
            "text": f"pattern {meta['id']}: {meta['title']}\n{m.group(2).strip()}"[:TEXT_CHARS]}


# ---------------------------------------------------------------- v2 document chunkers

def _passage(a: dict, cid: str, title: str, kind: str, rel: str, l0: int, l1: int, sha: str, text: str) -> dict:
    return {"id": f"{a['id']}:{cid}", "asset_id": a["id"], "version": a["version"], "licence": a["licence"],
            "class": title, "kind": kind, "source_path": rel, "line_start": l0, "line_end": l1, "file_sha256": sha,
            "text": text[:TEXT_CHARS]}


def latex_text(s: str) -> str:
    """LaTeX of the specification to readable plain text (code kept, markup dropped)."""
    s = re.sub(r"(?<!\\)%.*", "", s)
    s = re.sub(r"\\(?:lstinline|robustinline)\s*!([^!]*)!", r"\1", s)
    s = re.sub(r"\\(?:lstinline|robustinline)\s*\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\begin\{lstlisting\}(?:\[[^\]]*\])?", "\n", s).replace("\\end{lstlisting}", "\n")
    s = re.sub(r"\\(?:index|label|indexinline|hypertarget)\{[^}]*\}(?:\{[^}]*\})?", "", s)
    s = re.sub(r"\\[cC]ref\{([^}]*)\}", r"section \1", s)
    s = re.sub(r"\\productionref\{([^}]*)\}", r"production \1", s)
    s = re.sub(r"\\begin\{nonnormative\}", "[Non-normative] ", s)
    s = re.sub(r"\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?(?:\{[^}]*\})?", "\n", s)
    s = re.sub(r"\\item\s*", "- ", s)
    for _ in range(3):
        s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", " ", s).replace("$", "").replace("{", "").replace("}", "").replace("~", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


_SEC = re.compile(r"^\\(chapter|section|subsection|subsubsection)\*?\{(.+?)\}\s*(?:\\label\{([^}]*)\})?", re.M)


def latex_chunks(path: Path, root: Path, a: dict, sha: str) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    heads = list(_SEC.finditer(text))
    out, trail = [], {}
    levels = ["chapter", "section", "subsection", "subsubsection"]
    for i, m in enumerate(heads):
        lvl = levels.index(m.group(1))
        trail = {k: v for k, v in trail.items() if k < lvl}
        trail[lvl] = latex_text(m.group(2))
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = latex_text(text[m.end():end])
        if len(body) < 40:
            continue
        label = m.group(3) or re.sub(r"[^a-z0-9]+", "-", trail[lvl].lower()).strip("-")
        title = " > ".join(trail[k] for k in sorted(trail))
        l0 = text.count("\n", 0, m.start()) + 1
        parts = [body[j:j + TEXT_CHARS - 300] for j in range(0, len(body), TEXT_CHARS - 300)][:4]
        for k, part in enumerate(parts):
            out.append(_passage(a, label + (f"#{k + 1}" if len(parts) > 1 else ""), title, "spec-section",
                                path.relative_to(root).as_posix(), l0, text.count("\n", 0, end) + 1, sha,
                                f"Modelica Language Specification 3.7, {title}\n{part}"))
    return out


_ERR = re.compile(r"public constant ErrorTypes\.Message (\w+) = ErrorTypes\.MESSAGE\((\d+),\s*ErrorTypes\.(\w+)\(\),\s*"
                  r"ErrorTypes\.(\w+)\(\),\s*Gettext\.gettext\((.*?)\)\);", re.S)


def omc_error_chunks(path: Path, root: Path, a: dict, sha: str) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in _ERR.finditer(text):
        msg = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(5))).replace('\\"', '"')
        words = m.group(1).replace("_", " ").lower()
        out.append(_passage(a, m.group(1), f"OpenModelica error {m.group(1)}", "error-message", path.relative_to(root).as_posix(),
                            text.count("\n", 0, m.start()) + 1, text.count("\n", 0, m.end()) + 1, sha,
                            f"OpenModelica 1.27.1 message {m.group(1)} (id {m.group(2)}, {m.group(3).lower()}, "
                            f"{m.group(4).lower()}): {msg}\nMeaning in words: {words}. %s marks the names filled in by the compiler."))
    return out


def mos_chunks(path: Path, root: Path, a: dict, sha: str) -> list[dict]:
    """The conversion script grouped by old package (two levels below Modelica): each passage lists its renames."""
    text = path.read_text(encoding="utf-8", errors="replace")
    groups: dict[str, list[str]] = {}
    for m in re.finditer(r'convert(Class|Element|Modifiers|ClassIf)\(\s*"([^"]+)"\s*,\s*(.*?)\)\s*;', text, re.S):
        old = m.group(2)
        key = ".".join(old.split(".")[:3])
        groups.setdefault(key, []).append(f"convert{m.group(1)}({old} -> {re.sub(r'\s+', ' ', m.group(3))[:160]})")
    return [_passage(a, k, f"MSL 3 -> 4 renames under {k}", "conversion-rule", path.relative_to(root).as_posix(), 1,
                     text.count("\n") + 1, sha,
                     f"Modelica Standard Library conversion 3.2.3 -> 4.0.0, classes formerly under {k} "
                     f"(an old MSL 3 name used with MSL 4 must be replaced by its new name):\n" + "\n".join(v))
            for k, v in sorted(groups.items())]


def html_chunks(path: Path, root: Path, a: dict, sha: str) -> list[dict]:
    """User's Guide page cut at its h2/h3 headings (Sphinx sections)."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    body = re.search(r'(?is)<div[^>]+role="main"[^>]*>(.*)', raw)
    raw = body.group(1) if body else raw
    parts = re.split(r"(?is)(<h[23][^>]*>.*?</h[23]>)", raw)
    out, title = [], path.stem
    for k in range(1, len(parts), 2):
        title = html_text(parts[k]).replace("\uf0c1", "").strip(" #\u00b6")
        text = html_text(parts[k + 1] if k + 1 < len(parts) else "")
        if len(text) < 60:
            continue
        cid = f"{path.stem}/{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}"
        out.append(_passage(a, cid, f"OpenModelica User's Guide: {title}", "guide-section", path.relative_to(root).as_posix(),
                            1, raw.count("\n") + 1, sha, f"OpenModelica User's Guide 1.27, {path.stem}: {title}\n{text}"))
    return out


def build_chunks(man: dict) -> list[dict]:
    chunks = []
    by_type = {"latex": latex_chunks, "omc-errors": omc_error_chunks, "mos": mos_chunks, "html": html_chunks}
    for a in man["assets"]:
        root = Path(a["root"])
        for rel, sha in a["files"].items():
            f = root / rel
            if a["id"] == "project-patterns":
                chunks.append(pattern_chunk(f, a, sha))
            elif a.get("type") in by_type:
                chunks += by_type[a["type"]](f, root, a, sha)
            else:
                chunks += chunks_of_file(f, root, a, sha)
    ids = Counter(c["id"] for c in chunks)
    dup = [i for i, n in ids.items() if n > 1]
    chunks = [c for c in chunks if c["id"] not in dup] + _merge_duplicates(chunks, dup)
    for c in chunks:
        assert not _excluded(Path(c["source_path"])), c["id"]
    return sorted(chunks, key=lambda c: c["id"])


def _merge_duplicates(chunks: list[dict], dup: list[str]) -> list[dict]:
    """The same full class name declared twice (e.g. a class redeclared in a sub-package file): keep the first
    occurrence, deterministic by (source_path, line_start)."""
    out = []
    for i in dup:
        out.append(min((c for c in chunks if c["id"] == i), key=lambda c: (c["source_path"], c["line_start"])))
    return out


# ---------------------------------------------------------------- index and retrieval

def _doc_tokens(c: dict) -> list[str]:
    short = c["class"].rsplit(".", 1)[-1]
    return library_index.tokens((short + " ") * 3 + c["class"].replace(".", " ") + " " + c["text"])


def build(force: bool = False, cache: Path = CACHE) -> dict:
    man = manifest(cache)
    f = cache / f"index-{man['hash']}.json"
    if f.exists() and not force:
        return json.loads(f.read_text(encoding="utf-8"))
    chunks = build_chunks(man)
    toks = [_doc_tokens(c) for c in chunks]
    index = {"schema": SCHEMA, "manifest": {**man, "assets": [{k: v for k, v in a.items() if k != "files"} |
                                                               {"file_count": len(a["files"])} for a in man["assets"]]},
             "manifest_hash": man["hash"], "chunks": chunks, "tokens": toks,
             "df": dict(Counter(t for ts in toks for t in set(ts))), "n": len(chunks),
             "avgdl": sum(map(len, toks)) / max(1, len(toks))}
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(index), encoding="utf-8")
    return index


def search(query: str, k: int = 5, index: dict | None = None, asset_ids: list[str] | None = None,
           kinds: list[str] | None = None) -> list[dict]:
    """Top-k chunks by BM25 (library_index.search), filtered by asset and kind; ties broken by chunk id."""
    index = index or build()
    keep = [i for i, c in enumerate(index["chunks"])
            if (not asset_ids or c["asset_id"] in asset_ids) and (not kinds or c["kind"] in kinds)]
    view = {"n": index["n"], "avgdl": index["avgdl"], "df": index["df"],
            "tokens": [index["tokens"][i] for i in keep],
            "documents": [{"class": index["chunks"][i]["id"], "_i": i} for i in keep]}
    hits = library_index.search(query, k=len(keep), index=view)
    return [{**index["chunks"][h["_i"]], "score": h["score"]} for h in hits[:k]]


# Deterministic, documented query expansion per diagnostic category (vocabulary of the Modelica sources).
CATEGORY_TERMS = {
    "graphical annotation": "Line connect annotation Diagram Placement Icon graphics",
    "mechanical or kinematic inconsistency": "MultiBody joint frame kinematics mimic coupling relative position",
    "initialization and numerical": "initial start value initialization fixed assert",
    "connector and equation": "connect connector equation balance flow potential",
    "type and unit": "unit SI type quantity",
    "missing class or library": "uses version conversion class package",
    "syntax and translation": "syntax translation",
    "unsupported URDF element": "",
    "other": "",
}


def query_for(finding: dict) -> str:
    entity = " ".join(re.split(r"[._/,; ]+", finding.get("entity") or ""))
    return " ".join(x for x in (finding.get("category", ""), finding.get("check", ""), finding.get("message", ""),
                                entity, CATEGORY_TERMS.get(finding.get("category", ""), "")) if x)


def retrieve(finding: dict, k: int = 5, budget_chars: int = 6000, index: dict | None = None) -> dict:
    """Targeted retrieval for one Stage 2 finding: the query, and the chunks (with provenance) that fit the budget."""
    q = query_for(finding)
    items, used = [], 0
    for h in search(q, k=k * 3, index=index):
        if h["kind"] == "package" and h["asset_id"] != "modelicareference-4.1.0":
            continue  # MSL package headers are tables of contents, not guidance
        if used + len(h["text"]) > budget_chars:
            continue
        items.append(h)
        used += len(h["text"])
        if len(items) == k:
            break
    return {"finding": finding.get("id"), "query": q, "chunks": items}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--force", action="store_true")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "build":
        idx = build(force=a.force)
        by = Counter((c["asset_id"], c["kind"]) for c in idx["chunks"])
        print(json.dumps({"manifest_hash": idx["manifest_hash"], "chunks": idx["n"],
                          "by_asset_kind": {f"{x}/{y}": n for (x, y), n in sorted(by.items())}}, indent=1))
    else:
        for h in search(a.query, a.k):
            print(f"{h['score']:8.3f}  {h['id']}  ({h['source_path']}:{h['line_start']}, {h['licence'].split(' (')[0]})")


if __name__ == "__main__":
    main()
