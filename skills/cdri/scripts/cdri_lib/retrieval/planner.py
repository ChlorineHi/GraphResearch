"""Discipline routing and four-lane query planning (in-domain / adjacent / distant / contradictory).

The planner proposes; the agent disposes. Problem-structure triggers only *suggest* structures -
the agent should confirm them (or pass --abstraction / --structure explicitly)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

from .. import config

LANES = ("in_domain", "adjacent", "distant", "contradictory")
SENSITIVE = [
    (re.compile(r"[A-Za-z]:\\|/home/|/Users/|\.\./|~/"), "looks like a local file path"),
    (re.compile(r"\b(?:sk|ghp|gho|xox[abp]|AKIA)[-_A-Za-z0-9]{12,}"), "looks like an access token"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "long hex string (possible secret or hash)"),
    (re.compile(r"@[A-Za-z0-9.-]+\.[a-z]{2,}"), "contains an e-mail address"),
]


def privacy_check(query: str) -> List[str]:
    issues = [why for rx, why in SENSITIVE if rx.search(query)]
    if len(query) > 300:
        issues.append("query longer than 300 characters (may contain pasted unpublished text)")
    return issues


def detect_disciplines(text: str) -> List[Dict[str, object]]:
    lex = config.load_asset("disciplines.json")["disciplines"]
    t = text.lower()
    scores = []
    for d in lex:
        hits = [k for k in d["keywords"] if k.lower() in t]
        if hits:
            scores.append({"id": d["id"], "score": len(hits), "hits": hits[:8]})
    return sorted(scores, key=lambda x: -x["score"])  # type: ignore[operator]


def sources_for(disciplines: Sequence[str]) -> List[str]:
    lex = {d["id"]: d for d in config.load_asset("disciplines.json")["disciplines"]}
    out: List[str] = []
    for did in disciplines:
        for s in lex.get(did, {}).get("sources", []):
            if s not in out:
                out.append(s)
    return out or list(config.load_asset("disciplines.json")["default_sources"])


def match_structures(text: str, explicit: Sequence[str] = ()) -> List[dict]:
    structs = config.load_asset("problem_structures.json")["structures"]
    by_id = {s["id"]: s for s in structs}
    out = [dict(by_id[i], match="explicit", hits=[]) for i in explicit if i in by_id]
    t = text.lower()
    for s in structs:
        if s["id"] in explicit:
            continue
        hits = [k for k in s["triggers"] if k.lower() in t]
        if hits:
            out.append(dict(s, match="trigger (unconfirmed)", hits=hits))
    return out


def mechanisms_index() -> Dict[str, dict]:
    return {m["id"]: m for m in config.load_asset("mechanisms.json")["mechanisms"]}


@dataclass
class PlannedQuery:
    lane: str
    text: str
    rationale: str
    sources: List[str]
    date_from: Optional[str] = None
    preprints_only: bool = False
    meta: Dict[str, object] = field(default_factory=dict)

    @property
    def qid(self) -> str:
        return "q" + hashlib.sha1(f"{self.lane}|{self.text}".encode()).hexdigest()[:8]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["qid"] = self.qid
        return d


def plan(topic: str, *, intensity: str = "standard", variants: Sequence[str] = (),
         abstractions: Sequence[str] = (), structures: Sequence[str] = (), mechanisms: Sequence[str] = (),
         assumptions: Sequence[str] = (), methods: Sequence[str] = (), lanes: Optional[Sequence[str]] = None,
         kg_mechanisms: Sequence[str] = (), window_months: Optional[int] = None) -> dict:
    cfg = config.load_config()
    budget = config.INTENSITY[intensity]
    win = config.time_windows(window_months or cfg["window_months"], cfg["core_years"])
    disc = detect_disciplines(" ".join([topic, *variants, *abstractions]))
    home_disc = [d["id"] for d in disc] or []
    home_sources = sources_for(home_disc[:2])
    explicit_lanes = bool(lanes)
    lanes = list(lanes or (LANES if budget["lanes"] >= 4 else LANES[: budget["lanes"]]))
    if not explicit_lanes and intensity == "quick" and "contradictory" not in lanes:
        lanes = ["in_domain", "contradictory"]
    mech_idx = mechanisms_index()
    structs = match_structures(" ".join([topic, *abstractions]), structures)
    k = budget["max_queries_per_lane"]
    qs: List[PlannedQuery] = []

    if "in_domain" in lanes:
        texts = [topic] + list(variants)
        for t in texts[:k]:
            qs.append(PlannedQuery("in_domain", t, "direct topic / agent-supplied variant", home_sources,
                                   date_from=win["core_from"]))
        if "life_science" in home_disc:
            qs.append(PlannedQuery("in_domain", topic, "recent preprints (bioRxiv/medRxiv via Europe PMC)",
                                   ["europepmc"], date_from=win["recent_from"], preprints_only=True))
        qs.append(PlannedQuery("in_domain", topic, "foundational work (no date floor)", home_sources[:2]))

    if "adjacent" in lanes:
        cand: List[PlannedQuery] = []
        for a in abstractions:
            cand.append(PlannedQuery("adjacent", a, "agent-supplied abstract problem statement",
                                     sources_for(["cs_ml", "statistics"]), date_from=win["core_from"]))
        for s in structs:
            for q in s["abstract_queries"]:
                cand.append(PlannedQuery("adjacent", q, f"shared structure '{s['id']}' ({s['match']})",
                                         sources_for(["cs_ml", "statistics"]), date_from=win["core_from"],
                                         meta={"structure": s["id"]}))
            for f in s["adjacent_fields"][:2]:
                cand.append(PlannedQuery("adjacent", f"{f} {s['abstract_queries'][0].split(' in ')[0]}",
                                         f"adjacent field '{f}' sharing structure '{s['id']}'",
                                         sources_for(detect_disciplines_ids(f)), date_from=win["core_from"],
                                         meta={"structure": s["id"], "field": f}))
        qs += _dedupe_q(cand)[: max(k, len(abstractions))]

    if "distant" in lanes:
        mech_ids: List[str] = []
        for m in list(mechanisms) + list(kg_mechanisms):
            if m in mech_idx and m not in mech_ids:
                mech_ids.append(m)
        for s in structs:
            for m in s["candidate_mechanisms"]:
                if m not in mech_ids:
                    mech_ids.append(m)
        anchor = (abstractions[0] if abstractions else (structs[0]["abstract_queries"][0] if structs else topic))
        anchor_terms = " ".join(_key_terms(anchor)[:4])
        cand = []
        for mid in mech_ids:
            m = mech_idx[mid]
            far = [f for f in m["fields"] if f not in home_disc[:1]]
            if not far:
                continue
            cand.append(PlannedQuery("distant", f"{m['query_terms'][0]} {anchor_terms}",
                                     f"mechanism '{mid}' studied in {far}; same abstract structure, different field",
                                     sources_for(far[:2]), date_from=win["core_from"],
                                     meta={"mechanism": mid, "fields": far}))
            found = m["query_terms"][-1]
            if len(found.split()) < 2:
                found = f"{found} {m['label']}" if found.lower() not in m["label"].lower() else f"{m['label']} review"
            cand.append(PlannedQuery("distant", found,
                                     f"mechanism '{mid}' foundations in {far[0]} (no date floor)",
                                     sources_for(far[:1]), meta={"mechanism": mid, "fields": far}))
        qs += _dedupe_q(cand)[: 2 * k]

    if "contradictory" in lanes:
        cand = []
        for s in structs:
            for p in s["contradiction_probes"]:
                cand.append(PlannedQuery("contradictory", p, f"probe against assumptions behind '{s['id']}'",
                                         list(dict.fromkeys(home_sources + ["openalex"])),
                                         meta={"structure": s["id"]}))
        for a in assumptions:
            cand.append(PlannedQuery("contradictory", f"{a} violated limitations",
                                     f"evidence against assumption '{a}'", home_sources))
        for m in methods:
            cand.append(PlannedQuery("contradictory", f"{m} fails limitations benchmark re-evaluation",
                                     f"failure modes / re-evaluations of '{m}'", home_sources))
        cand.append(PlannedQuery("contradictory", f"{' '.join(_key_terms(topic)[:5])} benchmark evaluation bias leakage",
                                 "evaluation-protocol critiques for the topic", home_sources))
        qs += _dedupe_q(cand)[:k]

    return {"topic": topic, "intensity": intensity, "budget": budget, "windows": win,
            "disciplines": disc, "home_sources": home_sources,
            "structures": [{"id": s["id"], "match": s["match"], "hits": s["hits"]} for s in structs],
            "queries": [q.to_dict() for q in _dedupe_q(qs)],
            "notes": ["Budgets are upper bounds, not quotas.",
                      "Trigger-matched structures are unconfirmed: confirm or pass --structure/--abstraction.",
                      "Distant-lane queries come from mechanism structure, not from topic keywords."]
            + (["WARNING: contradictory lane not searched (explicit --lane); counter-evidence coverage is missing."]
               if "contradictory" not in lanes else [])}


def detect_disciplines_ids(text: str) -> List[str]:
    return [d["id"] for d in detect_disciplines(text)][:2] or ["cs_ml", "statistics"]


def _key_terms(text: str) -> List[str]:
    stop = set("a an the of for and or in on to with by from via using is are under at as its prediction "
               "predicting model models learning".split())
    return [t for t in re.findall(r"[A-Za-z][A-Za-z\-]+", text) if t.lower() not in stop]


def _dedupe_q(qs: List[PlannedQuery]) -> List[PlannedQuery]:
    seen, out = set(), []
    for q in qs:
        key = (q.lane, q.text.lower().strip(), q.preprints_only, q.date_from is None)
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out
