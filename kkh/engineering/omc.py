"""OpenModelica service: load, check, compile/simulate, read results, classify diagnostics.

All simulation data shown by the application comes from this module, i.e. from real omc runs.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.io

DEFAULT_OMHOME = os.environ.get("OPENMODELICAHOME", r"C:\Program Files\OpenModelica1.27.1-64bit")


@dataclass
class OmcResult:
    ok: bool
    action: str
    model: str
    messages: str = ""
    errors: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    seconds: float = 0.0

    def to_dict(self):
        return {"ok": self.ok, "action": self.action, "model": self.model, "messages": self.messages,
                "errors": self.errors, "data": self.data, "seconds": round(self.seconds, 3)}


_ERR_RE = re.compile(r"\[(?P<file>[^\]]*?):(?P<line>\d+):(?P<col>\d+)-[^\]]*\]\s*(?P<kind>Error|Warning|Notification):\s*(?P<msg>.*)")

ERROR_CLASSES = [
    ("lookup", r"not found in scope|Class .* not found|Variable .* not found|Failed to instantiate"),
    ("syntax", r"Parse error|Missing token|No viable alternative|Lexer"),
    ("type", r"Type mismatch|type .* does not match|dimension|Incompatible"),
    ("connect", r"connect|connector"),
    ("balance", r"equations? and \d+ variables?|over-determined|under-determined|structurally singular|is not balanced"),
    ("initialization", r"initiali[sz]ation"),
    ("assertion", r"assert"),
    ("numerical", r"solver|step size|Newton|nonlinear system|division by zero"),
    ("compile", r"gcc|clang|make|linker|compilation of"),
]


def classify(msg: str) -> str:
    for name, pat in ERROR_CLASSES:
        if re.search(pat, msg, re.IGNORECASE):
            return name
    return "other"


def parse_messages(text: str) -> list[dict]:
    out = []
    for line in (text or "").splitlines():
        m = _ERR_RE.search(line)
        if m:
            d = m.groupdict()
            d["class"] = classify(d["msg"])
            out.append(d)
        elif re.match(r"^\s*(Error|Warning):", line):
            out.append({"kind": line.split(":")[0].strip(), "msg": line.split(":", 1)[1].strip(),
                        "class": classify(line), "file": None, "line": None, "col": None})
    return out


class OMCService:
    """Thin, explicit wrapper over one omc process (OMPython)."""

    def __init__(self, workdir: str | Path, msl_version: str = "4.1.0"):
        from OMPython import OMCSessionLocal
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.session = OMCSessionLocal(omhome=DEFAULT_OMHOME)
        self.send(f'cd("{self.workdir.as_posix()}")')
        self.msl_version = msl_version
        ok = self.send(f'loadModel(Modelica, {{"{msl_version}"}})')
        if not ok:
            raise RuntimeError(f"Cannot load MSL {msl_version}: {self.errors()}")

    def send(self, expr: str):
        """Send an expression. OMPython raises on omc error messages; capture them as diagnostics."""
        from OMPython import OMSessionException
        try:
            return self.session.sendExpression(expr)
        except OMSessionException as e:
            self._pending_errors = str(e)
            return None

    def errors(self) -> str:
        pending, self._pending_errors = getattr(self, "_pending_errors", ""), ""
        try:
            more = self.session.sendExpression("getErrorString()", parsed=False).strip().strip('"')
        except Exception as e:  # pragma: no cover
            more = str(e)
        # OMPython formats captured messages as "NN: [translation:error:135] [file:...:l:c:l:c] msg"
        pending = re.sub(r"^\d+: \[(\w+):(\w+):\d+\] \[([^\]]*?):(?:false|true):(\d+):(\d+):[^\]]*\]",
                         lambda m: f"[{m.group(3)}:{m.group(4)}:{m.group(5)}-x] {m.group(2).capitalize()}:",
                         pending, flags=re.M)
        return (pending + "\n" + more).strip()

    def loaded_libraries(self) -> dict:
        out = {}
        for lib in ("Modelica",):
            out[lib] = self.send(f"getVersion({lib})")
        return out

    def version(self) -> str:
        return self.send("getVersion()")

    def load_package(self, package_mo: str | Path) -> OmcResult:
        t = time.time()
        p = Path(package_mo).resolve().as_posix()
        ok = bool(self.send(f'loadFile("{p}")'))
        msg = self.errors()
        return OmcResult(ok, "load", p, msg, parse_messages(msg), seconds=time.time() - t)

    def check(self, model: str) -> OmcResult:
        t = time.time()
        res = self.send(f"checkModel({model})") or ""
        msg = self.errors()
        ok = "completed successfully" in res
        data = {}
        m = re.search(r"has (\d+) equation\(s\) and (\d+) variable\(s\)", res)
        if m:
            data = {"equations": int(m.group(1)), "variables": int(m.group(2))}
        return OmcResult(ok, "check", model, (res + "\n" + msg).strip(), parse_messages(msg), data,
                         time.time() - t)

    def simulate(self, model: str, stop_time: float, intervals: int = 500, tolerance: float = 1e-6,
                 variable_filter: str = ".*", timeout_s: int = 300) -> OmcResult:
        t = time.time()
        res = self.send(
            f'simulate({model}, startTime=0, stopTime={stop_time}, numberOfIntervals={intervals}, '
            f'tolerance={tolerance}, method="dassl", variableFilter="{variable_filter}", '
            f'simflags="-alarm={int(timeout_s)} -lv=LOG_STATS")')
        msg = self.errors()
        res = res or {}
        sim_msgs = res.get("messages", "") if isinstance(res, dict) else str(res)
        rf = res.get("resultFile", "") if isinstance(res, dict) else ""
        ok = bool(rf) and "simulation finished successfully" in sim_msgs.lower()
        data = {k: res.get(k) for k in ("resultFile", "timeFrontend", "timeBackend", "timeSimCode",
                                        "timeCompile", "timeSimulation", "timeTotal")} if isinstance(res, dict) else {}
        data["assert_warnings"] = sim_msgs.count("assertion has been violated")
        return OmcResult(ok, "simulate", model, (sim_msgs + "\n" + msg).strip(),
                         parse_messages(msg + "\n" + sim_msgs), data, time.time() - t)

    def close(self):
        try:
            self.send("quit()")
        except Exception:
            pass


# ------------------------------------------------------------------------------------------
# Result file reader (MATLAB v4, OpenModelica "binTrans" layout)
# ------------------------------------------------------------------------------------------
class MatResult:
    def __init__(self, path: str | Path):
        d = scipy.io.loadmat(str(path))
        aclass = [str(s) for s in d["Aclass"]]
        transposed = len(aclass) > 3 and aclass[3].strip().startswith("binTrans")
        self.names = self._strings(d["name"], transposed)
        self.info = d["dataInfo"]
        # Normalise to: info (4, nvars); d1 (nparams, 2); d2 (nvars, ntimes)
        if transposed:
            self.info, self.d1, self.d2 = d["dataInfo"], d["data_1"], d["data_2"]
        else:  # pragma: no cover
            self.info, self.d1, self.d2 = d["dataInfo"].T, d["data_1"].T, d["data_2"].T
        if self.info.shape[0] != 4:
            self.info = self.info.T
        self.index = {n: i for i, n in enumerate(self.names)}
        self.time = self.d2[0, :]

    @staticmethod
    def _strings(arr, transposed) -> list[str]:
        rows = [str(r) for r in arr]
        if transposed:
            width = max(len(r) for r in rows)
            rows = [r.ljust(width) for r in rows]
            return ["".join(r[i] for r in rows).rstrip("\x00 ").strip() for i in range(width)]
        return [r.rstrip("\x00 ").strip() for r in rows]

    def has(self, name: str) -> bool:
        return name in self.index

    def get(self, name: str) -> np.ndarray:
        i = self.index[name]
        mat, col = int(self.info[0, i]), int(self.info[1, i])
        sign = -1.0 if col < 0 else 1.0
        col = abs(col) - 1
        if mat == 1:
            return np.full_like(self.time, sign * self.d1[col, 0])
        if mat in (2, 0):
            return sign * self.d2[col, :]
        raise KeyError(name)

    def final(self, name: str) -> float:
        return float(self.get(name)[-1])
