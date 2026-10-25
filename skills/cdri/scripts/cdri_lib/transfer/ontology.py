"""Mechanism / problem-structure ontology: seed assets + KG-discovered categories, alias resolution,
ancestor expansion. Unknown terms become *discovered* categories instead of being dropped."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .. import config
from ..ids import norm_text, slug

_seed_cache: Optional[Dict[str, dict]] = None


def seed_mechanisms() -> Dict[str, dict]:
    global _seed_cache
    if _seed_cache is None:
        _seed_cache = {m["id"]: m for m in config.load_asset("mechanisms.json")["mechanisms"]}
    return _seed_cache


def seed_structures() -> Dict[str, dict]:
    return {s["id"]: s for s in config.load_asset("problem_structures.json")["structures"]}


def _alias_table() -> Dict[str, str]:
    t: Dict[str, str] = {}
    for mid, m in seed_mechanisms().items():
        for a in [mid, m["label"], *m.get("aliases", [])]:
            t[norm_text(a)] = mid
    return t


def resolve_mechanism(term: str, kb=None) -> Tuple[str, bool]:
    """Return (mechanism_id, known). Exact alias first, then KG aliases, then containment."""
    n = norm_text(term)
    table = _alias_table()
    if n in table:
        return table[n], True
    if kb is not None:
        for nid in kb.resolve_alias(term, "Mechanism"):
            return nid.split(":", 1)[1], True
    best = None
    for alias, mid in table.items():
        if len(alias) >= 4 and (f" {alias} " in f" {n} "):
            if best is None or len(alias) > len(best[0]):
                best = (alias, mid)
    if best:
        return best[1], True
    return slug(term, 60), False


def ancestors(mid: str, kb=None) -> Set[str]:
    seen: Set[str] = set()
    stack = [mid]
    seeds = seed_mechanisms()
    while stack:
        cur = stack.pop()
        parents = list(seeds.get(cur, {}).get("parents", []))
        if kb is not None:
            parents += [e["dst"].split(":", 1)[1] for e in kb.edges(src=f"mechanism:{cur}", etype="SUBCLASS_OF")]
        for p in parents:
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def ensure_mechanism_node(kb, mid: str, label: Optional[str] = None, discovered: bool = False,
                          prov: Optional[dict] = None) -> str:
    nid = f"mechanism:{mid}"
    seed = seed_mechanisms().get(mid)
    if seed:
        if not kb.get_node(nid):
            kb.upsert_node(nid, "Mechanism", seed["label"], props={k: seed[k] for k in
                           ("fields", "operators", "typical_assumptions", "failure_conditions") if k in seed},
                           status="vocabulary", aliases=seed.get("aliases", []))
            for p in seed.get("parents", []):
                ensure_mechanism_node(kb, p)
                kb.add_edge(nid, "SUBCLASS_OF", f"mechanism:{p}", status="vocabulary")
        return nid
    if not kb.get_node(nid):
        kb.upsert_node(nid, "Mechanism", label or mid, props={"discovered": True},
                       status="agent_inference" if prov else "unverified",
                       prov=prov or None, aliases=[label] if label else [])
    return nid


def assumption_id(text: str) -> str:
    return slug(text, 70)
