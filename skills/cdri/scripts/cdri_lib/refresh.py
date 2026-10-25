"""Incremental refresh of watched topics. Runs only when the agent/user invokes it - there is no background
process. Each watch remembers when it was last checked; a refresh searches only from that date forward and
reports new papers plus status changes of known papers (preprint -> published)."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from . import config
from .ids import slug
from .kg.store import KnowledgeBase
from .retrieval import planner
from .retrieval import run as R


def _watches(kb: KnowledgeBase) -> List[dict]:
    return kb.g.get_meta("watches", [])


def add_watch(kb: KnowledgeBase, topic: str, *, intensity: str = "quick", variants=(), abstractions=(),
              structures=(), mechanisms=(), project_root: Optional[str] = None) -> dict:
    ws = _watches(kb)
    wid = slug(topic, 50)
    ws = [w for w in ws if w["id"] != wid]
    w = {"id": wid, "topic": topic, "intensity": intensity, "variants": list(variants),
         "abstractions": list(abstractions), "structures": list(structures), "mechanisms": list(mechanisms),
         "project_root": project_root, "created": config.today().isoformat(), "last_checked": None, "history": []}
    ws.append(w)
    kb.g.set_meta("watches", ws)
    return w


def list_watches(kb: KnowledgeBase) -> List[dict]:
    return _watches(kb)


def remove_watch(kb: KnowledgeBase, wid: str) -> bool:
    ws = _watches(kb)
    keep = [w for w in ws if w["id"] != wid]
    kb.g.set_meta("watches", keep)
    return len(keep) != len(ws)


def run_watch(kb: KnowledgeBase, wid: str, *, project: Optional[str] = None, since: Optional[str] = None,
              only_sources=None) -> Dict[str, Any]:
    ws = _watches(kb)
    w = next((x for x in ws if x["id"] == wid), None)
    if not w:
        raise KeyError(wid)
    start = since or w["last_checked"] or config.time_windows()["recent_from"]
    p = planner.plan(w["topic"], intensity=w["intensity"], variants=w["variants"], abstractions=w["abstractions"],
                     structures=w["structures"], mechanisms=w["mechanisms"])
    qs = []
    for q in p["queries"]:
        if q.get("date_from") is None:
            continue  # foundational queries are not part of an incremental refresh
        q["date_from"] = max(q["date_from"], start)
        qs.append(q)
    p["queries"] = qs
    p["notes"].append(f"incremental refresh since {start}")
    known = {n["id"] for n in kb.g.nodes("Paper")}
    known_status = {n["id"]: n["props"].get("pub_status") for n in kb.g.nodes("Paper")}
    run_id = R.new_run_id("refresh-" + wid)
    summary = R.execute(p, project=project, run_id=run_id, only_sources=only_sources, kb=kb)
    recs = R.load_records(project, run_id)
    new, status_changes = [], []
    for r in recs:
        ids = {r.canonical} | {f"paper:arxiv:{v['arxiv']}" for v in r.versions if v.get("arxiv")}
        if not ids & known:
            new.append(r.to_dict())
        for i in ids & known:
            if known_status.get(i) == "preprint" and r.pub_status == "published":
                status_changes.append({"id": i, "now": r.canonical, "venue": r.venue})
    attempted = summary["attempted_calls"]
    ok = sum(v.get("ok", 0) + v.get("empty", 0) for v in summary["by_db"].values())
    entry = {"t": _dt.datetime.now().isoformat(timespec="seconds"), "since": start, "run_id": run_id,
             "new": len(new), "status_changes": len(status_changes), "failed_calls": attempted - ok,
             "skipped_calls": summary["skipped_calls"]}
    if ok:  # only advance the checkpoint if at least part of the search actually ran
        w["last_checked"] = config.today().isoformat()
    w["history"].append(entry)
    kb.g.set_meta("watches", ws)
    return {"watch": wid, "since": start, "run_id": run_id, "new_papers": new, "status_changes": status_changes,
            "failures": summary["failures"],
            "checkpoint_advanced": bool(ok),
            "note": "results cover only the sources that responded; failures are listed above"}
