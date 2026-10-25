"""Case A: "调研最新的 TF–DNA binding specificity prediction，重点关注 unseen transcription factor generalization。"
Offline, against synthetic fixtures. Verifies routing, dynamic windows, four lanes, multi-source search with logged
failures, dedup of preprint/published versions, screening with reasons, report honesty, DOI verification,
full text + read plan + sentinel + ledger, code-to-method mapping and ledger-gated paper card ingestion."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import git_repo_copy, ok, run, write_json

TOPIC = "TF-DNA binding specificity prediction for unseen transcription factors"
REQUEST = "调研最新的 TF–DNA binding specificity prediction，重点关注 unseen transcription factor generalization。"


def _plan(env):
    p = env.tmp / "plan.json"
    ok("landscape", "plan", TOPIC, "--variant", "zero-shot transcription factor binding prediction",
       "--abstraction", "predict interactions between sequences and unseen entities described by descriptors",
       "--structure", "unseen-entity-interaction", "--structure", "sequence-to-function", "--out", p)
    return p


def test_case_a_route_plan_and_search(env):
    r = ok("route", REQUEST)
    assert r["mode"] == "landscape"

    plan = json.loads(_plan(env).read_text(encoding="utf-8"))
    assert plan["windows"]["recent_from"] == "2024-06-15"          # derived from CDRI_TODAY, not hardcoded
    assert {q["lane"] for q in plan["queries"]} == {"in_domain", "adjacent", "distant", "contradictory"}
    assert any(d["id"] == "life_science" for d in plan["disciplines"])

    s = ok("landscape", "run", "--plan", env.tmp / "plan.json", "--run-id", "caseA")
    statuses = {st for db in s["by_db"].values() for st in db}
    assert "ok" in statuses
    # every failure is reported, none silently dropped
    if "semantic_scholar" in s["by_db"]:
        assert s["by_db"]["semantic_scholar"].get("rate_limited")
    fail_dbs = {f["db"] for f in s["failures"]}
    assert fail_dbs, "fixture routes contain rate-limited / offline sources that must be reported"
    log = [json.loads(l) for l in (env.proj / ".cdri/runs/caseA/log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all("status" in e and "db" in e and "query" in e for e in log)

    recs = [json.loads(l) for l in (env.proj / ".cdri/runs/caseA/records.jsonl").read_text(encoding="utf-8").splitlines()]
    by_doi = {r.get("doi"): r for r in recs if r.get("doi")}
    p1 = by_doi["10.5555/cdri.fx.001"]
    assert p1["pub_status"] == "published"
    assert any(v.get("relation") == "preprint_version" and v.get("arxiv") == "9912.00001" for v in p1["versions"])
    assert sum(1 for r in recs if "Protein language model features" in r["title"]) == 1   # merged, not duplicated
    assert by_doi["10.1101/2026.03.01.000001"]["pub_status"] == "preprint"                 # bioRxiv
    assert by_doi["10.5555/cdri.fx.006"]["pub_status"] == "preprint"                       # posted-content
    assert by_doi["10.5555/cdri.fx.003"]["signals"]["recency"] != "recent"                 # foundational


def test_case_a_screen_report_verify(env):
    _plan(env)
    ok("landscape", "run", "--plan", env.tmp / "plan.json", "--run-id", "caseA")
    sug = ok("screen", "suggest", "--run", "caseA", "--tier", "focused")
    assert sug["candidates"]
    code, err = run("screen", "decide", "paper:doi:10.5555/cdri.fx.001", "--run", "caseA", "--tier", "deep",
                    "--reason", " ")
    assert code == 2 and "reason" in err["error"]
    ok("screen", "decide", "paper:doi:10.5555/cdri.fx.001", "--run", "caseA", "--tier", "deep",
       "--reason", "directly addresses unseen-TF generalization with a homology-aware split")
    ok("screen", "decide", "paper:doi:10.5555/cdri.fx.004", "--run", "caseA", "--tier", "focused",
       "--reason", "contradictory lane: benchmark leakage critique")

    rep = run("report", "landscape", "--run", "caseA")[1]
    assert "未完成的检索" in rep and "预印本" in rep and "正式发表" in rep
    assert "D. Contradictory" in rep and "AGENT" in rep
    assert "deep" in rep

    v = ok("paper", "verify", "doi:10.5555/cdri.fx.001", "--title",
           "[SYNTHETIC FIXTURE] Protein language model features enable binding specificity prediction for unseen "
           "transcription factors")
    assert v["verdict"] == "exists" and v["pub_status"] == "published"
    fake = ok("paper", "verify", "doi:10.5555/cdri.fx.999")
    assert fake["verdict"] == "not_found"
    mism = ok("paper", "verify", "doi:10.5555/cdri.fx.001", "--title", "A totally different title about galaxies")
    assert mism["verdict"] == "title_mismatch"
    pre = ok("paper", "verify", "doi:10.1101/2026.03.01.000001")
    assert pre["verdict"] in ("not_found", "exists", "unverifiable_now")


def _card(sha: str, repo: Path) -> dict:
    loc = lambda s: {"type": "paper_fulltext", "location": s}  # noqa: E731
    return {
        "paper_id": "arxiv:9912.00001", "title": "[SYNTHETIC FIXTURE] PLM-conditioned TF binding",
        "reading_depth": "deep",
        "method": {"name": "Fixture PLM-FiLM TF binding model", "introduced_here": True, "location": "2.1 Model"},
        "A_question": {"problem": {"id": "unseen-tf-binding-specificity",
                                   "text": "Predict DNA-binding specificity for transcription factors unseen in training",
                                   "source": loc("1 Introduction")},
                       "what_changed": ["problem_definition", "model_mechanism"]},
        "B_formulation": {
            "inputs": {"text": "one-hot DNA x and PLM embedding z of the DNA-binding domain", "source": loc("2.1 Model")},
            "objective": {"text": "pairwise within-TF ranking loss", "source": loc("2.2 Objective")},
            "assumptions": [{"id": "descriptor-carries-information-about-unseen-entities",
                             "text": "binding preferences vary smoothly in DBD embedding space",
                             "source": loc("2.2 Objective")}],
            "operators": [{"name": "FiLM conditioning", "text": "feature-wise scale/shift from z", "source": loc("2.1 Model")}],
            "equations": [{"label": "Eq. 1", "latex": "s(x,z)=w^T max_l(γ(z)⊙h_l(x)+β(z))", "role": "model",
                           "source": loc("2.1 Model")}]},
        "C_innovation": [
            {"statement": "TF identity enters only through a protein descriptor (FiLM), enabling unseen-TF prediction",
             "kind": "structure", "novel_vs_prior": "prior multi-task models use one output head per TF",
             "inductive_bias": "TF specificity is a smooth function of DBD embedding", "why_fits": "unseen entities",
             "source": loc("2.1 Model")},
            {"statement": "uses a transformer protein language model", "kind": "representation",
             "source": {"type": "paper_abstract", "location": "abstract"}}],
        "D_implementation": {
            "repo": {"url": "https://github.com/cdri-fixture/tfbind-fixture", "commit": sha, "official": True,
                     "location": "Code availability"},
            "items": [{"aspect": "hyperparameters", "text": "lr 0.001, batch 256, 30 epochs",
                       "source": {"type": "code", "location": "train.py:L37-L40", "commit": sha}}],
            "code_links": [
                {"formula": "Eq. 1", "path": "model.py", "symbol": "TFBindModel.forward", "lines": "25-31",
                 "status": "discrepancy", "note": "code uses mean pooling; Eq. 1 uses max pooling"},
                {"formula": "Eq. 2", "path": "losses.py", "symbol": "pairwise_ranking_loss", "lines": "6-14",
                 "status": "consistent"}]},
        "E_evidence": {
            "experiments": [{"text": "median per-TF Spearman 0.41 vs 0.33 nearest-neighbour baseline on held-out clusters",
                             "is_ood": True, "datasets": ["fixture-pbm"], "metrics": ["spearman"],
                             "protocol": {"split": "homology-aware", "aggregation": "median_per_tf"},
                             "source": loc("3 Results")}],
            "negative_results": [{"text": "near-baseline for families with <3 training members", "source": loc("3 Results")}],
            "limitations": {
                "author_acknowledged": [{"text": "fails for TF families absent in training",
                                         "source": loc("4 Discussion and Limitations")}],
                "inferred_from_results": [{"text": "random splits overstate generalization",
                                           "basis": "3 Results: 0.58 random vs 0.41 homology-aware"}],
                "agent_proposed": [{"text": "ranking loss may hide calibration failures across TFs",
                                    "rationale": "only within-TF order supervised"}]}},
        "F_signature": {
            "source_domain": "computational biology", "original_problem": "TF-DNA binding for unseen TFs",
            "mathematical_abstraction": "f(x, z) with generalization over descriptor space z",
            "core_operators": ["FiLM conditioning", "convolution"], "mechanisms": ["meta-learning-conditioning"],
            "inductive_biases": ["descriptor smoothness"],
            "required_assumptions": ["descriptor-carries-information-about-unseen-entities"],
            "data_structure": ["sequence", "entity descriptor"], "supervision": ["ranking"],
            "failure_conditions": ["unseen-entities-out-of-descriptor-distribution"],
            "problem_structures": ["unseen-entity-interaction", "sequence-to-function"],
            "potential_target_domains": ["drug-target interaction", "perturbation response for unseen perturbations"]},
    }


def test_case_a_fulltext_code_and_card(env):
    meta = ok("paper", "fetch", "arxiv:9912.00001", "--plan")
    assert meta["status"] == "ok" and meta["sentinel"] and meta["read_plan"]
    assert "https://github.com/cdri-fixture/tfbind-fixture" in meta["code_links"]
    parsed = Path(meta["parsed_path"]).read_text(encoding="utf-8")
    assert parsed.startswith("<!-- CDRI: UNTRUSTED EXTERNAL CONTENT")
    assert parsed.rstrip().endswith(f"<!-- END-OF-PAPER:{meta['sentinel']} -->")

    # a paper with no legal OA full text is reported as unavailable, with every attempt listed
    miss = ok("paper", "fetch", "doi:10.5555/cdri.fx.004")
    assert miss["status"] == "unavailable" and miss["tried"]

    repo, sha = git_repo_copy(env.tmp / "repo")
    an = ok("code", "analyze", repo)
    roles = set(an["by_role"])
    assert {"model", "loss", "train_loop"} <= roles
    assert an["repo"]["commit"] == sha
    show = run("code", "show", repo, "model.py", "--symbol", "TFBindModel.forward")[1]
    assert "h.mean(dim=-1)" in show

    card_p = write_json(env.tmp / "card.json", _card(sha, repo))
    # before reading anything: depth is downgraded and paper-sourced claims cannot be author_claim
    v0 = ok("paper", "validate", card_p)
    assert v0["reading_depth"] == "abstract"
    assert any("abstract/introduction" in w for w in v0["warnings"])     # innovation[1] from abstract
    # read the Methods section through the CLI (ledger), but not Results
    txt = run("paper", "section", "arxiv:9912.00001", "methods")[1]
    assert "FiLM" in txt and "ledger" in txt
    r1 = ok("paper", "ingest", write_json(env.tmp / "card1.json", _card(sha, repo)))
    assert r1["reading_depth"] == "deep"
    assert any("ledger" in w or "unverified" in w for w in r1["write_warnings"])   # Results not yet read
    res = ok("kg", "show", "result:paper-arxiv-9912-00001-0")
    assert res["node"]["status"] != "author_claim"

    method = ok("kg", "show", "method:fixture-plm-film-tf-binding-model")
    lim_edge = next(e for e in method["out"] if e["type"] == "HAS_LIMITATION"
                    and e["props"]["category"] == "author_acknowledged")
    assert lim_edge["status"] == "unverified"            # Discussion was not in the ledger at ingest time

    # full read confirmed with the sentinel hash; re-ingest does NOT silently upgrade -> pending promotions
    bad = ok("paper", "confirm", "arxiv:9912.00001", "deadbeef")
    assert bad["confirmed"] is False
    good = ok("paper", "confirm", "arxiv:9912.00001", meta["sentinel"])
    assert good["confirmed"]
    r2 = ok("paper", "ingest", write_json(env.tmp / "card2.json", _card(sha, repo)))
    assert any("not upgraded" in w.lower() for w in r2["write_warnings"])
    pend = {p["id"] for p in ok("kg", "pending")}
    assert {"result:paper-arxiv-9912-00001-0", lim_edge["id"]} <= pend
    pr = ok("kg", "promote", "result:paper-arxiv-9912-00001-0", "--status", "author_claim",
            "--source-type", "paper_fulltext", "--ref", "paper:arxiv:9912.00001", "--location", "3 Results")
    assert pr["promoted"]
    ok("kg", "promote", lim_edge["id"], "--status", "author_claim", "--source-type", "paper_fulltext",
       "--ref", "paper:arxiv:9912.00001", "--location", "4 Discussion and Limitations")

    method = ok("kg", "show", "method:fixture-plm-film-tf-binding-model")
    out = {(e["type"], e["dst"]): e for e in method["out"]}
    impl = [e for e in method["out"] if e["type"] == "IMPLEMENTED_BY"]
    assert any(e["props"].get("match") == "discrepancy" and e["status"] == "code_verified" for e in impl)
    lims = [e for e in method["out"] if e["type"] == "HAS_LIMITATION"]
    cats = {e["props"]["category"]: e["status"] for e in lims}
    assert cats["author_acknowledged"] == "author_claim"
    assert cats["inferred_from_results"] == "agent_inference"
    assert cats["agent_proposed"] == "hypothesis"
    innov = ok("kg", "show", "claim:paper-arxiv-9912-00001-innov-1")
    assert innov["node"]["status"] == "unverified"          # method detail from the abstract
    assert any(k[0] == "USES_MECHANISM" for k in out)
    # prompt-injection text in the paper had no effect on statuses
    paper = ok("kg", "show", "paper:arxiv:9912.00001")
    assert paper["node"]["status"] != "code_verified"

    _plan(env)
    ok("landscape", "run", "--plan", env.tmp / "plan.json", "--run-id", "caseA")   # registers the published version
    md = run("report", "paper", "--id", "arxiv:9912.00001")[1]
    assert "Deep Method Review" in md and "discrepancy" in md
    assert "paper:doi:10.5555/cdri.fx.001" in md and "差异未核对" in md     # preprint vs published version flagged
