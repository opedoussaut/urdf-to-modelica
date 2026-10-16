"""SQLite documents with revision history, compare-and-swap writes, and soft deletion."""
from __future__ import annotations
import datetime as dt
import json
import sqlite3
import uuid
from pathlib import Path
from kkh.domain.aloha.configuration import ROOT

DB_PATH = ROOT / "runs/studio/studio.sqlite3"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
              data TEXT NOT NULL, version INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, deleted INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS history(sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL,
              version INTEGER NOT NULL, snapshot TEXT NOT NULL, recorded TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS documents_kind ON documents(kind, deleted, updated);
            CREATE INDEX IF NOT EXISTS message_conversation ON documents(json_extract(data,'$.conversation')) WHERE kind='message';
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def decode(row):
        if row is None:
            raise KeyError("Record not found")
        out = dict(row)
        out["data"] = json.loads(out["data"])
        return out

    def create(self, kind, name, data, identity=None):
        identity = identity or uuid.uuid4().hex
        timestamp = now()
        with self.connect() as db:
            db.execute("INSERT INTO documents(id,kind,name,data,version,created,updated) VALUES(?,?,?,?,1,?,?)",
                       (identity, kind, name.strip()[:160] or kind, json.dumps(data, allow_nan=False), timestamp, timestamp))
        return self.get(identity)

    def get(self, identity, kind=None):
        with self.connect() as db:
            record = self.decode(db.execute("SELECT * FROM documents WHERE id=? AND deleted=0", (identity,)).fetchone())
        if kind and record["kind"] != kind:
            raise KeyError("Record type mismatch")
        return record

    def list(self, kind, search="", limit=200):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM documents WHERE kind=? AND deleted=0 AND (name LIKE ? OR data LIKE ?) ORDER BY updated DESC LIMIT ?",
                              (kind, f"%{search}%", f"%{search}%", min(limit, 2000))).fetchall()
            return [self.decode(row) for row in rows]

    def update(self, identity, version, data=None, name=None, delete=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = self.decode(db.execute("SELECT * FROM documents WHERE id=? AND deleted=0", (identity,)).fetchone())
            if old["version"] != version:
                raise ValueError("This record changed. Reload it before saving; existing work was preserved.")
            db.execute("INSERT INTO history(id,version,snapshot,recorded) VALUES(?,?,?,?)", (identity, version, json.dumps(old), now()))
            db.execute("UPDATE documents SET name=?,data=?,version=version+1,updated=?,deleted=? WHERE id=?",
                       (name if name is not None else old["name"], json.dumps(data if data is not None else old["data"], allow_nan=False), now(), int(delete), identity))
        return {"deleted": True, "id": identity} if delete else self.get(identity)

    def history(self, identity):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT snapshot FROM history WHERE id=? ORDER BY sequence DESC", (identity,))]

    def messages(self, conversation):
        with self.connect() as db:
            return [self.decode(row) for row in db.execute("SELECT * FROM documents WHERE kind='message' AND deleted=0 AND json_extract(data,'$.conversation')=? ORDER BY created,id",(conversation,))]

    def exists(self, identity):
        """Includes tombstones so audit recovery never resurrects a deleted conversation."""
        with self.connect() as db:
            return db.execute("SELECT 1 FROM documents WHERE id=?",(identity,)).fetchone() is not None

    def conversations(self, search=""):
        with self.connect() as db:
            return [self.decode(row) for row in db.execute("""SELECT c.* FROM documents c WHERE c.kind='conversation' AND c.deleted=0
                AND (c.name LIKE ? OR c.data LIKE ? OR EXISTS(SELECT 1 FROM documents m WHERE m.kind='message' AND m.deleted=0
                AND json_extract(m.data,'$.conversation')=c.id AND m.data LIKE ?)) ORDER BY c.updated DESC LIMIT 500""",(f"%{search}%",f"%{search}%",f"%{search}%"))]


def recover_audits(store: Store):
    """Recover actual old copilot audit records once; do not reconstruct missing user text."""
    for path in sorted((ROOT / "runs/copilot").glob("*.json")):
        identity = "recovered-" + path.stem
        if store.exists(identity):continue
        try:
            audit = json.loads(path.read_text(encoding="utf-8"))
            conversation = store.create("conversation", "Recovered: " + audit.get("question", "engineering answer")[:65],
                                        {"recovered_from": path.relative_to(ROOT).as_posix()}, identity)
            if audit.get("question"):
                store.create("message", "user", {"conversation": conversation["id"], "role": "user", "content": audit["question"], "mode": "grounded", "original_timestamp": audit.get("created")})
            store.create("message", "assistant", {"conversation": conversation["id"], "role": "assistant", "content": audit.get("answer", ""),
                         "mode": "grounded", "evidence": audit.get("evidence", []), "citations": audit.get("citations", []),
                         "original_timestamp": audit.get("created"), "recovery_note": "User question unavailable" if not audit.get("question") else "Recovered from actual audit"})
        except (ValueError, OSError):
            continue
