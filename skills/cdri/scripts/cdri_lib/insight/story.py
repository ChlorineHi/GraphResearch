"""Scientific story: Important Question -> Observation/Gap -> Mechanistic Insight -> Approach ->
Critical Evidence -> Implication -> Boundary Conditions. Scaffold is filled from the KB with evidence status;
`check` refuses to call something established unless its evidence is verified/observed/author-claimed."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import project as proj
from ..kg import epistemics as ep
from ..kg.store import KnowledgeBase

ARC = ["important_question", "observation_or_gap", "mechanistic_insight", "approach", "critical_evidence",
       "scientific_implication", "boundary_conditions"]
ESTABLISHED_OK = {"verified", "code_verified", "experiment_observed", "author_claim"}
CONTRIBUTION_TYPES = ["problem_definition", "theoretical_framework", "inductive_bias", "mechanistic_understanding",
                      "benchmark_or_evaluation", "counterexample", "noise_ceiling_or_identifiability",
                      "failure_explanation", "cross_domain_concept"]


def _brief(n: dict) -> dict:
    return {"id": n["id"], "label": n["label"], "type": n["type"], "status": n["status"],
            "evidence_label": ep.label(n["status"])}


def scaffold(kb: KnowledgeBase, project: Optional[str] = None) -> Dict[str, Any]:
    pdata = proj.load(project)
    nodes = kb.p.nodes() if kb.p else []
    exps = [n for n in nodes if n["type"] == "LocalExperiment"]
    fails = [n for n in nodes if n["type"] == "FailureMode"]
    ideas = [n for n in nodes if n["type"] in ("ResearchIdea",)] + kb.nodes("TransferHypothesis")
    claims = [n for n in nodes if n["type"] == "ScientificClaim"]
    neg = [e for e in exps if e["props"].get("outcome") in ("negative", "null", "mixed")]
    pos = [e for e in exps if e["props"].get("outcome") == "positive"]
    problems = [n for n in kb.nodes("ResearchProblem") if n["props"].get("project") == pdata.get("name")]
    lims = []
    for t in kb.edges(etype="HAS_LIMITATION"):
        n = kb.get_node(t["dst"])
        if n:
            lims.append(n)
    sections = {
        "important_question": {"candidates": [_brief(n) for n in problems],
                               "prompt": "Why does this question matter beyond a metric gain? Which untested "
                                         "assumption of existing work does it expose?"},
        "observation_or_gap": {"candidates": [_brief(n) for n in neg + fails],
                               "prompt": "Which unexpected observation, contradiction or negative result motivates "
                                         "the work? Is it reproducible?"},
        "mechanistic_insight": {"candidates": [_brief(n) for n in ideas + claims],
                                "prompt": "What mechanism explains the observation? Status must stay "
                                          "hypothesis/agent_inference until tested."},
        "approach": {"candidates": [], "prompt": "How does the approach follow from the insight (not from "
                                                 "component stacking)?"},
        "critical_evidence": {"candidates": [_brief(n) for n in pos + neg],
                              "prompt": "Which experiments discriminate the insight from alternatives?"},
        "scientific_implication": {"candidates": [], "prompt": "What changes in how the field should model / "
                                                               "evaluate this problem?"},
        "boundary_conditions": {"candidates": [_brief(n) for n in lims[:20]],
                                "prompt": "Where does the claim stop holding? Which assumptions must hold?"},
    }
    gaps = [k for k, v in sections.items() if not v["candidates"] and k not in ("approach", "scientific_implication")]
    return {"project": pdata.get("name"), "arc": ARC, "sections": sections, "evidence_gaps": gaps,
            "contribution_types": CONTRIBUTION_TYPES, "frozen_decisions": pdata.get("frozen_decisions", []),
            "template": {
                "core_question": "", "central_hypothesis": "", "main_contribution": {"type": [], "text": ""},
                "research_gap": "",
                "claims": [{"step": "observation_or_gap", "text": "", "evidence": ["kb-id"],
                            "asserted_as": "established | hypothesis"}],
                "alternative_explanations": [{"text": "", "how_ruled_out_or_open": ""}],
                "limitations": [""], "broader_implications": [""],
                "status": "draft_narrative (not a verified conclusion)"}}


def check(story: Dict[str, Any], kb: KnowledgeBase) -> Dict[str, Any]:
    problems: List[str] = []
    notes: List[str] = []
    steps = {c.get("step") for c in story.get("claims") or []}
    for s in ("important_question", "observation_or_gap", "mechanistic_insight", "critical_evidence",
              "boundary_conditions"):
        if s not in steps:
            problems.append(f"arc step '{s}' has no claim")
    for i, c in enumerate(story.get("claims") or []):
        ev = c.get("evidence") or []
        statuses = []
        for e in ev:
            n = kb.get_node(e)
            if n is None:
                ed = next((x for x in kb.edges() if x["id"] == e), None)
                statuses.append(ed["status"] if ed else "missing")
            else:
                statuses.append(n["status"])
        c["_evidence_status"] = dict(zip(ev, statuses))
        if "missing" in statuses:
            problems.append(f"claims[{i}] cites evidence not in the KB: "
                            f"{[e for e, s in zip(ev, statuses) if s == 'missing']}")
        if c.get("asserted_as") == "established":
            if not ev:
                problems.append(f"claims[{i}] asserted as established without evidence")
            elif not any(s in ESTABLISHED_OK for s in statuses):
                problems.append(f"claims[{i}] asserted as established but evidence is only "
                                f"{sorted(set(statuses))} -> must be framed as hypothesis")
        if c.get("step") == "critical_evidence" and not any(s == "experiment_observed" for s in statuses) \
                and c.get("asserted_as") == "established":
            notes.append(f"claims[{i}]: critical evidence without a locally observed experiment relies on "
                         "literature only")
        txt = (c.get("text") or "").lower()
        if any(w in txt for w in ("prove", "demonstrate that", "establish that", "证明")) and \
                c.get("asserted_as") != "established":
            problems.append(f"claims[{i}] uses proof language while being a hypothesis")
        if any(w in txt for w in ("causes", "causal", "导致")) and not any(
                s == "experiment_observed" for s in statuses):
            notes.append(f"claims[{i}] uses causal language without interventional evidence")
    if not story.get("alternative_explanations"):
        problems.append("no alternative explanations listed")
    if not story.get("limitations"):
        problems.append("no limitations listed")
    mc = (story.get("main_contribution") or {}).get("type") or []
    if mc and set(mc) == {"benchmark_or_evaluation"} and "sota" in (story.get("main_contribution") or {}).get("text", "").lower():
        notes.append("contribution framed as SOTA only; is there a scientific question behind it?")
    return {"ok": not problems, "problems": problems, "notes": notes,
            "status": "narrative passes evidence checks (still a narrative, not new evidence)" if not problems
            else "narrative over-claims or is incomplete"}
