"""Three-tier screening support: landscape signals, focused / deep suggestions. Signals are transparent
components, never collapsed into a single quality score; the agent records the actual decisions + reasons."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Dict, List, Optional, Sequence

from .. import config
from ..ids import norm_text
from .records import Record

STOP = set("a an the of for and or in on to with by from via using is are under at as its we our this that".split())


def _terms(text: str) -> List[str]:
    return [t for t in norm_text(text).split() if t not in STOP and len(t) > 2]


def relevance(record: Record, query: str) -> float:
    q = set(_terms(query))
    if not q:
        return 0.0
    title = set(_terms(record.title))
    body = set(_terms(record.abstract or ""))
    hit_t = len(q & title) / len(q)
    hit_b = len(q & body) / len(q)
    return round(min(1.0, 0.6 * hit_t + 0.4 * hit_b + (0.1 if hit_t and hit_b else 0)), 3)


def _months_since(date: Optional[str], year: Optional[int]) -> Optional[float]:
    t = config.today()
    try:
        if date and len(date) >= 7:
            d = _dt.date.fromisoformat((date + "-01")[:10] if len(date) == 7 else date[:10])
        elif year:
            d = _dt.date(int(year), 7, 1)
        else:
            return None
    except ValueError:
        return None
    return max(0.5, (t - d).days / 30.44)


def venue_signal(venue: Optional[str]) -> Optional[str]:
    if not venue:
        return None
    v = venue.lower()
    for d in config.load_asset("disciplines.json")["disciplines"]:
        for name in d["venues"]:
            n = name.lower()
            if v == n or (len(n) > 5 and n in v) or re.fullmatch(rf"(proceedings of )?.*\b{re.escape(n)}\b.*", v):
                return name
    return None


def annotate(records: List[Record], queries: Dict[str, str], window_months: int = 24) -> List[Record]:
    win = config.time_windows(window_months)
    for r in records:
        rel = max((relevance(r, queries[fb["qid"]]) for fb in r.found_by if fb.get("qid") in queries), default=0.0)
        m = _months_since(r.date, r.year)
        date = r.date or (f"{r.year}-07-01" if r.year else None)
        if date and date >= win["recent_from"]:
            bucket = "recent"
        elif date and date >= win["core_from"]:
            bucket = "core"
        elif date:
            bucket = "foundational_or_older"
        else:
            bucket = "undated"
        r.signals.update({
            "relevance": rel,
            "recency": bucket,
            "months_since_pub": round(m, 1) if m else None,
            "citation_velocity": round((r.citations or 0) / m, 2) if m and r.citations is not None else None,
            "recognized_venue": venue_signal(r.venue),
            "lanes": sorted({fb.get("lane") for fb in r.found_by if fb.get("lane")}),
            "n_sources": len(r.sources),
            "has_abstract": bool(r.abstract),
            "oa_candidate": bool(r.oa_url or r.arxiv or r.pmcid),
        })
    return records


def suggest(records: List[Record], tier: str, intensity: str = "standard", min_relevance: float = 0.25,
            lanes: Sequence[str] = ("in_domain", "adjacent", "distant", "contradictory")) -> List[dict]:
    """Suggest candidates; stops early instead of padding with low-relevance papers."""
    cap = config.INTENSITY[intensity]["focused_max" if tier == "focused" else "deep_max"]
    pool = [r for r in records if r.signals.get("relevance", 0) >= min_relevance]
    if tier == "deep":
        pool = [r for r in pool if r.signals.get("oa_candidate")] or pool
    per_lane: Dict[str, List[Record]] = {l: [] for l in lanes}
    for r in pool:
        for l in r.signals.get("lanes", []):
            if l in per_lane:
                per_lane[l].append(r)
    def key(r: Record):
        return (r.signals.get("relevance", 0), r.signals.get("recency") == "recent",
                r.signals.get("citation_velocity") or 0)
    for l in per_lane:
        per_lane[l].sort(key=key, reverse=True)
    chosen: List[Record] = []
    i = 0
    while len(chosen) < cap and any(len(v) > i for v in per_lane.values()):
        for l in lanes:
            if len(per_lane[l]) > i and per_lane[l][i] not in chosen and len(chosen) < cap:
                chosen.append(per_lane[l][i])
        i += 1
    out = []
    for r in chosen:
        reasons = [f"relevance={r.signals['relevance']}", f"recency={r.signals['recency']}",
                   f"lanes={r.signals['lanes']}", f"status={r.pub_status}"]
        if r.signals.get("recognized_venue"):
            reasons.append(f"recognized venue signal: {r.signals['recognized_venue']}")
        out.append({"id": r.canonical, "title": r.title, "year": r.year, "suggested_tier": tier,
                    "reasons": reasons, "note": "suggestion only - agent must confirm with a reason"})
    return out
