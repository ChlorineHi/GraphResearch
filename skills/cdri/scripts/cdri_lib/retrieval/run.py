"""Execute a query plan: call sources, log every attempt (including failures), dedupe, annotate,
persist the run and ingest paper metadata into the Global KB."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .. import config, http
from ..kg.store import KnowledgeBase
from . import sources as S
from .dedupe import deduplicate
from .planner import privacy_check
from .records import Record
from .screening import annotate


def run_dir(project: Optional[str], run_id: str) -> Path:
    d = config.project_dir(project) / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_run_id(topic: str) -> str:
    from ..ids import slug
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slug(topic, 30)


def execute(plan: dict, *, project: Optional[str] = None, run_id: Optional[str] = None,
            only_sources: Optional[Sequence[str]] = None, allow_sensitive: bool = False,
            kb: Optional[KnowledgeBase] = None, ingest: bool = True) -> dict:
    run_id = run_id or new_run_id(plan["topic"])
    d = run_dir(project, run_id)
    (d / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    log_p = d / "log.jsonl"
    per_query = plan["budget"]["per_query"]
    all_recs: List[Record] = []
    log: List[dict] = []
    paused_sources: Dict[str, dict] = {}
    for q in plan["queries"]:
        issues = privacy_check(q["text"])
        srcs = [s for s in q["sources"] if not only_sources or s in only_sources]
        for src in srcs:
            entry = {"t": _dt.datetime.now().isoformat(timespec="seconds"), "qid": q["qid"], "lane": q["lane"],
                     "db": src, "query": q["text"], "date_from": q.get("date_from"),
                     "preprints_only": q.get("preprints_only", False), "attempted": False}
            if issues and not allow_sensitive:
                entry.update(status="blocked_privacy", n_results=0, error="; ".join(issues))
                log.append(entry)
                continue
            if src == "semantic_scholar" and not config.env("s2_api_key"):
                entry["note"] = "no S2_API_KEY: shared unauthenticated pool, 429 likely"
            if src in paused_sources:
                cause = paused_sources[src]
                entry.update(status="skipped_source", n_results=0, cause_status=cause["status"],
                             cause_qid=cause["qid"], error=f"source paused for this run after {cause['status']} "
                             f"on {cause['qid']}; no request sent; other sources continue")
                log.append(entry)
                continue
            try:
                fn = S.SEARCHERS[src]
                kwargs = {"limit": per_query, "date_from": q.get("date_from")}
                if src == "europepmc" and q.get("preprints_only"):
                    kwargs["preprints_only"] = True
                elif q.get("preprints_only"):
                    entry.update(status="skipped", n_results=0, error="preprints_only applies to europepmc")
                    log.append(entry)
                    continue
                entry["attempted"] = True
                recs = fn(q["text"], **kwargs)
                for r in recs:
                    r.found_by.append({"qid": q["qid"], "lane": q["lane"], "db": src})
                all_recs += recs
                entry.update(status="ok" if recs else "empty", n_results=len(recs))
            except http.HTTPFailure as e:
                entry.update(status=e.status, n_results=0, error=str(e))
                if e.status in ("rate_limited", "blocked"):
                    paused_sources[src] = {"status": e.status, "qid": q["qid"]}
            except Exception as e:  # parsing errors etc. must be visible, not swallowed
                entry.update(status="error", n_results=0, error=f"{type(e).__name__}: {e}")
            log.append(entry)
    with log_p.open("a", encoding="utf-8") as fh:
        for e in log:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    deduped = deduplicate(all_recs)
    qtext = {q["qid"]: q["text"] for q in plan["queries"]}
    annotate(deduped, qtext, config.load_config()["window_months"])
    deduped.sort(key=lambda r: -r.signals.get("relevance", 0))
    with (d / "records.jsonl").open("w", encoding="utf-8") as fh:
        for r in deduped:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    summary = coverage(log, deduped)
    summary.update({"run_id": run_id, "dir": str(d), "raw_records": len(all_recs), "unique_records": len(deduped)})
    planned_sources = sorted({s for q in plan["queries"] for s in q["sources"]})
    summary.update({"planned_sources": planned_sources, "source_filter": list(only_sources) if only_sources else None,
                    "excluded_sources": [s for s in planned_sources if only_sources and s not in only_sources]})
    (d / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if ingest:
        kb = kb or KnowledgeBase(project)
        for r in deduped:
            ingest_record(kb, r, run_id)
    return summary


def coverage(log: List[dict], records: List[Record]) -> dict:
    by_db: Dict[str, Dict[str, int]] = {}
    by_lane: Dict[str, Dict[str, int]] = {}
    failures = []
    for e in log:
        by_db.setdefault(e["db"], {}).setdefault(e["status"], 0)
        by_db[e["db"]][e["status"]] += 1
        by_lane.setdefault(e["lane"], {"queries": 0, "results": 0})
        by_lane[e["lane"]]["queries"] += 1
        by_lane[e["lane"]]["results"] += e.get("n_results", 0)
        if e["status"] not in ("ok", "empty"):
            failures.append({"db": e["db"], "query": e["query"], "status": e["status"], "error": e.get("error"),
                             "attempted": e.get("attempted", True), "cause_status": e.get("cause_status")})
    status_counts: Dict[str, int] = {}
    recency: Dict[str, int] = {}
    for r in records:
        status_counts[r.pub_status] = status_counts.get(r.pub_status, 0) + 1
        b = r.signals.get("recency", "undated")
        recency[b] = recency.get(b, 0) + 1
    available = [db for db, counts in by_db.items() if counts.get("ok", 0) + counts.get("empty", 0)]
    attempted = sum(e.get("attempted", True) for e in log)
    status = ("partial" if failures else "complete") if available else ("failed" if attempted else "not_run")
    recovery = []
    for db, counts in by_db.items():
        if counts.get("rate_limited") or counts.get("blocked"):
            advice = "Retry in a later run or restrict --source to other databases; coverage remains incomplete."
            if db == "semantic_scholar":
                advice += (" Set S2_API_KEY in the environment of the process launching the agent, restart the "
                           "agent, and verify with config check --ping; a key does not guarantee no 429.")
            elif db == "dblp":
                advice += " An anti-bot HTML response is not search results; do not loop on the challenge."
            recovery.append({"db": db, "action": advice})
    return {"status": status, "available_sources": available, "attempted_calls": attempted,
            "skipped_calls": len(log) - attempted, "source_recovery": recovery,
            "by_db": by_db, "by_lane": by_lane, "failures": failures, "pub_status": status_counts,
            "recency": recency}


def ingest_record(kb: KnowledgeBase, r: Record, run_id: str = "") -> str:
    pid = r.canonical
    props = {k: v for k, v in r.to_dict().items() if k not in ("found_by", "signals", "title", "id") and v}
    props["signals"] = {k: v for k, v in r.signals.items() if k in ("recency", "recognized_venue")}
    prov = {"source_type": "metadata_api", "source_ref": ",".join(r.sources), "location": "registry metadata",
            "extractor": "cli", "note": f"run {run_id}; status evidence: {r.status_evidence}"}
    old = kb.get_node(pid)
    kb.upsert_node(pid, "Paper", r.title, props=props, status="verified", prov=prov,
                   aliases=[x for x in (r.doi, r.arxiv, r.pmid, r.pmcid) if x])
    old_status = (old or {}).get("props", {}).get("pub_status")
    rank = {"unknown": 0, "preprint": 1, "accepted": 2, "published": 3}
    if old and rank.get(r.pub_status, 0) > rank.get(old_status, 0):
        hist = old["props"].get("status_history", []) + [{"from": old_status, "to": r.pub_status,
                                                          "evidence": r.status_evidence, "run": run_id}]
        kb.upsert_node(pid, "Paper", old["label"], props={"pub_status": r.pub_status, "venue": r.venue,
                                                          "status_evidence": r.status_evidence,
                                                          "status_history": hist}, overwrite=True)
    for v in r.versions:
        if v.get("relation") == "preprint_version" and v.get("arxiv"):
            vid = f"paper:arxiv:{v['arxiv']}"
            kb.upsert_node(vid, "Paper", r.title, props={"pub_status": "preprint", "arxiv": v["arxiv"]},
                           status="verified", prov=prov)
            kb.add_edge(vid, "VERSION_OF", pid, status="verified", prov=prov)
    if r.venue:
        from ..ids import entity_id
        vid = entity_id("venue", r.venue)
        kb.upsert_node(vid, "Venue", r.venue, status="vocabulary")
        kb.add_edge(pid, "PUBLISHED_IN", vid, status="verified", prov=prov)
    return pid


def load_records(project: Optional[str], run_id: str) -> List[Record]:
    p = run_dir(project, run_id) / "records.jsonl"
    return [Record.from_dict(json.loads(l)) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def record_decision(project: Optional[str], run_id: str, ids: Sequence[str], tier: str, reason: str) -> dict:
    if not reason.strip():
        raise ValueError("a screening decision needs a reason")
    if tier not in ("landscape", "focused", "deep", "exclude"):
        raise ValueError("tier must be landscape|focused|deep|exclude")
    d = run_dir(project, run_id)
    known = {r.canonical for r in load_records(project, run_id)}
    entries = []
    with (d / "screening.jsonl").open("a", encoding="utf-8") as fh:
        for i in ids:
            e = {"t": _dt.datetime.now().isoformat(timespec="seconds"), "id": i, "tier": tier, "reason": reason,
                 "in_run": i in known}
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            entries.append(e)
    return {"recorded": entries}


def decisions(project: Optional[str], run_id: str) -> Dict[str, dict]:
    p = run_dir(project, run_id) / "screening.jsonl"
    out: Dict[str, dict] = {}
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.strip():
                e = json.loads(l)
                out[e["id"]] = e
    return out
