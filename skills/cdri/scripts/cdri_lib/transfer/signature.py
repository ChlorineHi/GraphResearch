"""Method Signature: the transferable abstraction of a method, normalized against the ontology."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..ids import norm_text, slug
from .ontology import assumption_id, resolve_mechanism, seed_structures

FIELDS = ["source_domain", "original_problem", "mathematical_abstraction", "core_operators", "mechanisms",
          "inductive_biases", "required_assumptions", "data_structure", "supervision", "invariances",
          "complexity", "generalization_mechanism", "failure_conditions", "potential_target_domains",
          "problem_structures"]
LIST_FIELDS = {"core_operators", "mechanisms", "inductive_biases", "required_assumptions", "data_structure",
               "supervision", "invariances", "failure_conditions", "potential_target_domains", "problem_structures"}
REQUIRED = ["source_domain", "original_problem", "mathematical_abstraction", "mechanisms", "required_assumptions",
            "data_structure", "supervision"]


def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [x if isinstance(x, str) else (x.get("id") or x.get("text") or str(x)) for x in v]


def normalize(sig: Dict[str, Any], kb=None) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    out: Dict[str, Any] = {}
    for f in FIELDS:
        v = sig.get(f)
        out[f] = _as_list(v) if f in LIST_FIELDS else (v or "")
    missing = [f for f in REQUIRED if not out[f]]
    if missing:
        warnings.append(f"signature missing fields {missing}: matching on these facets will be weak")
    mechs, discovered = [], []
    for m in out["mechanisms"]:
        mid, known = resolve_mechanism(m, kb)
        if mid not in mechs:
            mechs.append(mid)
        if not known:
            discovered.append({"id": mid, "label": m})
    out["mechanisms"] = mechs
    out["_discovered_mechanisms"] = discovered
    if discovered:
        warnings.append(f"new mechanism categories discovered (stored as agent_inference): "
                        f"{[d['id'] for d in discovered]}")
    out["required_assumptions"] = [assumption_id(a) for a in out["required_assumptions"]]
    out["failure_conditions"] = [assumption_id(a) for a in out["failure_conditions"]]
    for f in ("data_structure", "supervision", "invariances", "core_operators", "inductive_biases"):
        out[f] = [slug(x, 60) for x in out[f]]
    known_structs = seed_structures()
    ps = []
    for s in out["problem_structures"]:
        sid = slug(s, 60)
        if sid not in known_structs:
            warnings.append(f"problem structure {sid!r} not in seed ontology (kept as discovered)")
        ps.append(sid)
    out["problem_structures"] = ps
    out["source_domain"] = norm_text(out["source_domain"]).replace(" ", "_") if out["source_domain"] else ""
    return out, warnings


def signature_id(method_id: str) -> str:
    return "signature:" + method_id.split(":", 1)[-1]
