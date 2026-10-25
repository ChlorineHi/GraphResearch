"""Unit tests: ids, epistemics, KG store rules, planner, dedupe, screening, metrics, audit, parsing, router,
matcher, logs, semantic search, exports, config, http fixtures."""

from __future__ import annotations

import json

import pytest

from conftest import write_json


# ---------------------------------------------------------------- ids
def test_identifier_parsing_and_canonical():
    from cdri_lib.ids import parse_identifier
    assert parse_identifier("https://doi.org/10.1038/S41586-020-2649-2").canonical == "paper:doi:10.1038/s41586-020-2649-2"
    assert parse_identifier("arXiv:2101.00001v3").canonical == "paper:arxiv:2101.00001"
    assert parse_identifier("10.48550/arXiv.2101.00001").canonical == "paper:arxiv:2101.00001"
    assert parse_identifier("https://arxiv.org/abs/2101.00001v2").canonical == "paper:arxiv:2101.00001"
    assert parse_identifier("PMID:123456").canonical == "paper:pmid:123456"
    assert parse_identifier("PMC765432").canonical == "paper:pmcid:PMC765432"


def test_preprint_doi_rules():
    from cdri_lib.retrieval.records import is_preprint_doi
    assert is_preprint_doi("10.1101/2026.03.01.000001")
    assert is_preprint_doi("10.48550/arXiv.2101.00001")
    assert not is_preprint_doi("10.1101/gr.123456.120")  # Genome Research (CSHL journal), not a preprint
    assert not is_preprint_doi("10.5555/cdri.fx.001")


# ---------------------------------------------------------------- epistemics / store
def test_status_caps_and_ledger_gate(env):
    from cdri_lib.kg.store import KnowledgeBase
    kb = KnowledgeBase(use_project=False)
    # author_claim from full text without a reading-ledger entry is refused
    r = kb.upsert_node("claim:x", "ScientificClaim", "x", status="author_claim",
                       prov={"source_type": "paper_fulltext", "source_ref": "paper:doi:10.5555/a", "location": "Methods"})
    assert r["status"] != "author_claim" and r["warnings"]
    kb.g.ledger_add("paper:doi:10.5555/a", "2 Methods", 100, "abc", "cli_read")
    r2 = kb.upsert_node("claim:y", "ScientificClaim", "y", status="author_claim",
                        prov={"source_type": "paper_fulltext", "source_ref": "paper:doi:10.5555/a",
                              "location": "2.1 Model"})
    assert r2["status"] == "author_claim"
    # agents cannot self-certify verified facts
    r3 = kb.upsert_node("claim:z", "ScientificClaim", "z", status="verified",
                        prov={"source_type": "agent", "source_ref": "me"})
    assert r3["status"] in ("agent_inference", "hypothesis", "unverified")
    # code_verified needs a commit
    r4 = kb.upsert_node("claim:c", "ScientificClaim", "c", status="code_verified",
                        prov={"source_type": "code", "source_ref": "repo", "location": "model.py:L1-L5"})
    assert r4["status"] != "code_verified"


def test_no_automatic_upgrade_and_promote(env):
    from cdri_lib.kg.store import KnowledgeBase
    kb = KnowledgeBase(use_project=False)
    kb.upsert_node("claim:h", "ScientificClaim", "h", status="hypothesis", prov={"source_type": "agent", "source_ref": "a"})
    kb.g.ledger_add("paper:doi:10.5555/b", "__FULL__", 1, "s", "sentinel_confirmed")
    r = kb.upsert_node("claim:h", "ScientificClaim", "h", status="author_claim",
                       prov={"source_type": "paper_fulltext", "source_ref": "paper:doi:10.5555/b", "location": "3"})
    assert r["status"] == "hypothesis" and any("NOT upgraded" in w for w in r["warnings"])
    assert any(p["id"] == "claim:h" for p in kb.g.pending_promotions())
    p = kb.promote("claim:h", "author_claim", {"source_type": "paper_fulltext", "source_ref": "paper:doi:10.5555/b",
                                               "location": "Results"})
    assert p["promoted"] and kb.get_node("claim:h")["status"] == "author_claim"


def test_contradiction_marks_contested_and_retract(env):
    from cdri_lib.kg.store import KnowledgeBase
    kb = KnowledgeBase(use_project=False)
    kb.upsert_node("claim:a", "ScientificClaim", "a", status="hypothesis", prov={"source_type": "agent", "source_ref": "x"})
    kb.upsert_node("claim:b", "ScientificClaim", "b", status="hypothesis", prov={"source_type": "agent", "source_ref": "x"})
    kb.add_edge("claim:a", "CONTRADICTS", "claim:b", status="agent_inference", prov={"source_type": "agent", "source_ref": "x"})
    assert kb.get_node("claim:b")["props"]["contested"] is True
    kb.retract("claim:a", "duplicate")
    assert all(n["id"] != "claim:a" for n in kb.nodes("ScientificClaim"))


