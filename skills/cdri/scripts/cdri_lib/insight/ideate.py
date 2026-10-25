"""Innovation hypothesis cards. A card is a *proposal*: stored as status=hypothesis with lineage edges from
every source it was derived from. Single aggregate scores are rejected; dimensions are qualitative + rationale."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import project as proj
from ..ids import parse_identifier, slug
from ..kg.store import KnowledgeBase

REQUIRED = ["question", "sources", "shared_structure", "mechanism_hypothesis", "distinction_from_prior",
            "falsifiable_predictions", "risks", "evidence", "innovation_type", "dimensions"]
DIMENSIONS = ["importance", "mechanism_plausibility", "novelty", "evidence_base", "transferability", "risk"]
LEVELS = {"low", "medium", "high", "unknown"}
INNOVATION_TYPES = {"problem_definition", "theory_link", "inductive_bias", "evaluation_paradigm",
                    "mechanism_explanation", "negative_result_insight", "identifiability_or_ceiling_analysis",
                    "cross_domain_concept_transfer", "method_combination"}
BANNED_KEYS = {"score", "total_score", "overall_score", "novelty_score", "rank"}


def validate(card: Dict[str, Any], kb: KnowledgeBase, project: Optional[str] = None) -> Dict[str, Any]:
    errors, warnings = [], []
    for k in REQUIRED:
        if not card.get(k):
            errors.append(f"missing '{k}'")
    for k in BANNED_KEYS & set(card):
        errors.append(f"'{k}' is not allowed: do not summarize an idea with a single score; use 'dimensions'")
    dims = card.get("dimensions") or {}
    for d in DIMENSIONS:
        v = dims.get(d)
        if not isinstance(v, dict) or v.get("level") not in LEVELS or not v.get("rationale"):
            errors.append(f"dimensions.{d} needs {{level: low|medium|high|unknown, rationale}}")
    preds = card.get("falsifiable_predictions") or []
    for i, p in enumerate(preds):
        if not isinstance(p, dict) or not p.get("prediction") or not p.get("refuted_if"):
            errors.append(f"falsifiable_predictions[{i}] needs 'prediction' and 'refuted_if'")
    ev = card.get("evidence") or {}
    if not isinstance(ev, dict) or "existing" not in ev or "missing" not in ev:
        errors.append("evidence must list both 'existing' and 'missing'")
    risks = card.get("risks") or {}
    if isinstance(risks, dict) and not risks.get("fails_if"):
        errors.append("risks.fails_if (conditions under which the idea does not hold) is required")
    types = set(card.get("innovation_type") or [])
    bad = types - INNOVATION_TYPES
    if bad:
        errors.append(f"unknown innovation_type {sorted(bad)}; allowed {sorted(INNOVATION_TYPES)}")
    if types == {"method_combination"}:
        warnings.append("innovation_type is only 'method_combination': explain what new inductive bias, problem "
                        "definition or mechanism the combination introduces, or reconsider the idea")
    unresolved = []
    for s in card.get("sources") or []:
        sid = s if s.split(":", 1)[0] in ("mechanism", "method", "experiment", "failure", "limitation", "result",
                                          "transfer", "claim", "problem", "paper", "assumption", "signature") \
            else parse_identifier(s).canonical
        if not kb.get_node(sid):
            unresolved.append(s)
    if unresolved:
        warnings.append(f"sources not in the knowledge base (lineage will be incomplete): {unresolved}")
    pdata = proj.load(project)
    if pdata.get("frozen_decisions") and "respects_frozen_decisions" not in card:
        errors.append("project has frozen decisions: card must state respects_frozen_decisions (true/false + note)")
    domains = set(card.get("source_domains") or [])
    if len(domains) < 2:
        warnings.append("fewer than two source_domains listed: is this really a cross-domain idea?")
    return {"errors": errors, "warnings": warnings, "unresolved_sources": unresolved}


def add(card: Dict[str, Any], kb: KnowledgeBase, project: Optional[str] = None) -> Dict[str, Any]:
    rep = validate(card, kb, project)
    if rep["errors"]:
        return {"stored": False, **rep}
    iid = f"idea:{slug(card.get('id') or card['question'], 70)}"
    prov = {"source_type": "agent", "source_ref": ",".join(card["sources"]), "extractor": "agent",
            "note": "innovation hypothesis; not a finding"}
    store = kb.p if (kb.p and card.get("project_specific", True)) else kb.g
    r = store.upsert_node(iid, "ResearchIdea", card["question"][:200],
                          props={k: v for k, v in card.items() if k != "id"}, status="hypothesis", prov=prov,
                          overwrite=True, ledger_has=kb.g.ledger_has)
    for s in card["sources"]:
        sid = s if ":" in s and s.split(":", 1)[0] in ("mechanism", "method", "experiment", "failure", "limitation",
                                                       "result", "transfer", "claim", "problem", "paper",
                                                       "assumption", "signature") else parse_identifier(s).canonical
        if kb.get_node(sid):
            kb.add_edge(sid, "INSPIRES_HYPOTHESIS", iid, status="hypothesis", prov=prov)
    if kb.p:
        pdata = proj.load(project)
        kb.add_edge(iid, "PART_OF_PROJECT", proj.project_node_id(pdata), status="user_reported",
                    prov={"source_type": "user", "source_ref": "ideate", "extractor": "cli"})
    return {"stored": True, "idea_id": iid, "status": r["status"], **rep}


def scaffold(kb: KnowledgeBase, transfer_id: Optional[str] = None, project: Optional[str] = None) -> Dict[str, Any]:
    card: Dict[str, Any] = {k: None for k in REQUIRED}
    card["dimensions"] = {d: {"level": "unknown", "rationale": ""} for d in DIMENSIONS}
    card["falsifiable_predictions"] = [{"prediction": "", "refuted_if": ""}]
    card["evidence"] = {"existing": [], "missing": []}
    card["risks"] = {"fails_if": [], "negative_transfer": []}
    card["innovation_type"] = []
    card["source_domains"] = []
    card["sources"] = []
    if transfer_id:
        t = kb.get_node(transfer_id)
        if t:
            p = t["props"]
            comp = p.get("comparison") or {}
            card["sources"] = [transfer_id, p.get("method")] + [f"mechanism:{m}" for m in
                                                                (comp.get("facets", {}).get("mechanisms") or {}).get("shared", [])]
            card["shared_structure"] = {f: v.get("shared") for f, v in (comp.get("facets") or {}).items()
                                        if v and v.get("shared")}
            appl = p.get("applicability") or {}
            card["risks"]["negative_transfer"] = appl.get("negative_transfer_risks", [])
            card["evidence"]["missing"] = [f"check: {u}" for u in appl.get("unknown_to_check", [])]
    pdata = proj.load(project)
    if pdata.get("frozen_decisions"):
        card["respects_frozen_decisions"] = {"value": None, "note": "", "frozen": pdata["frozen_decisions"]}
    card["_instructions"] = ("Fill every field. dimensions: level + rationale each; no single score. "
                             "falsifiable_predictions need refuted_if. evidence.existing cites KB ids/DOIs.")
    return card
