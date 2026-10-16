"""Immutable Modelica revisions and explicit native-editor round trips."""
from __future__ import annotations
import difflib
import hashlib
import re
import shutil
import subprocess
import uuid
import threading
from functools import wraps
from pathlib import Path
import numpy as np
from kkh.domain.aloha.configuration import ROOT
from kkh.engineering.modelica_inspect import parse_class, parse_modifiers
from kkh.engineering.omc import OMCService, DEFAULT_OMHOME
from .storage import Store

BASELINE = ROOT / "generated/modelica/ALOHA2"
WORKSPACES = ROOT / "runs/studio/models"
_mutation_lock=threading.RLock()


def synchronized(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        with _mutation_lock:return fn(*args,**kwargs)
    return wrapped


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(directory):
    return {p.relative_to(directory).as_posix(): digest(p) for p in directory.rglob("*") if p.is_file() and p.suffix in {".mo",".order"}}


def safe_file(directory, name):
    target = (directory / name).resolve()
    if not target.is_relative_to(directory.resolve()) or target.suffix != ".mo" or not target.is_file():
        raise ValueError("Select an existing Modelica source inside this working copy")
    return target


def declaration_end(text, start):
    """Semicolons inside matrices and quoted documentation do not end a declaration."""
    depth=0;quoted=False;escaped=False
    for index in range(start,len(text)):
        char=text[index]
        if quoted:
            if char=='"' and not escaped:quoted=False
            escaped=char=='\\' and not escaped
        elif char=='"':quoted=True
        elif char in "([{":depth+=1
        elif char in ")]}":depth-=1
        elif char==';' and depth==0:return index+1
    return len(text)


class Models:
    def __init__(self, store: Store, root=WORKSPACES, baseline=BASELINE):
        self.store, self.root, self.baseline = store, Path(root), Path(baseline)

    @synchronized
    def create(self, name="ALOHA editable model"):
        identity = uuid.uuid4().hex
        directory = self.root / identity / "working/ALOHA2"
        # Meshes remain in the frozen package; package resources are copied to preserve modelica:// references.
        shutil.copytree(self.baseline, directory)
        workspace = self.store.create("model", name, {"baseline_hashes": manifest(self.baseline), "accepted": None, "head": None}, identity)
        return self.snapshot(workspace, "working", "Initial copy of protected generated baseline")

    def directory(self, identity):
        self.store.get(identity, "model")
        return self.root / identity / "working/ALOHA2"

    @synchronized
    def snapshot(self, workspace, status, reason):
        identity = uuid.uuid4().hex
        source = self.directory(workspace["id"])
        destination = self.root / workspace["id"] / "versions" / identity / "ALOHA2"
        shutil.copytree(source, destination)
        revision = self.store.create("revision", reason, {"workspace": workspace["id"], "status": status, "origin":status, "hashes": manifest(source), "parent": workspace["data"]["head"]}, identity)
        return self.store.update(workspace["id"], workspace["version"], {**workspace["data"], "head": revision["id"]})

    def revision_dir(self, revision):
        return self.root / revision["data"]["workspace"] / "versions" / revision["id"] / "ALOHA2"

    def files(self, identity):
        directory = self.directory(identity)
        return [{"path": name, "class_name": "ALOHA2" + ("." + name[:-3].replace("/", ".") if name != "package.mo" else ""), "hash": value}
                for name, value in manifest(directory).items() if name.endswith(".mo")]

    def source(self, identity, name, compare_revision=None):
        file = safe_file(self.directory(identity), name)
        baseline = self.baseline / name
        structure = parse_class(file)
        original_components={c["name"]:parse_modifiers(c["modifiers"]) for c in parse_class(baseline)["components"]} if baseline.exists() else {}
        for component in structure["components"]:
            component["parameters"] = parse_modifiers(component["modifiers"])
            component["parameter_evidence"]={key:{"baseline":original_components.get(component["name"],{}).get(key),
                "status":"generated source" if value==original_components.get(component["name"],{}).get(key) else "user override",
                "source": "generated/modelica/ALOHA2/"+name} for key,value in component["parameters"].items()}
            match = re.search(r"^\s*(?:(?:parameter|constant|inner|final)\s+)*" + re.escape(component["type"]) + r"(?:\[[^\]]*\])?\s+" + re.escape(component["name"]) + r"\b", structure["source"], re.M)
            component["line"] = structure["source"][:match.start()].count("\n") + 1 if match else 1
            component["offset"] = match.start() if match else 0
            component["end_offset"] = declaration_end(structure["source"],component["offset"])
            tail = structure["source"][component["offset"]:component["end_offset"]] if match else ""
            placement = re.search(r"Placement\s*\(transformation\s*\(origin\s*=\s*\{([^}]+)\}", tail)
            component["position"] = [float(v) for v in placement[1].split(",")] if placement else None
        comparison=baseline
        if compare_revision:
            revision=self.store.get(compare_revision,"revision")
            if revision["data"]["workspace"]!=identity:raise ValueError("Comparison revision belongs to another model")
            comparison=self.revision_dir(revision)/name
        return {**structure, "path": name, "hash": digest(file), "baseline_source": comparison.read_text(encoding="utf-8") if comparison.exists() else "", "comparison":compare_revision or "generated baseline", "layout": "Source Placement annotations where present; automatic layout for unplaced ports/components"}

    @synchronized
    def save(self, identity, name, text, expected_hash, reason="Browser source edit", status="working"):
        file = safe_file(self.directory(identity), name)
        if digest(file) != expected_hash:
            raise ValueError("Source changed outside this editor. Refresh Changes before saving; unsaved text remains in the browser.")
        if len(text) > 2_000_000:
            raise ValueError("Source exceeds the 2 MB editor limit")
        file.write_text(text, encoding="utf-8")
        return self.snapshot(self.store.get(identity, "model"), status, reason)

    def changes(self, identity):
        workspace = self.store.get(identity, "model")
        head = self.store.get(workspace["data"]["head"], "revision")
        old = self.revision_dir(head)
        current = self.directory(identity)
        hashes = manifest(current)
        changes = []
        for name in sorted(set(hashes) | set(head["data"]["hashes"])):
            if hashes.get(name) == head["data"]["hashes"].get(name):
                continue
            before = (old / name).read_text(encoding="utf-8") if (old / name).exists() else ""
            after = (current / name).read_text(encoding="utf-8") if (current / name).exists() else ""
            changes.append({"path": name, "before": before, "after": after, "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="previous/"+name, tofile="working/"+name))})
        return {"head": head["id"], "hashes": hashes, "changes": changes}

    @synchronized
    def roundtrip(self, identity, action, expected_hashes):
        changes = self.changes(identity)
        if changes["hashes"] != expected_hashes:
            raise ValueError("Files changed again. Refresh and review the latest diff.")
        workspace = self.store.get(identity, "model")
        if action == "import":
            return self.snapshot(workspace, "working", "Explicitly imported native editor changes")
        if action != "reject":
            raise ValueError("Choose import or reject")
        head = self.store.get(workspace["data"]["head"])
        directory = self.directory(identity)
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix not in {".mo",".order"}:continue
            if path.relative_to(directory).as_posix() not in head["data"]["hashes"]:
                path.unlink()
        for path in self.revision_dir(head).rglob("*"):
            if not path.is_file() or path.suffix not in {".mo",".order"}:continue
            destination = directory / path.relative_to(self.revision_dir(head))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        return workspace

    def open_native(self, identity, name="package.mo"):
        exe = Path(DEFAULT_OMHOME) / "bin/OMEdit.exe"
        if not exe.exists():
            raise ValueError("OMEdit is unavailable in the configured OpenModelica installation")
        file = safe_file(self.directory(identity), name)
        subprocess.Popen([str(exe), str(self.directory(identity) / "package.mo"), str(file)] if name != "package.mo" else [str(exe), str(file)], cwd=file.parent)
        return {"opened": str(file), "baseline_protected": True}

    def validate(self, identity, class_name, simulate=False, stop_time=9):
        if not re.fullmatch(r"ALOHA2(?:\.[A-Za-z_]\w*)*", class_name):
            raise ValueError("Select a class inside ALOHA2")
        if self.changes(identity)["changes"]:
            raise ValueError("Import or reject external changes before validation")
        workspace = self.store.get(identity, "model")
        revision = self.store.get(workspace["data"]["head"])
        directory = self.revision_dir(revision)
        run = ROOT / "runs/studio/validation" / uuid.uuid4().hex
        run.mkdir(parents=True)
        omc = OMCService(run)
        try:
            loaded = omc.load_package(directory / "package.mo")
            check = omc.check(class_name)
            result = {"load": loaded.to_dict(), "check": check.to_dict(), "diagnostics": omc.errors(), "class": class_name,"stop_time_s":stop_time}
            if simulate and check.ok:
                result["simulation"] = omc.simulate(class_name, stop_time=stop_time, intervals=400).to_dict()
            valid = loaded.ok and check.ok and (not simulate or result["simulation"]["ok"])
            result["valid"] = valid
            if valid:
                self.store.update(revision["id"], revision["version"], {**revision["data"], "status": "validated", "validation": result})
            return result
        finally:
            omc.close()

    @synchronized
    @synchronized
    def propose_parameters(self, identity, name, changes, reason):
        """Apply numeric literal parameter changes to the working copy as an 'AI proposal' revision.

        Each change must name an existing component and an existing numeric literal parameter of that component in
        the given file. Nothing is accepted: the human reviews the diff, runs OpenModelica and accepts explicitly."""
        if self.changes(identity)["changes"]:
            raise ValueError("The working copy has unreviewed changes. Import or reject them before creating a proposal.")
        file = safe_file(self.directory(identity), name)
        text = file.read_text(encoding="utf-8")
        structure = parse_class(file)
        components = {c["name"]: c for c in structure["components"]}
        applied = []
        for change in changes:
            comp, key, value = change["component"], change["parameter"], change["value"]
            if comp not in components:
                raise ValueError(f"Component {comp} does not exist in {name}")
            current = parse_modifiers(components[comp]["modifiers"]).get(key)
            if current is None:
                raise ValueError(f"Parameter {key} is not set on {comp}")
            try:
                old = float(current)
            except ValueError:
                raise ValueError(f"{comp}.{key} is not a numeric literal ({current}); edit it in source")
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value):
                raise ValueError(f"{comp}.{key}: proposed value must be a finite number")
            match = re.search(r"^\s*(?:(?:parameter|constant|inner|final)\s+)*" + re.escape(components[comp]["type"])
                              + r"(?:\[[^\]]*\])?\s+" + re.escape(comp) + r"\b", text, re.M)
            start, end = match.start(), declaration_end(text, match.start())
            block, count = re.subn(r"(?<![\w.])" + re.escape(key) + r"\s*=\s*" + re.escape(current) + r"(?![\w.])",
                                   f"{key} = {float(value)!r}", text[start:end], count=1)
            if count != 1:
                raise ValueError(f"Could not locate {comp}.{key} = {current} in source")
            text = text[:start] + block + text[end:]
            applied.append({"component": comp, "parameter": key, "before": old, "after": float(value)})
        file.write_text(text, encoding="utf-8")
        workspace = self.snapshot(self.store.get(identity, "model"), "AI proposal", reason)
        return {"workspace": workspace, "revision": workspace["data"]["head"], "applied": applied, "file": name}

    def accept(self, identity, revision_id):
        revision = self.store.get(revision_id, "revision")
        workspace = self.store.get(identity, "model")
        if revision["data"]["workspace"] != identity or revision["data"]["status"] != "validated":
            raise ValueError("Only an explicitly validated revision of this model may be accepted")
        return self.store.update(identity, workspace["version"], {**workspace["data"], "accepted": revision_id})

    @synchronized
    def restore(self, identity, revision_id, expected_hashes):
        revision = self.store.get(revision_id, "revision")
        if revision["data"]["workspace"] != identity:
            raise ValueError("Revision belongs to another model")
        self.roundtrip(identity, "reject", expected_hashes)
        for path in self.directory(identity).rglob("*"):
            if path.is_file() and path.suffix in {".mo",".order"} and path.relative_to(self.directory(identity)).as_posix() not in revision["data"]["hashes"]:
                path.unlink()
        for path in self.revision_dir(revision).rglob("*"):
            if not path.is_file() or path.suffix not in {".mo",".order"}:continue
            destination = self.directory(identity) / path.relative_to(self.revision_dir(revision))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        return self.snapshot(self.store.get(identity, "model"), "working", "Restored revision " + revision_id)