def test_project_layer_separation(env, tmp_path):
    from cdri_lib.kg.store import KnowledgeBase
    p1, p2 = tmp_path / "p1", tmp_path / "p2"
    p1.mkdir(); p2.mkdir()
    kb1 = KnowledgeBase(str(p1))
    kb1.upsert_node("experiment:run1", "LocalExperiment", "run1", status="user_reported",
                    prov={"source_type": "user", "source_ref": "x"})
    kb1.upsert_node("mechanism:test-mech", "Mechanism", "test", status="vocabulary")
    kb2 = KnowledgeBase(str(p2))
    assert kb2.get_node("experiment:run1") is None          # project data stays local
    assert kb2.get_node("mechanism:test-mech") is not None  # global knowledge is shared


# ---------------------------------------------------------------- planner / windows / privacy
def test_dynamic_time_windows(env, monkeypatch):
    from cdri_lib import config
    w = config.time_windows(24, 5)
    assert w == {"today": "2026-06-15", "recent_from": "2024-06-15", "core_from": "2021-06-15"}
    monkeypatch.setenv("CDRI_TODAY", "2031-01-31")
    w2 = config.time_windows(12, 3)
    assert w2["recent_from"] == "2030-01-28" and w2["core_from"] == "2028-01-28"


def test_plan_has_four_lanes_and_structure_based_distant(env):
    from cdri_lib.retrieval.planner import plan
    p = plan("TF-DNA binding specificity prediction for unseen transcription factors",
             abstractions=["predict interactions for unseen entities described by descriptors"],
             structures=["unseen-entity-interaction"])
    lanes = {q["lane"] for q in p["queries"]}
    assert lanes == {"in_domain", "adjacent", "distant", "contradictory"}
    distant = [q for q in p["queries"] if q["lane"] == "distant"]
    assert all(q["meta"].get("mechanism") for q in distant)
    assert any(q["date_from"] is None for q in p["queries"])  # foundational lane without a date floor
    assert p["windows"]["recent_from"] == "2024-06-15"


def test_privacy_gate():
    from cdri_lib.retrieval.planner import privacy_check
    assert privacy_check(r"results in C:\Users\me\secret_run")
    assert privacy_check("token ghp_ABCDEFGHIJKLMNOPQRSTUV")
    assert not privacy_check("optimal transport single cell perturbation")


# ---------------------------------------------------------------- dedupe / screening
def _rec(**kw):
    from cdri_lib.retrieval.records import Record
    base = dict(title="t", source_db="x")
    base.update(kw)
    return Record(**base)


def test_dedupe_merges_preprint_into_published():
    from cdri_lib.retrieval.dedupe import deduplicate
    a = _rec(title="Deep models of binding for unseen factors", doi="10.5555/x.1", year=2026, venue="J",
             pub_status="published", status_evidence="crossref", source_db="crossref")
    b = _rec(title="Deep Models of Binding for Unseen Factors", arxiv="9912.00001", year=2025, venue="arXiv",
             pub_status="preprint", status_evidence="arxiv", source_db="arxiv")
    c = _rec(title="A different paper entirely about optimal transport", doi="10.5555/x.2", year=2026,
             pub_status="published", source_db="openalex")
    out = deduplicate([a, b, c])
    assert len(out) == 2
    m = next(r for r in out if r.doi == "10.5555/x.1")
    assert m.pub_status == "published"
    assert any(v.get("relation") == "preprint_version" for v in m.versions)


def test_screening_does_not_pad():
    from cdri_lib.retrieval.screening import annotate, suggest
    recs = [_rec(title="unseen transcription factor binding", year=2026, date="2026-01-01", abstract="binding",
                 found_by=[{"qid": "q1", "lane": "in_domain", "db": "x"}]),
            _rec(title="completely unrelated astronomy", year=2026, date="2026-01-01",
                 found_by=[{"qid": "q1", "lane": "in_domain", "db": "x"}])]
    annotate(recs, {"q1": "unseen transcription factor binding"}, 24)
    sel = suggest(recs, "focused", "standard", 0.25)
    assert len(sel) == 1  # no filler to reach a quota


