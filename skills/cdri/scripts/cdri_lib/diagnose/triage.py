"""Literature-guided diagnosis: trivial-error gate, symptom -> ordered problem types -> checks -> targeted
queries, worksheets, and conclusions (including negative results) written to the project KB."""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .. import config
from .. import project as proj
from ..ids import slug
from ..kg.store import KnowledgeBase

NONTRIVIAL_MIN_ATTEMPTS = 2


def taxonomy() -> dict:
    return config.load_asset("diagnosis_taxonomy.json")


def triage(symptom: str, *, log_observations: Sequence[dict] = (), attempts: int = 0, reproducible: bool = False,
           topic: str = "", mechanisms: Sequence[str] = (), components: Sequence[str] = (),
           routine_checks_done: Sequence[str] = (), project: Optional[str] = None) -> dict:
    tax = taxonomy()
    text = symptom + " " + " ".join(o.get("detail", "") + " " + o.get("symptom", "") for o in log_observations)
    for t in tax["trivial_patterns"]:
        if re.search(t["pattern"], text):
            return {"trivial": True, "literature_search": "not_recommended", "matched": t["pattern"],
                    "advice": t["advice"],
                    "reason": "routine software error: a literature review would be wasted cost"}
    sym_hits = []
    for s in tax["symptoms"]:
        if any(p.lower() in text.lower() for p in s["patterns"]) or \
                any(o.get("symptom") == s["id"] for o in log_observations):
            sym_hits.append(s)
    ptypes = {p["id"]: p for p in tax["problem_types"]}
    cand_ids: List[str] = []
    for s in sym_hits:
        for c in s["candidates"]:
            if c not in cand_ids:
                cand_ids.append(c)
    if not cand_ids:
        cand_ids = ["implementation_bug", "data_processing_error", "evaluation_mismatch"]
    for always in ("implementation_bug", "data_processing_error", "evaluation_mismatch"):
        if always not in cand_ids:
            cand_ids.append(always)
    ordered = sorted((ptypes[c] for c in cand_ids), key=lambda p: p["order"])
    done = set(routine_checks_done)
    local_first = [p for p in ordered if not p.get("literature")]
    lit_types = [p for p in ordered if p.get("literature")]
    lit_ok = (reproducible or attempts >= NONTRIVIAL_MIN_ATTEMPTS) and \
        all(p["id"] in done for p in local_first)
    queries = []
    mech = mechanisms[0].replace("-", " ") if mechanisms else "inductive bias"
    comp = components[0] if components else "model"
    for p in lit_types:
        if p.get("query_hint"):
            q = p["query_hint"].format(topic=topic or "the task", mechanism=mech, component=comp)
            queries.append({"problem_type": p["id"], "query": q.strip(),
                            "lanes": ["in_domain", "adjacent", "contradictory"] +
                                     (["distant"] if p["id"] in ("inductive_bias_mismatch", "identifiability_limit",
                                                                 "representation_failure") else [])})
    pdata = proj.load(project)
    reasons = []
    if not lit_ok:
        if not (reproducible or attempts >= NONTRIVIAL_MIN_ATTEMPTS):
            reasons.append(f"problem not yet shown reproducible (attempts={attempts} < {NONTRIVIAL_MIN_ATTEMPTS})")
        missing = [p["id"] for p in local_first if p["id"] not in done]
        if missing:
            reasons.append(f"local checks not completed: {missing} (pass --done ID after running them)")
    return {
        "trivial": False, "symptoms": [s["id"] for s in sym_hits],
        "candidate_problem_types": [{"id": p["id"], "label": p["label"], "order": p["order"],
                                     "checks": p["checks"], "needs_literature": p.get("literature", False)}
                                    for p in ordered],
        "literature_search": "recommended" if lit_ok else "deferred",
        "literature_gate_reasons": reasons or ["reproducible non-trivial problem and local checks done"],
        "targeted_queries": queries,
        "frozen_decisions": pdata.get("frozen_decisions", []),
        "rules": ["Do not add model complexity as the default fix.",
                  "Do not change research direction or rewrite the model based on one bad run.",
                  "Record negative findings with `cdri diagnose conclude`."]}


