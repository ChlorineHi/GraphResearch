"""SQLite-backed typed knowledge graph with provenance, epistemic status, aliases, reading ledger and FTS5.

Two stores share one schema: the Global KB (cross-project knowledge) and a Project KB (local experiments,
diagnoses, project facts). Edges that touch a project node live in the project store; that is the link layer.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .. import config
from ..ids import norm_text, parse_identifier
from . import epistemics as ep
from .schema import EDGE_TYPES, NODE_TYPES, PROJECT_TYPES, type_from_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(
  id TEXT PRIMARY KEY, type TEXT NOT NULL, label TEXT NOT NULL, props TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'unverified', retracted INTEGER NOT NULL DEFAULT 0,
  created TEXT, updated TEXT);
CREATE INDEX IF NOT EXISTS nodes_type ON nodes(type);
CREATE TABLE IF NOT EXISTS edges(
  id TEXT PRIMARY KEY, src TEXT NOT NULL, dst TEXT NOT NULL, type TEXT NOT NULL, props TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'unverified', retracted INTEGER NOT NULL DEFAULT 0, created TEXT, updated TEXT);
CREATE INDEX IF NOT EXISTS edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS edges_type ON edges(type);
CREATE TABLE IF NOT EXISTS provenance(
  pid INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT NOT NULL, source_type TEXT, source_ref TEXT,
  location TEXT, quote TEXT, commit_sha TEXT, extractor TEXT, extracted_at TEXT, note TEXT,
  requested_status TEXT, granted_status TEXT);
CREATE INDEX IF NOT EXISTS prov_target ON provenance(target);
CREATE TABLE IF NOT EXISTS aliases(alias TEXT NOT NULL, node_id TEXT NOT NULL, PRIMARY KEY(alias, node_id));
CREATE TABLE IF NOT EXISTS ledger(paper_id TEXT NOT NULL, section TEXT NOT NULL, chars INTEGER, sha TEXT,
  mode TEXT, read_at TEXT, PRIMARY KEY(paper_id, section, sha));
CREATE TABLE IF NOT EXISTS events(t TEXT, kind TEXT, target TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(id UNINDEXED, type UNINDEXED, label, body,
  tokenize='porter unicode61');
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(paper_id UNINDEXED, section, chunk UNINDEXED, text,
  tokenize='porter unicode61');
"""

VOCABULARY = "vocabulary"  # ontology terms are vocabulary, not claims


def now() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def edge_id(src: str, etype: str, dst: str) -> str:
    return "e:" + hashlib.sha1(f"{src}|{etype}|{dst}".encode()).hexdigest()[:16]