# ---------------------------------------------------------------- metrics / audit
def test_metrics_known_values():
    from cdri_lib.audit import metrics as M
    assert M.pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert M.spearman([1, 2, 3, 4], [10, 20, 30, 25]) == pytest.approx(0.8)
    assert M.auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert M.rmse([0, 0], [3, 4]) == pytest.approx((12.5) ** 0.5)
    assert M.lookup("Spearman's rho")["id"] == "spearman"


def test_pooled_vs_grouped_metric(env, tmp_path):
    from cdri_lib.audit.metrics import recompute
    rows = ["group,true,pred"]
    for g, off in (("a", 0), ("b", 10)):
        for i in range(5):
            rows.append(f"{g},{off + i},{off + (4 - i)}")  # anti-correlated within group, offset between groups
    p = tmp_path / "p.csv"
    p.write_text("\n".join(rows), encoding="utf-8")
    r = recompute(str(p), "pearson", "true", "pred", ["group"])
    assert r["pooled"] > 0.8
    assert r["by_group"]["group"]["mean_over_groups"] < -0.9
    assert "warning" in r


def test_comparability_matrix():
    from cdri_lib.audit.integrity import comparability
    proto = {"split": "homology-aware", "split_unit": "tf_family", "aggregation": "median_per_tf"}
    res = comparability([
        {"id": "A", "metric": "spearman", "value": 0.41, "protocol": dict(proto)},
        {"id": "B", "metric": "spearman", "value": 0.58, "protocol": dict(proto, split="random")},
        {"id": "C", "metric": "pearson", "value": 0.5, "protocol": dict(proto)}])
    v = {(p["a"], p["b"]): p["verdict"] for p in res["pairs"]}
    assert v[("A", "B")] == "not_directly_comparable"
    assert v[("A", "C")] == "not_directly_comparable"
    assert not res["rankings_within_comparable_groups"]


def test_group_leakage(env, tmp_path):
    from cdri_lib.audit.integrity import split_leakage
    p = tmp_path / "s.csv"
    p.write_text("tf,family,split\nT1,F1,train\nT2,F1,test\nT3,F2,train\nT4,F3,test\n", encoding="utf-8")
    r = split_leakage(str(p), "split", ["family"])
    f = r["findings"][0]
    assert f["severity"] == "high" and f["n_shared"] == 1
    assert "tf" in r["hierarchy_columns_not_checked"]


# ---------------------------------------------------------------- parsing
def test_html_parsing_sections_and_math():
    from conftest import FIX
    from cdri_lib.paper.parse import html_to_md, sections
    md = html_to_md((FIX / "paper_tfbind.html").read_text(encoding="utf-8"))
    secs = sections(md)
    kinds = {s["kind"] for s in secs}
    assert {"methods", "results"} <= kinds
    assert "\\gamma(z)" in md  # equation alttext preserved


# ---------------------------------------------------------------- router
@pytest.mark.parametrize("text,mode", [
    ("调研最新的 TF–DNA binding specificity prediction，重点关注 unseen transcription factor generalization。", "landscape"),
    ("某个新模型训练正常，但在未见过的测试对象上泛化很差，甚至低于简单基线。", "diagnose"),
    ("研究空间细胞扰动预测，并主动从其他学科寻找可以迁移的方法。", "transfer"),
    ("模型性能提升有限，但我们发现了测量噪声上限、训练目标的局限和重要的机制反例。", "story"),
    ("在知识图谱里查一下之前读过的最优传输相关机制，并追溯迁移假设的来源", "graph"),
    ("/cdri audit 检查这个结果", "audit"),
    ("mode: paper 10.5555/cdri.fx.001", "paper"),
])
def test_router(text, mode):
    from cdri_lib.router import route
    assert route(text)["mode"] == mode


def test_router_explicit_wins():
    from cdri_lib.router import route
    r = route("/cdri landscape 迁移 跨领域 泛化很差")
    assert r["mode"] == "landscape" and r["explicit"]


# ---------------------------------------------------------------- matcher / signatures
def test_signature_normalization_aliases(env):
    from cdri_lib.transfer.signature import normalize
    sig, w = normalize({"source_domain": "Computational Physics", "original_problem": "x",
                        "mathematical_abstraction": "y", "mechanisms": ["Sinkhorn", "made-up-mechanism-xyz"],
                        "required_assumptions": ["Meaningful ground cost"], "data_structure": ["Point Clouds"],
                        "supervision": ["unpaired"]})
    assert "entropic-optimal-transport" in sig["mechanisms"] or "optimal-transport" in sig["mechanisms"]
    assert any(d["id"] == "made-up-mechanism-xyz" for d in sig["_discovered_mechanisms"])
    assert sig["required_assumptions"] == ["meaningful-ground-cost"]
    assert sig["source_domain"] == "computational_physics"