def worksheet_dir(project: Optional[str]) -> Path:
    d = config.project_dir(project) / "diagnoses"
    d.mkdir(parents=True, exist_ok=True)
    return d


def open_worksheet(symptom: str, result: dict, project: Optional[str] = None,
                   kb: Optional[KnowledgeBase] = None) -> dict:
    did = _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slug(symptom, 30)
    ws = {"id": did, "symptom": symptom, "opened": _dt.datetime.now().isoformat(timespec="seconds"),
          "status": "open", "triage": result, "checks": [], "evidence": [], "conclusions": []}
    (worksheet_dir(project) / f"{did}.json").write_text(json.dumps(ws, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = kb or KnowledgeBase(project)
    pdata = proj.load(project)
    nid = f"diagnosis:{did}"
    kb.upsert_node(nid, "Diagnosis", symptom[:200], props={"worksheet": did, "status": "open"}, status="user_reported",
                   prov={"source_type": "user", "source_ref": "diagnosis worksheet", "extractor": "cli"})
    kb.add_edge(nid, "PART_OF_PROJECT", proj.project_node_id(pdata), status="user_reported",
                prov={"source_type": "user", "source_ref": "diagnosis worksheet", "extractor": "cli"})
    return ws


def load_ws(did: str, project: Optional[str] = None) -> dict:
    return json.loads((worksheet_dir(project) / f"{did}.json").read_text(encoding="utf-8"))


def save_ws(ws: dict, project: Optional[str] = None) -> None:
    (worksheet_dir(project) / f"{ws['id']}.json").write_text(json.dumps(ws, indent=2, ensure_ascii=False),
                                                             encoding="utf-8")


def add_check(did: str, check: str, outcome: str, artifact: Optional[str] = None, project: Optional[str] = None) -> dict:
    ws = load_ws(did, project)
    ws["checks"].append({"check": check, "outcome": outcome, "artifact": artifact,
                         "artifact_exists": bool(artifact and Path(artifact).exists()),
                         "t": _dt.datetime.now().isoformat(timespec="seconds")})
    save_ws(ws, project)
    return ws


def conclude(did: str, *, hypothesis: str, problem_type: str, verdict: str, mechanism_explanation: str = "",
             supporting: Sequence[str] = (), opposing: Sequence[str] = (), papers: Sequence[str] = (),
             uncertainty: str = "", artifact: Optional[str] = None, project: Optional[str] = None,
             kb: Optional[KnowledgeBase] = None) -> dict:
    if verdict not in ("supported", "refuted", "inconclusive"):
        raise ValueError("verdict must be supported | refuted | inconclusive")
    if verdict == "supported" and not supporting:
        raise ValueError("a 'supported' diagnosis needs at least one supporting fact (--for)")
    if not opposing and verdict == "supported":
        note = "no opposing facts listed: state explicitly what would refute this diagnosis"
    else:
        note = ""
    kb = kb or KnowledgeBase(project)
    ws = load_ws(did, project)
    art_ok = bool(artifact and Path(artifact).exists())
    fid = f"failure:{slug(did, 40)}-{slug(problem_type, 30)}"
    ev_prov = {"source_type": "local_experiment", "source_ref": artifact or f"diagnosis {did}",
               "location": artifact, "artifact_exists": art_ok, "extractor": "agent",
               "note": "; ".join(supporting)}
    r = (kb.p or kb.g).upsert_node(fid, "FailureMode", hypothesis[:200],
                       props={"problem_type": problem_type, "verdict": verdict, "mechanism": mechanism_explanation,
                              "supporting": list(supporting), "opposing": list(opposing),
                              "uncertainty": uncertainty, "diagnosis": did},
                       status="experiment_observed" if art_ok else "user_reported", prov=ev_prov)
    dnode = f"diagnosis:{did}"
    kb.add_edge(dnode, "HAS_FAILURE_MODE", fid, status="agent_inference",
                prov={"source_type": "agent", "source_ref": did, "extractor": "agent"},
                props={"verdict": verdict})
    for pid in papers:
        from ..ids import parse_identifier
        p = parse_identifier(pid).canonical
        kb.add_edge(p, "EXPLAINS_FAILURE", fid, status="agent_inference",
                    prov={"source_type": "agent", "source_ref": p, "extractor": "agent",
                          "note": "literature mechanism proposed as explanation; analogy, not proof"},
                    props={"verdict": verdict})
    concl = {"hypothesis": hypothesis, "problem_type": problem_type, "verdict": verdict,
             "mechanism_explanation": mechanism_explanation, "supporting": list(supporting),
             "opposing": list(opposing), "papers": list(papers), "uncertainty": uncertainty,
             "artifact": artifact, "artifact_exists": art_ok, "failure_node": fid, "node_status": r["status"]}
    ws["conclusions"].append(concl)
    if verdict == "supported":
        ws["status"] = "diagnosed"
    save_ws(ws, project)
    return {"conclusion": concl, "warnings": r["warnings"] + ([note] if note else [])}


def record_experiment(*, name: str, config_desc: Dict[str, Any], metrics: Dict[str, Any], outcome: str,
                      interpretation: str = "", tests: Sequence[str] = (), artifact: Optional[str] = None,
                      negative_analysis: Optional[Dict[str, str]] = None, project: Optional[str] = None,
                      kb: Optional[KnowledgeBase] = None) -> dict:
    """Record an experiment that was actually run. Negative/null outcomes require the negative-result analysis."""
    if outcome not in ("positive", "negative", "null", "mixed"):
        raise ValueError("outcome must be positive | negative | null | mixed")
    questions = ["module_ineffective", "problem_misformulated", "supervision_cannot_identify",
                 "data_quality_limits", "baseline_captures_signal", "new_mechanistic_insight"]
    if outcome in ("negative", "null"):
        missing = [q for q in questions if not (negative_analysis or {}).get(q)]
        if missing:
            raise ValueError(f"negative/null results need the negative-result analysis fields {missing} "
                             "(answer 'unknown' where not known)")
    kb = kb or KnowledgeBase(project)
    pdata = proj.load(project)
    eid = f"experiment:{slug(name, 60)}"
    art_ok = bool(artifact and Path(artifact).exists())
    prov = {"source_type": "local_experiment", "source_ref": artifact or name, "location": artifact,
            "artifact_exists": art_ok, "extractor": "agent"}
    r = kb.upsert_node(eid, "LocalExperiment", name,
                       props={"config": config_desc, "metrics": metrics, "outcome": outcome,
                              "interpretation": interpretation, "artifact": artifact,
                              "negative_analysis": negative_analysis or {},
                              "t": _dt.datetime.now().isoformat(timespec="seconds")},
                       status="experiment_observed", prov=prov, overwrite=True)
    kb.add_edge(eid, "PART_OF_PROJECT", proj.project_node_id(pdata), status="user_reported",
                prov={"source_type": "user", "source_ref": "experiment record", "extractor": "cli"})
    for t in tests:
        kb.add_edge(eid, "TESTS", t, status="agent_inference",
                    prov={"source_type": "agent", "source_ref": eid, "extractor": "agent"},
                    props={"outcome": outcome})
    if interpretation:
        cid = f"claim:{slug(name, 50)}-interpretation"
        (kb.p or kb.g).upsert_node(cid, "ScientificClaim", interpretation[:200], props={"claim_type": "interpretation",
                       "experiment": eid}, status="agent_inference",
                       prov={"source_type": "agent", "source_ref": eid, "extractor": "agent"})
        kb.add_edge(eid, "SUPPORTS", cid, status="agent_inference",
                    prov={"source_type": "agent", "source_ref": eid, "extractor": "agent"})
    return {"experiment_id": eid, "status": r["status"], "warnings": r["warnings"]}
