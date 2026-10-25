"""Case C: "研究空间细胞扰动预测，并主动从其他学科寻找可以迁移的方法。"
Problem-driven transfer with synthetic method signatures. Verifies structure-based distant lanes, structural
(not lexical) matching, applicability vs project facts, negative-transfer risks, hypothesis storage, idea cards
without single scores, lineage tracing and graph export."""

from __future__ import annotations

from conftest import ok, run, write_json

REQUEST = "研究空间细胞扰动预测，并主动从其他学科寻找可以迁移的方法。"

PROBLEM = {
    "source_domain": "spatial transcriptomics",
    "original_problem": "predict spatially resolved cellular responses to genetic perturbations in tissue",
    "mathematical_abstraction": "map unpaired control/perturbed cell distributions on a spatial graph",
    "mechanisms": ["graphical-models"],
    "required_assumptions": ["locality-of-interactions"],
    "data_structure": ["unpaired cell populations", "spatial graph", "expression vectors"],
    "supervision": ["unpaired distributions"],
    "invariances": ["permutation of cells"],
    "problem_structures": ["intervention-response-prediction", "unpaired-distribution-alignment",
                           "spatially-structured-local-interaction"],
}
SIGS = {
    "method:fixture-ot-cell-response": {
        "source_domain": "single-cell computational biology",
        "original_problem": "map unpaired control to perturbed single-cell populations",
        "mathematical_abstraction": "learn a transport map between unpaired distributions",
        "core_operators": ["sinkhorn", "input convex network"], "mechanisms": ["optimal-transport"],
        "required_assumptions": ["meaningful-ground-cost", "comparable-supports"],
        "data_structure": ["unpaired cell populations", "expression vectors"], "supervision": ["unpaired distributions"],
        "invariances": ["permutation of cells"],
        "problem_structures": ["unpaired-distribution-alignment", "intervention-response-prediction"]},
    "method:fixture-equivariant-particles": {
        "source_domain": "computational physics",
        "original_problem": "predict forces on interacting particles",
        "mathematical_abstraction": "E(n)-equivariant message passing on geometric graphs",
        "core_operators": ["message passing"], "mechanisms": ["symmetry-equivariance", "graphical-models"],
        "required_assumptions": ["known-symmetry-group", "locality-of-interactions"],
        "data_structure": ["spatial graph", "point cloud"], "supervision": ["regression"],
        "invariances": ["rotation", "permutation of cells"],
        "problem_structures": ["spatially-structured-local-interaction", "symmetric-structured-objects"]},
    "method:fixture-spatial-clustering": {
        "source_domain": "spatial transcriptomics",
        "original_problem": "cluster spatially resolved cellular expression in tissue after perturbations",
        "mathematical_abstraction": "low-rank factorization of count matrices",
        "core_operators": ["nmf"], "mechanisms": ["low-rank-structure"],
        "required_assumptions": ["signal-approximately-low-rank"], "data_structure": ["count matrix"],
        "supervision": ["unsupervised"], "problem_structures": ["noisy-measurement-inverse-problem"]},
}


def _setup(env):
    ok("project", "init", "--name", "spatial-perturb", "--goal", "spatial perturbation response prediction")
    pr = ok("project", "problem", write_json(env.tmp / "problem.json", PROBLEM))
    for m, s in SIGS.items():
        ok("signature", "add", m, write_json(env.tmp / f"{m.split(':')[1]}.json", s),
           "--location", "synthetic fixture signature")
    return pr["problem_id"]