def _flatten(v: Any) -> str:
    if isinstance(v, dict):
        return " ".join(_flatten(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return " ".join(_flatten(x) for x in v)
    return "" if v is None else str(v)


def fts_query(q: str) -> str:
    phrases = re.findall(r'"([^"]+)"', q)
    rest = re.sub(r'"[^"]+"', " ", q)
    terms = [t for t in re.findall(r"[\w-]+", rest) if len(t) > 1]
    parts = [f'"{p}"' for p in phrases] + [f'"{t}"' for t in terms]
    return " OR ".join(parts) if parts else '""'


def _norm_section(s: str) -> str:
    s = norm_text(s)
    s = re.sub(r"^(section|sec|supplementary note|appendix)\s+", "", s)
    return s


class Store:
    def __init__(self, path: Path, scope: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.scope = scope
        self.con = sqlite3.connect(str(self.path))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    # ---------- events ----------
    def log(self, kind: str, target: str, payload: Any = None) -> None:
        self.con.execute("INSERT INTO events VALUES (?,?,?,?)",
                         (now(), kind, target, json.dumps(payload, ensure_ascii=False, default=str)))

    # ---------- ledger ----------
    def ledger_add(self, paper_id: str, section: str, chars: int, sha: str, mode: str) -> None:
        self.con.execute("INSERT OR REPLACE INTO ledger VALUES (?,?,?,?,?,?)",
                         (paper_id, section, chars, sha, mode, now()))
        self.con.commit()

    def ledger(self, paper_id: str) -> List[dict]:
        return [dict(r) for r in self.con.execute("SELECT * FROM ledger WHERE paper_id=?", (paper_id,))]

    def ledger_has(self, ref: str, location: str) -> bool:
        pid = ref if ref.startswith("paper:") else parse_identifier(ref).canonical
        rows = self.ledger(pid)
        if not rows:
            return False
        if any(r["section"] == "__FULL__" for r in rows):
            return True
        loc = _norm_section(location)
        loc_num = re.match(r"^(\d+(?:\s\d+)*)", loc)
        for r in rows:
            sec = _norm_section(r["section"])
            if not sec:
                continue
            if sec in loc or loc in sec:
                return True
            sec_num = re.match(r"^(\d+(?:\s\d+)*)", sec)
            if loc_num and sec_num and (loc_num.group(1) + " ").startswith(sec_num.group(1) + " "):
                return True
        return False

    # ---------- provenance ----------
    def _add_prov(self, target: str, prov: dict, requested: Optional[str], granted: str) -> int:
        cur = self.con.execute(
            "INSERT INTO provenance(target, source_type, source_ref, location, quote, commit_sha, extractor,"
            " extracted_at, note, requested_status, granted_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (target, prov.get("source_type"), prov.get("source_ref"), prov.get("location"),
             (prov.get("quote") or "")[:500] or None, prov.get("commit"), prov.get("extractor", "agent"),
             prov.get("extracted_at") or now(), prov.get("note"), requested, granted))
        return int(cur.lastrowid)

    def provenance(self, target: str) -> List[dict]:
        return [dict(r) for r in self.con.execute("SELECT * FROM provenance WHERE target=? ORDER BY pid",
                                                  (target,))]

    def _grant(self, requested: Optional[str], prov: Optional[dict], ledger_has) -> Tuple[str, List[str]]:
        if requested == VOCABULARY:
            return VOCABULARY, []
        if not prov:
            if requested in (None, "unverified"):
                return "unverified", []
            return "unverified", [f"status {requested} requested without provenance; stored as unverified"]
        return ep.grant(requested, prov, ledger_has)

    # ---------- nodes ----------
    def upsert_node(self, node_id: str, ntype: str, label: str, props: Optional[dict] = None,
                    status: Optional[str] = None, prov: Optional[dict] = None, aliases: Iterable[str] = (),
                    overwrite: bool = False, ledger_has=None) -> Dict[str, Any]:
        warnings: List[str] = []
        if ntype not in NODE_TYPES:
            warnings.append(f"node type {ntype} is not in the base schema (accepted as extension)")
        granted, w = self._grant(status, prov, ledger_has or self.ledger_has)
        warnings += w
        props = props or {}
        row = self.con.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        t = now()
        if row is None:
            self.con.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                             (node_id, ntype, label, json.dumps(props, ensure_ascii=False), granted, 0, t, t))
            final = granted
            self.log("node_create", node_id, {"status": granted})
        else:
            old = json.loads(row["props"])
            merged = dict(old)
            for k, v in props.items():
                if overwrite or k not in merged or merged[k] in (None, "", [], {}):
                    merged[k] = v
                elif isinstance(merged[k], list) and isinstance(v, list):
                    merged[k] = merged[k] + [x for x in v if x not in merged[k]]
            final = row["status"]
            if final == VOCABULARY and granted != VOCABULARY:
                final = VOCABULARY
            elif ep.RANK.get(granted, 0) > ep.RANK.get(final, 0) and final != VOCABULARY:
                warnings.append(f"new evidence would support {granted} (current {final}); status NOT upgraded "
                                f"automatically - use `cdri kg promote {node_id}`")
            self.con.execute("UPDATE nodes SET label=?, props=?, updated=? WHERE id=?",
                             (label if overwrite or not row["label"] else row["label"],
                              json.dumps(merged, ensure_ascii=False), t, node_id))
        if prov:
            self._add_prov(node_id, prov, status, granted)
        for a in list(aliases or ()) + [label]:
            if a:
                self.con.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (norm_text(a), node_id))
        self._reindex_node(node_id)
        self.con.commit()
        return {"id": node_id, "status": final, "granted": granted, "warnings": warnings}

    def _reindex_node(self, node_id: str) -> None:
        r = self.con.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        self.con.execute("DELETE FROM node_fts WHERE id=?", (node_id,))
        if r:
            self.con.execute("INSERT INTO node_fts VALUES (?,?,?,?)",
                             (node_id, r["type"], r["label"], _flatten(json.loads(r["props"]))))

    def get_node(self, node_id: str) -> Optional[dict]:
        r = self.con.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["props"] = json.loads(d["props"])
        d["scope"] = self.scope
        return d

    def nodes(self, ntype: Optional[str] = None, include_retracted: bool = False) -> List[dict]:
        q = "SELECT * FROM nodes WHERE 1=1"
        args: List[Any] = []
        if ntype:
            q += " AND type=?"
            args.append(ntype)
        if not include_retracted:
            q += " AND retracted=0"
        out = []
        for r in self.con.execute(q, args):
            d = dict(r)
            d["props"] = json.loads(d["props"])
            d["scope"] = self.scope
            out.append(d)
        return out

    def resolve_alias(self, text: str, ntype: Optional[str] = None) -> List[str]:
        rows = self.con.execute("SELECT a.node_id FROM aliases a JOIN nodes n ON n.id=a.node_id WHERE a.alias=?"
                                + (" AND n.type=?" if ntype else ""),
                                (norm_text(text), ntype) if ntype else (norm_text(text),)).fetchall()
        return [r[0] for r in rows]

    # ---------- edges ----------
    def add_edge(self, src: str, etype: str, dst: str, props: Optional[dict] = None, status: Optional[str] = None,
                 prov: Optional[dict] = None, ledger_has=None) -> Dict[str, Any]:
        warnings: List[str] = []
        if etype not in EDGE_TYPES:
            warnings.append(f"edge type {etype} is not in the base schema (accepted as extension)")
        granted, w = self._grant(status, prov, ledger_has or self.ledger_has)
        warnings += w
        eid = edge_id(src, etype, dst)
        row = self.con.execute("SELECT * FROM edges WHERE id=?", (eid,)).fetchone()
        t = now()
        if row is None:
            self.con.execute("INSERT INTO edges VALUES (?,?,?,?,?,?,?,?,?)",
                             (eid, src, dst, etype, json.dumps(props or {}, ensure_ascii=False), granted, 0, t, t))
            final = granted
        else:
            final = row["status"]
            merged = json.loads(row["props"])
            for k, v in (props or {}).items():
                merged.setdefault(k, v)
            self.con.execute("UPDATE edges SET props=?, updated=? WHERE id=?",
                             (json.dumps(merged, ensure_ascii=False), t, eid))
            if ep.RANK.get(granted, 0) > ep.RANK.get(final, 0):
                warnings.append(f"edge {eid}: new evidence supports {granted} (current {final}); "
                                "not upgraded automatically")
        if prov:
            self._add_prov(eid, prov, status, granted)
        if etype == "CONTRADICTS":
            for nid in (src, dst):
                n = self.get_node(nid)
                if n and not n["props"].get("contested"):
                    n["props"]["contested"] = True
                    self.con.execute("UPDATE nodes SET props=? WHERE id=?",
                                     (json.dumps(n["props"], ensure_ascii=False), nid))
        self.con.commit()
        return {"id": eid, "status": final, "granted": granted, "warnings": warnings}

    def edges(self, src: Optional[str] = None, dst: Optional[str] = None, etype: Optional[str] = None,
              include_retracted: bool = False) -> List[dict]:
        q, args = "SELECT * FROM edges WHERE 1=1", []
        for col, val in (("src", src), ("dst", dst), ("type", etype)):
            if val:
                q += f" AND {col}=?"
                args.append(val)
        if not include_retracted:
            q += " AND retracted=0"
        out = []
        for r in self.con.execute(q, args):
            d = dict(r)
            d["props"] = json.loads(d["props"])
            d["scope"] = self.scope
            out.append(d)
        return out

    # ---------- status changes ----------
    def _target_table(self, target: str) -> Optional[str]:
        if self.con.execute("SELECT 1 FROM nodes WHERE id=?", (target,)).fetchone():
            return "nodes"
        if self.con.execute("SELECT 1 FROM edges WHERE id=?", (target,)).fetchone():
            return "edges"
        return None

    def promote(self, target: str, to_status: str, prov: dict) -> Dict[str, Any]:
        table = self._target_table(target)
        if not table:
            raise KeyError(target)
        granted, warnings = ep.grant(to_status, prov, self.ledger_has)
        cur = self.con.execute(f"SELECT status FROM {table} WHERE id=?", (target,)).fetchone()[0]
        self._add_prov(target, prov, to_status, granted)
        if granted != to_status or ep.RANK[granted] <= ep.RANK.get(cur, 0):
            self.con.commit()
            return {"id": target, "status": cur, "promoted": False,
                    "warnings": warnings + [f"evidence grants {granted}; current {cur}; no promotion"]}
        self.con.execute(f"UPDATE {table} SET status=?, updated=? WHERE id=?", (granted, now(), target))
        self.log("promote", target, {"from": cur, "to": granted, "evidence": prov})
        self.con.commit()
        return {"id": target, "status": granted, "promoted": True, "warnings": warnings}

    def pending_promotions(self) -> List[dict]:
        out = []
        for table in ("nodes", "edges"):
            for r in self.con.execute(f"SELECT id, status FROM {table} WHERE retracted=0 AND status != ?",
                                      (VOCABULARY,)):
                provs = [p for p in self.provenance(r["id"]) if p["source_type"] not in ("agent", "user")]
                if not provs:
                    continue
                best = ep.best([p["granted_status"] for p in provs])
                if ep.RANK.get(best, 0) > ep.RANK.get(r["status"], 0):
                    out.append({"id": r["id"], "current": r["status"], "supported": best})
        return out

    def retract(self, target: str, reason: str) -> None:
        table = self._target_table(target)
        if not table:
            raise KeyError(target)
        self.con.execute(f"UPDATE {table} SET retracted=1, updated=? WHERE id=?", (now(), target))
        self.log("retract", target, {"reason": reason})
        self.con.commit()

    # ---------- search ----------
    def search_nodes(self, query: str, types: Optional[List[str]] = None, k: int = 20) -> List[dict]:
        rows = self.con.execute(
            "SELECT id, type, label, bm25(node_fts) AS s FROM node_fts WHERE node_fts MATCH ? ORDER BY s LIMIT ?",
            (fts_query(query), k * 3)).fetchall()
        out = []
        for r in rows:
            if types and r["type"] not in types:
                continue
            n = self.get_node(r["id"])
            if n and not n["retracted"]:
                out.append({"id": r["id"], "type": r["type"], "label": r["label"], "score": round(-r["s"], 3),
                            "status": n["status"], "scope": self.scope})
        return out[:k]

    def index_chunks(self, paper_id: str, chunks: List[Tuple[str, str]]) -> int:
        self.con.execute("DELETE FROM chunk_fts WHERE paper_id=?", (paper_id,))
        self.con.executemany("INSERT INTO chunk_fts VALUES (?,?,?,?)",
                             [(paper_id, s, i, t) for i, (s, t) in enumerate(chunks)])
        self.con.commit()
        return len(chunks)

    def search_chunks(self, query: str, k: int = 10, paper_id: Optional[str] = None) -> List[dict]:
        q = ("SELECT paper_id, section, chunk, snippet(chunk_fts, 3, '[', ']', ' ... ', 24) AS snip, "
             "bm25(chunk_fts) AS s FROM chunk_fts WHERE chunk_fts MATCH ?")
        args: List[Any] = [fts_query(query)]
        if paper_id:
            q += " AND paper_id=?"
            args.append(paper_id)
        q += " ORDER BY s LIMIT ?"
        args.append(k)
        return [{"cite": f"{r['paper_id']}#{r['chunk']}", "section": r["section"], "snippet": r["snip"],
                 "score": round(-r["s"], 3)} for r in self.con.execute(q, args)]

    def get_meta(self, key: str, default: Any = None) -> Any:
        r = self.con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_meta(self, key: str, value: Any) -> None:
        self.con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))
        self.con.commit()

    def stats(self) -> Dict[str, Any]:
        nt = {r[0]: r[1] for r in self.con.execute("SELECT type, COUNT(*) FROM nodes WHERE retracted=0 GROUP BY type")}
        et = {r[0]: r[1] for r in self.con.execute("SELECT type, COUNT(*) FROM edges WHERE retracted=0 GROUP BY type")}
        st = {r[0]: r[1] for r in self.con.execute("SELECT status, COUNT(*) FROM edges WHERE retracted=0 GROUP BY status")}
        return {"scope": self.scope, "path": str(self.path), "nodes": nt, "edges": et, "edge_status": st}

    def close(self) -> None:
        self.con.close()


