"""Case D: "模型性能提升有限，但我们发现了测量噪声上限、训练目标的局限和重要的机制反例。"
Verifies: story routing, experiment records with artifacts, counterexamples as CONTRADICTS (contested, not
deleted), ledger-gated claims, aggregation-dependent metrics, Not-Directly-Comparable results, and a story check
that refuses to present hypotheses as established findings."""

from __future__ import annotations

import json

from conftest import ok, run, write_json

REQUEST = "模型性能提升有限，但我们发现了测量噪声上限、训练目标的局限和重要的机制反例。"


def test_case_d_story_flow(env):
    r = ok("route", REQUEST)
    assert r["mode"] == "story"
    ok("project", "init", "--name", "tfbind-ceiling", "--goal", "understand limited gains")

    # noise ceiling: replicate agreement measured locally (synthetic artifact file)
    art = env.tmp / "replicates.csv"
    art.write_text("tf,rep1,rep2\n" + "\n".join(f"TF{i},{i % 7},{(i * 3) % 7}" for i in range(30)), encoding="utf-8")
    ceil = ok("audit", "metric", art, "--metric", "spearman", "--true", "rep1", "--pred", "rep2")
    e1 = ok("experiment", "record", "--name", "replicate noise ceiling", "--outcome", "positive",
            "--metrics", json.dumps({"replicate_spearman": ceil["pooled"], "model_spearman": 0.41}),
            "--interpretation", "model performance is close to the replicate ceiling", "--artifact", art)
    assert e1["status"] == "experiment_observed"

    neg = {k: "unknown" for k in ("module_ineffective", "problem_misformulated", "supervision_cannot_identify",
                                  "data_quality_limits", "baseline_captures_signal", "new_mechanistic_insight")}
    neg["supervision_cannot_identify"] = "ranking objective cannot identify absolute affinity"
    e2 = ok("experiment", "record", "--name", "absolute affinity head", "--outcome", "null",
            "--metrics", '{"calibration_error": 0.3}', "--negative", json.dumps(neg))
    assert e2["status"] == "user_reported"

    # a paper claim (agent tried to cite Results without reading them -> not accepted as author_claim)
    c = ok("kg", "node", "claim:fixture-additivity", "ScientificClaim",
           "binding energies are additive across positions", "--status", "author_claim",
           "--source-type", "paper_fulltext", "--ref", "doi:10.5555/cdri.fx.003", "--location", "Results")
    assert c["status"] != "author_claim" and c["warnings"]
    # mechanistic counterexample from a local experiment
    cx = env.tmp / "cooperativity.csv"
    cx.write_text("pair,observed,additive\nA,2.1,1.0\nB,1.9,1.1\n", encoding="utf-8")
    ok("experiment", "record", "--name", "cooperative pair counterexample", "--outcome", "mixed",
       "--metrics", '{"n_pairs": 2}', "--artifact", cx)
    ln = ok("kg", "link", "experiment:cooperative-pair-counterexample", "CONTRADICTS", "claim:fixture-additivity",
            "--status", "experiment_observed", "--source-type", "local_experiment", "--artifact", cx)
    assert ln["status"] == "experiment_observed"
    claim = ok("kg", "show", "claim:fixture-additivity")
    assert claim["node"]["props"]["contested"] is True     # preserved and marked, not deleted
    assert ok("kg", "contradictions")

    # aggregation changes the number -> must be reported
    p = env.tmp / "preds.csv"
    p.write_text("tf,true,pred\n" + "\n".join(f"T{g},{g * 5 + i},{g * 5 + (4 - i)}" for g in range(3) for i in range(5)),
                 encoding="utf-8")
    m = ok("audit", "metric", p, "--metric", "spearman", "--true", "true", "--pred", "pred", "--group", "tf")
    assert m["pooled"] > 0 > m["by_group"]["tf"]["mean_over_groups"] and "warning" in m
    res = write_json(env.tmp / "results.json", {"results": [
        {"id": "ours", "metric": "spearman", "value": 0.41,
         "protocol": {"split": "homology-aware", "aggregation": "median_per_tf", "unit_of_analysis": "tf"}},
        {"id": "paperX", "metric": "Spearman's rho", "value": 0.58,
         "protocol": {"split": "random", "aggregation": "pooled", "unit_of_analysis": "probe"}}]})
    cmp_ = ok("audit", "compare", "--results", res)
    assert cmp_["pairs"][0]["verdict"] == "not_directly_comparable"
    assert not cmp_["rankings_within_comparable_groups"]

    sc = ok("story", "scaffold")
    assert sc["sections"]["observation_or_gap"]["candidates"]
    assert "counterexample" in sc["contribution_types"]

    over = {"core_question": "Is TF binding prediction limited by the assay rather than the model?",
            "main_contribution": {"type": ["noise_ceiling_or_identifiability"], "text": "ceiling analysis"},
            "claims": [
                {"step": "important_question", "text": "how close are models to the assay ceiling",
                 "evidence": [], "asserted_as": "hypothesis"},
                {"step": "observation_or_gap", "text": "model is near the replicate ceiling",
                 "evidence": ["experiment:replicate-noise-ceiling"], "asserted_as": "established"},
                {"step": "mechanistic_insight", "text": "cooperativity causes the residual error; we prove additivity fails",
                 "evidence": ["claim:fixture-additivity"], "asserted_as": "hypothesis"},
                {"step": "critical_evidence", "text": "counterexample pairs",
                 "evidence": ["experiment:cooperative-pair-counterexample"], "asserted_as": "established"},
                {"step": "boundary_conditions", "text": "in vitro only", "evidence": [], "asserted_as": "hypothesis"}],
            "alternative_explanations": [], "limitations": []}
    bad = ok("story", "check", write_json(env.tmp / "story_bad.json", over))
    assert not bad["ok"]
    joined = " ".join(bad["problems"])
    assert "proof language" in joined and "alternative explanations" in joined
    good = dict(over, alternative_explanations=[{"text": "batch effects in replicates", "how_ruled_out_or_open": "open"}],
                limitations=["two counterexample pairs only"])
    good["claims"][2] = {"step": "mechanistic_insight", "text": "cooperativity may explain part of the residual error",
                         "evidence": ["claim:fixture-additivity"], "asserted_as": "hypothesis"}
    chk = ok("story", "check", write_json(env.tmp / "story_good.json", good))
    assert chk["ok"], chk
    syn = run("report", "synthesis")[1]
    assert "冲突证据" in syn and "claim:fixture-additivity" in syn