def test_case_c_transfer_flow(env):
    assert ok("route", REQUEST)["mode"] == "transfer"
    pid = _setup(env)

    plan = ok("landscape", "plan", "spatial perturbation response prediction in tissue", "--structure",
              "intervention-response-prediction", "--structure", "unpaired-distribution-alignment")
    distant = [q for q in plan["queries"] if q["lane"] == "distant"]
    assert distant and {q["meta"]["mechanism"] for q in distant} & {"optimal-transport", "causal-identification",
                                                                    "control-theory", "dynamical-systems"}

    scan = ok("transfer", "scan", "--min-structural", "0.0")
    cands = {c["method_id"]: c for c in scan["candidates"]}
    ot = cands["method:fixture-ot-cell-response"]
    assert "optimal-transport" in ot["new_mechanisms_for_target"]
    assert ot["structural_similarity"] > cands["method:fixture-spatial-clustering"]["structural_similarity"]
    lex = cands["method:fixture-spatial-clustering"]
    assert lex["lexical_similarity"] >= ot["lexical_similarity"] or any("lexical_only" in f for f in lex["flags"])
    assert scan["candidates"][0]["method_id"] != "method:fixture-spatial-clustering"
    assert "prior_transfer" in scan and scan["prior_transfer"]["note"]

    ok("project", "fact", "meaningful-ground-cost", "true", "--note", "expression distance after normalization")
    ok("project", "fact", "mass-conservation-or-unbalanced-relaxation", "false",
       "--note", "perturbation kills cells: proportions change")
    chk = ok("transfer", "check", "method:fixture-ot-cell-response")
    states = {r["assumption"]: r["state"] for r in chk["assumptions"]}
    assert states["meaningful-ground-cost"] == "satisfied"
    assert states["mass-conservation-or-unbalanced-relaxation"] == "violated"
    assert states["comparable-supports"] == "unknown"
    assert any(r["type"] == "assumption_violated" for r in chk["negative_transfer_risks"])

    rec = ok("transfer", "record", "method:fixture-ot-cell-response", "--rationale",
             "shared unpaired-alignment structure; OT adds a coupling the graph model lacks")
    tid = rec["transfer_id"]
    assert rec["status"] == "hypothesis"
    t = ok("kg", "show", tid)
    assert t["node"]["status"] == "hypothesis"
    probe = ok("kg", "show", pid)
    assert any(e["type"] == "VIOLATES_ASSUMPTION" for e in probe["out"])

    sc = ok("ideate", "scaffold", "--from", tid)
    assert tid in sc["sources"] and sc["risks"]["negative_transfer"]
    bad = dict(sc, score=8.5)
    r = ok("ideate", "add", write_json(env.tmp / "bad.json", bad))
    assert not r["stored"] and any("single score" in e for e in r["errors"])
    lvl = lambda l, why: {"level": l, "rationale": why}  # noqa: E731
    card = dict(sc)
    card.pop("_instructions", None)
    card.update({
        "question": "Can unbalanced OT on a spatial graph predict perturbation responses where cell proportions change?",
        "shared_structure": sc["shared_structure"] or {"problem_structures": ["unpaired-distribution-alignment"]},
        "mechanism_hypothesis": "an unbalanced transport coupling constrained by spatial neighbourhoods captures "
                                "redistribution of cell states that a local graph model cannot",
        "distinction_from_prior": "prior OT methods ignore spatial context; spatial models ignore unpaired coupling",
        "falsifiable_predictions": [{"prediction": "gain over graph baseline grows with proportion change",
                                     "refuted_if": "no gain on perturbations with large proportion shifts"}],
        "risks": {"fails_if": ["ground cost not meaningful after batch effects"],
                  "negative_transfer": sc["risks"]["negative_transfer"]},
        "evidence": {"existing": [tid], "missing": ["check: comparable-supports"]},
        "innovation_type": ["cross_domain_concept_transfer", "inductive_bias"],
        "source_domains": ["single-cell computational biology", "spatial transcriptomics"],
        "dimensions": {"importance": lvl("high", "proportion changes are common"),
                       "mechanism_plausibility": lvl("medium", "assumption violated -> needs unbalanced OT"),
                       "novelty": lvl("unknown", "prior-transfer search not yet run"),
                       "evidence_base": lvl("low", "no local experiment yet"),
                       "transferability": lvl("medium", "2 of 3 assumptions satisfied or unknown"),
                       "risk": lvl("high", "mass conservation violated")}})
    added = ok("ideate", "add", write_json(env.tmp / "idea.json", card))
    assert added["stored"] and added["status"] == "hypothesis"

    lin = ok("graph", "lineage", added["idea_id"])
    srcs = {e["src"] for e in lin["derived_from"]}
    assert tid in srcs and "method:fixture-ot-cell-response" in srcs
    assert "mechanism:optimal-transport" in srcs
    assert any(k.startswith("domain:") for k in lin["nodes"])

    mm = run("graph", "export", "--view", "transfer", "--format", "mermaid")[1]
    assert "POTENTIALLY_TRANSFERS_TO" in mm and "-.->" in mm
    html_p = env.tmp / "g.html"
    ok("graph", "export", "--view", "mechanism", "--format", "html", "--out", html_p)
    assert "<svg" in html_p.read_text(encoding="utf-8")
    rep = run("report", "transfer")[1]
    assert "Negative Transfer Risk" in rep and "Hypothesis" in rep and "violated" in rep