class KnowledgeBase:
    """Union view over the Global KB and (optionally) a Project KB."""

    def __init__(self, project: Optional[str] = None, global_path: Optional[Path] = None, use_project: bool = True):
        self.g = Store(global_path or (config.home() / "global.sqlite"), "global")
        self.p: Optional[Store] = None
        self.project_root: Optional[Path] = None
        if use_project:
            pdir = config.project_dir(project)
            self.project_root = pdir.parent
            self.p = Store(pdir / "project.sqlite", "project")

    def stores(self) -> List[Store]:
        return [s for s in (self.p, self.g) if s is not None]

    def _is_project_id(self, node_id: str) -> bool:
        t = type_from_id(node_id)
        if t in PROJECT_TYPES:
            return True
        return bool(self.p and self.p.get_node(node_id))

    def store_for_node(self, ntype: str, node_id: str) -> Store:
        if self.p and (ntype in PROJECT_TYPES or self.p.get_node(node_id)):
            return self.p
        return self.g

    def upsert_node(self, node_id: str, ntype: str, label: str, **kw) -> Dict[str, Any]:
        kw.setdefault("ledger_has", self.g.ledger_has)
        return self.store_for_node(ntype, node_id).upsert_node(node_id, ntype, label, **kw)

    def add_edge(self, src: str, etype: str, dst: str, **kw) -> Dict[str, Any]:
        kw.setdefault("ledger_has", self.g.ledger_has)
        store = self.p if (self.p and (self._is_project_id(src) or self._is_project_id(dst))) else self.g
        r = store.add_edge(src, etype, dst, **kw)
        if etype == "CONTRADICTS":
            for nid in (src, dst):
                owner = self.owner(nid)
                n = owner.get_node(nid) if owner else None
                if n and not n["props"].get("contested"):
                    owner.upsert_node(nid, n["type"], n["label"], props={"contested": True})
        return r

    def get_node(self, node_id: str) -> Optional[dict]:
        for s in self.stores():
            n = s.get_node(node_id)
            if n:
                return n
        return None

    def nodes(self, ntype: Optional[str] = None) -> List[dict]:
        seen, out = set(), []
        for s in self.stores():
            for n in s.nodes(ntype):
                if n["id"] not in seen:
                    seen.add(n["id"])
                    out.append(n)
        return out

    def edges(self, **kw) -> List[dict]:
        out = []
        for s in self.stores():
            out += s.edges(**kw)
        return out

    def provenance(self, target: str) -> List[dict]:
        out = []
        for s in self.stores():
            out += s.provenance(target)
        return out

    def resolve_alias(self, text: str, ntype: Optional[str] = None) -> List[str]:
        out: List[str] = []
        for s in self.stores():
            out += [x for x in s.resolve_alias(text, ntype) if x not in out]
        return out

    def search_nodes(self, query: str, types: Optional[List[str]] = None, k: int = 20) -> List[dict]:
        hits = []
        for s in self.stores():
            hits += s.search_nodes(query, types, k)
        return sorted(hits, key=lambda h: -h["score"])[:k]

    def owner(self, target: str) -> Optional[Store]:
        for s in self.stores():
            if s._target_table(target):
                return s
        return None

    def promote(self, target: str, to_status: str, prov: dict) -> Dict[str, Any]:
        s = self.owner(target)
        if not s:
            raise KeyError(target)
        if s is not self.g:
            # paper-section checks always consult the global reading ledger
            s.ledger_has = self.g.ledger_has  # type: ignore[assignment]
        return s.promote(target, to_status, prov)

    def retract(self, target: str, reason: str) -> None:
        s = self.owner(target)
        if not s:
            raise KeyError(target)
        s.retract(target, reason)

    def stats(self) -> List[Dict[str, Any]]:
        return [s.stats() for s in self.stores()]
