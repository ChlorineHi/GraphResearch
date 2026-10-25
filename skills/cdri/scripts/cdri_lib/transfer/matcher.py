"""Structural matching between method signatures / problem signatures, applicability reasoning against
project facts, and negative-transfer risk. Output is a facet breakdown - never a single verdict."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set

from ..ids import norm_text, slug
from .ontology import ancestors, seed_mechanisms

FACETS = {"mechanisms": 0.22, "problem_structures": 0.2, "data_structure": 0.14, "supervision": 0.1,
          "core_operators": 0.1, "required_assumptions": 0.1, "invariances": 0.08, "inductive_biases": 0.06}
STOP = set("a an the of for and or in on to with by from via using is are under at as its prediction predicting "
           "model models learning data based new".split())


def _set(sig: Dict[str, Any], f: str) -> Set[str]:
    return {x for x in sig.get(f) or [] if x}


def _mech_expand(ms: Set[str], kb=None) -> Dict[str, float]:
    out = {m: 1.0 for m in ms}
    for m in ms:
        for a in ancestors(m, kb):
            out.setdefault(a, 0.5)
    return out


def facet_score(a: Dict[str, Any], b: Dict[str, Any], f: str, kb=None) -> Optional[Dict[str, Any]]:
    sa, sb = _set(a, f), _set(b, f)
    if not sa or not sb:
        return None
    if f == "mechanisms":
        ea, eb = _mech_expand(sa, kb), _mech_expand(sb, kb)
        keys = set(ea) | set(eb)
        num = sum(min(ea.get(k, 0), eb.get(k, 0)) for k in keys)
        den = sum(max(ea.get(k, 0), eb.get(k, 0)) for k in keys)
        shared = sorted(k for k in keys if ea.get(k) and eb.get(k))
        return {"score": round(num / den, 3) if den else 0.0, "shared": shared}
    inter = sa & sb
    return {"score": round(len(inter) / len(sa | sb), 3), "shared": sorted(inter)}


def _tokens(*texts: str) -> Set[str]:
    return {t for t in norm_text(" ".join(texts)).split() if t not in STOP and len(t) > 2}


def lexical_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    ta = _tokens(a.get("original_problem", ""), a.get("source_domain", ""), " ".join(a.get("potential_target_domains") or []))
    tb = _tokens(b.get("original_problem", ""), b.get("source_domain", ""), " ".join(b.get("potential_target_domains") or []))
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 3)


def compare(a: Dict[str, Any], b: Dict[str, Any], kb=None) -> Dict[str, Any]:
    facets: Dict[str, Any] = {}
    num = den = 0.0
    for f, wgt in FACETS.items():
        r = facet_score(a, b, f, kb)
        facets[f] = r if r is not None else {"score": None, "shared": [], "note": "missing on one side"}
        if r is not None:
            num += wgt * r["score"]
            den += wgt
    structural = round(num / den, 3) if den else 0.0
    coverage = round(den / sum(FACETS.values()), 3)
    lex = lexical_similarity(a, b)
    da, db = a.get("source_domain") or "", b.get("source_domain") or ""
    flags = []
    if lex >= 0.3 and structural < 0.25:
        flags.append("lexical_only: shared vocabulary but little shared structure - do not treat as transferable")
    if structural >= 0.35 and da and db and da != db:
        flags.append("structural_bridge: shared structure across different domains")
    if da and da == db:
        flags.append("same_domain")
    if coverage < 0.5:
        flags.append("low_facet_coverage: signatures too sparse for a reliable comparison")
    return {"structural_similarity": structural, "facet_coverage": coverage, "lexical_similarity": lex,
            "facets": facets, "flags": flags,
            "note": "structural_similarity is a retrieval aid, not evidence that transfer will work"}


def problem_match(problem: Dict[str, Any], method_sig: Dict[str, Any], kb=None) -> Dict[str, Any]:
    """Problem-driven comparison: shared problem structure matters; mechanism *difference* is the opportunity."""
    c = compare(problem, method_sig, kb)
    cur = _set(problem, "mechanisms")
    new = sorted(_set(method_sig, "mechanisms") - cur)
    c["new_mechanisms_for_target"] = new
    if not new and cur:
        c["flags"].append("no_new_mechanism: method relies on mechanisms the target approach already uses")
    return c


def _fact_value(facts: Dict[str, Any], key: str):
    if key in facts:
        return facts[key]
    nk = slug(key)
    for k, v in facts.items():
        if slug(k) == nk:
            return v
    return None


def applicability(source_sig: Dict[str, Any], facts: Dict[str, Any], target: Optional[Dict[str, Any]] = None,
                  kb=None) -> Dict[str, Any]:
    """Check source-method assumptions / failure conditions against target project facts.
    facts: {assumption_or_condition_id: true | false | "unknown", "_notes": {...}}"""
    target = target or {}
    rows, violated, unknown = [], [], []
    mech_assumptions = []
    for m in source_sig.get("mechanisms") or []:
        seed = seed_mechanisms().get(m) or {}
        mech_assumptions += [(a, m) for a in seed.get("typical_assumptions", [])]
    req = [(a, "method") for a in source_sig.get("required_assumptions") or []] + mech_assumptions
    seen = set()
    for a, origin in req:
        if a in seen:
            continue
        seen.add(a)
        v = _fact_value(facts, a)
        state = "satisfied" if v is True else "violated" if v is False else "unknown"
        rows.append({"assumption": a, "origin": origin, "state": state,
                     "note": (facts.get("_notes") or {}).get(a)})
        (violated if state == "violated" else unknown if state == "unknown" else []).append(a)
    fails = []
    mech_fails = [(f, m) for m in source_sig.get("mechanisms") or [] for f in
                  (seed_mechanisms().get(m) or {}).get("failure_conditions", [])]
    for fcond, origin in [(f, "method") for f in source_sig.get("failure_conditions") or []] + mech_fails:
        v = _fact_value(facts, fcond)
        state = "present" if v is True else "absent" if v is False else "unknown"
        fails.append({"failure_condition": fcond, "origin": origin, "state": state})
    risks = []
    for a in violated:
        risks.append({"type": "assumption_violated", "detail": a,
                      "implication": "mechanism may not apply as-is; needs redefinition or a relaxed variant"})
    for f in fails:
        if f["state"] == "present":
            risks.append({"type": "failure_condition_present", "detail": f["failure_condition"],
                          "implication": "known failure regime of this mechanism"})
    sup_s, sup_t = _set(source_sig, "supervision"), _set(target, "supervision")
    if sup_s and sup_t and not (sup_s & sup_t):
        risks.append({"type": "supervision_mismatch", "detail": f"source {sorted(sup_s)} vs target {sorted(sup_t)}",
                      "implication": "training objective must be redefined; source evidence may not carry over"})
    ds_s, ds_t = _set(source_sig, "data_structure"), _set(target, "data_structure")
    if ds_s and ds_t and not (ds_s & ds_t):
        risks.append({"type": "data_structure_mismatch", "detail": f"source {sorted(ds_s)} vs target {sorted(ds_t)}",
                      "implication": "input representation must be re-derived"})
    if facts.get("data_scale") and source_sig.get("complexity"):
        risks.append({"type": "scale_check", "detail": f"target scale {facts['data_scale']} vs source complexity "
                      f"{source_sig['complexity']}", "implication": "verify compute/memory feasibility"})
    return {"assumptions": rows, "failure_conditions": fails, "negative_transfer_risks": risks,
            "unknown_to_check": unknown + [f["failure_condition"] for f in fails if f["state"] == "unknown"],
            "summary": {"violated": len(violated), "unknown": len(unknown), "satisfied":
                        sum(1 for r in rows if r["state"] == "satisfied"), "risks": len(risks)}}


def signatures(kb) -> List[dict]:
    out = []
    for n in kb.nodes("MethodSignature"):
        method = next((e["src"] for e in kb.edges(dst=n["id"], etype="HAS_SIGNATURE")), None)
        out.append({"signature_id": n["id"], "method_id": method, "sig": n["props"], "status": n["status"]})
    return out


def candidates(kb, target: Dict[str, Any], *, exclude_method: Optional[str] = None, k: int = 10,
               min_structural: float = 0.15, problem_mode: bool = True) -> List[dict]:
    out = []
    for s in signatures(kb):
        if s["method_id"] == exclude_method:
            continue
        c = problem_match(target, s["sig"], kb) if problem_mode else compare(target, s["sig"], kb)
        if c["structural_similarity"] < min_structural:
            continue
        out.append({"method_id": s["method_id"], "signature_id": s["signature_id"],
                    "source_domain": s["sig"].get("source_domain"), **c})
    out.sort(key=lambda x: (-x["structural_similarity"], x["lexical_similarity"]))
    return out[:k]


def prior_transfer_check(kb, mechanisms: Sequence[str], target_domain: str) -> Dict[str, Any]:
    """Methods in the target domain already using the same mechanism (from the KB), plus queries to verify."""
    hits = []
    for m in mechanisms:
        for e in kb.edges(dst=f"mechanism:{m}", etype="USES_MECHANISM"):
            dom = [x["dst"] for x in kb.edges(src=e["src"], etype="IN_DOMAIN")]
            if any(target_domain and slug(target_domain) in d for d in dom):
                hits.append({"mechanism": m, "method": e["src"], "domains": dom})
    seeds = seed_mechanisms()
    queries = [f"{(seeds.get(m) or {}).get('query_terms', [m.replace('-', ' ')])[0]} {target_domain.replace('_', ' ')}"
               for m in mechanisms]
    return {"known_in_kb": hits, "verify_with_queries": queries,
            "note": "absence in the KB is not evidence of novelty; run the queries (lane=distant/in_domain)"}


def record_transfer(kb, method_id: str, problem_id: str, comparison: Dict[str, Any],
                    appl: Optional[Dict[str, Any]] = None, rationale: str = "") -> Dict[str, Any]:
    tid = f"transfer:{slug(method_id.split(':', 1)[1], 40)}--{slug(problem_id.split(':', 1)[1], 40)}"
    prov = {"source_type": "agent", "source_ref": f"{method_id} -> {problem_id}", "extractor": "cli",
            "note": "structural match + applicability; untested"}
    props = {"method": method_id, "problem": problem_id, "comparison": comparison, "applicability": appl,
             "rationale": rationale}
    r = kb.upsert_node(tid, "TransferHypothesis", f"{method_id} → {problem_id}", props=props, status="hypothesis",
                       prov=prov, overwrite=True)
    kb.add_edge(method_id, "POTENTIALLY_TRANSFERS_TO", problem_id, status="hypothesis", prov=prov,
                props={"transfer": tid, "structural_similarity": comparison.get("structural_similarity")})
    kb.add_edge(method_id, "INSPIRES_HYPOTHESIS", tid, status="hypothesis", prov=prov)
    for e in kb.edges(dst=method_id, etype="USES_METHOD"):
        kb.add_edge(e["src"], "INSPIRES_HYPOTHESIS", tid, status="hypothesis", prov=prov)
    for m in (comparison.get("facets", {}).get("mechanisms") or {}).get("shared", []) + \
            comparison.get("new_mechanisms_for_target", []):
        if kb.get_node(f"mechanism:{m}"):
            kb.add_edge(f"mechanism:{m}", "INSPIRES_HYPOTHESIS", tid, status="hypothesis", prov=prov)
    if appl:
        for a in appl["assumptions"]:
            if a["state"] in ("violated", "satisfied"):
                aid = f"assumption:{a['assumption']}"
                kb.upsert_node(aid, "Assumption", a["assumption"].replace("-", " "), status="vocabulary")
                kb.add_edge(problem_id, "VIOLATES_ASSUMPTION" if a["state"] == "violated" else "SATISFIES_ASSUMPTION",
                            aid, status="user_reported",
                            prov={"source_type": "user", "source_ref": "project facts", "extractor": "cli"})
    return {"transfer_id": tid, "status": r["status"]}