def test_lexical_only_flag():
    from cdri_lib.transfer.matcher import compare
    a = {"source_domain": "spatial_transcriptomics", "original_problem": "spatial cell perturbation response tissue",
         "mechanisms": ["graphical-models"], "problem_structures": ["intervention-response-prediction"],
         "data_structure": ["spatial-graph"], "supervision": ["unpaired-distributions"]}
    b = {"source_domain": "spatial_transcriptomics", "original_problem": "spatial cell tissue clustering perturbation",
         "mechanisms": ["low-rank-structure"], "problem_structures": ["noisy-measurement-inverse-problem"],
         "data_structure": ["count-matrix"], "supervision": ["unsupervised"]}
    c = compare(a, b)
    assert any(f.startswith("lexical_only") for f in c["flags"])
    assert c["structural_similarity"] < 0.25


# ---------------------------------------------------------------- logs / semantic / exports / config / http
def test_log_analysis(tmp_path):
    from cdri_lib.diagnose.logs import analyze_log
    rows = ["epoch,train_loss,val_loss,val_spearman"]
    for e in range(30):
        rows.append(f"{e},{1.0 / (e + 1):.5f},{0.6 + (0.0 if e > 8 else (9 - e) * 0.05):.5f},{min(0.3, 0.03 * e):.4f}")
    p = tmp_path / "log.csv"
    p.write_text("\n".join(rows), encoding="utf-8")
    r = analyze_log(str(p), metric_col="val_spearman", baseline=0.35)
    syms = {o["symptom"] for o in r["observations"]}
    assert {"plateau", "below_simple_baseline"} <= syms


def test_tfidf_semantic(env):
    from cdri_lib.kg import semantic
    from cdri_lib.kg.store import KnowledgeBase
    kb = KnowledgeBase(use_project=False)
    kb.upsert_node("method:a", "Method", "descriptor conditioned binding model", status="vocabulary")
    kb.upsert_node("method:b", "Method", "galaxy rotation curve fitting", status="vocabulary")
    hits = semantic.search(kb, "conditioning on descriptors for binding")["hits"]
    assert hits[0]["id"] == "method:a"


def test_mermaid_export_marks_weak_edges(env):
    from cdri_lib.kg import views
    from cdri_lib.kg.store import KnowledgeBase
    kb = KnowledgeBase(use_project=False)
    kb.upsert_node("method:a", "Method", "A", status="vocabulary")
    kb.upsert_node("mechanism:optimal-transport", "Mechanism", "OT", status="vocabulary")
    kb.add_edge("method:a", "USES_MECHANISM", "mechanism:optimal-transport", status="agent_inference",
                prov={"source_type": "agent", "source_ref": "x"})
    nodes, edges = views.subgraph(kb, "mechanism")
    mm = views.to_mermaid(nodes, edges)
    assert mm.startswith("flowchart LR") and "-.->|USES_MECHANISM|" in mm
    html = views.to_html(nodes, edges)
    assert "<svg" in html and "Dashed edge" in html


def test_config_rejects_secrets(env):
    from cdri_lib import config
    with pytest.raises(ValueError):
        config.save_config({"s2_api_key": "abc"})


def test_http_fixture_statuses(env):
    from cdri_lib import http
    with pytest.raises(http.HTTPFailure) as e:
        http.get("https://api.semanticscholar.org/graph/v1/paper/search?query=x")
    assert e.value.status == "rate_limited"
    with pytest.raises(http.Offline):
        http.get("https://dblp.org/search/publ/api?q=x")
    assert http.redact("https://x.org/?api_key=SECRET&q=1") == "https://x.org/?api_key=***&q=1"


def test_anti_bot_html_is_reported_as_blocked(env, tmp_path, monkeypatch):
    from cdri_lib import http
    (tmp_path / "bot.html").write_text("<!doctype html><html><title>Making sure you're not a bot!</title>",
                                       encoding="utf-8")
    (tmp_path / "routes.json").write_text(json.dumps([{"match": "dblp", "file": "bot.html", "status": 202}]),
                                          encoding="utf-8")
    monkeypatch.setenv("CDRI_FIXTURES", str(tmp_path))
    with pytest.raises(http.HTTPFailure) as e:
        http.get_json("https://dblp.org/search/publ/api?q=x&format=json")
    assert e.value.status == "blocked"
