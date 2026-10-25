"""Case E: knowledge reuse across projects. Project 1 reads a paper deeply and stores a method + signature;
project 2 retrieves the mechanism knowledge, sees which papers/sources support it, reuses the cached full text
(no re-parse), records a counterexample, keeps its local data private and traces transfer-hypothesis lineage.
Also covers incremental refresh (new papers, preprint->published, failed refresh does not advance checkpoint)."""

from __future__ import annotations

import json

import fixture_builder
from conftest import ok, run, write_json
from test_case_a_landscape import _card
from test_case_c_transfer import PROBLEM


def test_case_e_cross_project_reuse(env):
    p1, p2 = env.tmp / "project1", env.tmp / "project2"
    p1.mkdir(); p2.mkdir()
    # ---- project 1: deep read + card
    m1 = ok("paper", "fetch", "arxiv:9912.00001", project=p1)
    ok("paper", "confirm", "arxiv:9912.00001", m1["sentinel"], project=p1)
    r = ok("paper", "ingest", write_json(env.tmp / "card.json", _card("", env.tmp)), project=p1)
    assert r["reading_depth"] == "deep"
    ok("project", "init", "--name", "tfbind", project=p1)
    ok("experiment", "record", "--name", "p1 private run", "--outcome", "positive", "--metrics", "{}", project=p1)

    # ---- project 2: different problem, same mechanism family
    ok("project", "init", "--name", "drug-target-unseen", project=p2)
    ms = ok("kg", "search", "meta-learning-conditioning", "--mode", "mechanism", project=p2)
    meth = [m for m in ms["methods"] if m["method"] == "method:fixture-plm-film-tf-binding-model"]
    assert meth and meth[0]["papers"]["paper:arxiv:9912.00001"] == "deep"
    assert "computational-biology" in ms["domains"]
    sem = ok("kg", "search", "conditioning on a descriptor of unseen entities", "--mode", "semantic", project=p2)
    assert sem["hits"]
    chunks = ok("kg", "search", "FiLM conditioning", "--mode", "chunks", project=p2)
    assert any(c["cite"].startswith("paper:arxiv:9912.00001#") for c in chunks)

    again = ok("paper", "fetch", "arxiv:9912.00001", project=p2)
    assert again["from_cache"] is True and again["previously_read_sections"]     # no redundant parsing

    show = ok("kg", "show", "paper:arxiv:9912.00001", project=p2)
    assert show["reading_ledger"]
    # privacy: project-1 local experiment is invisible from project 2
    code, miss = run("kg", "show", "experiment:p1-private-run", project=p2)
    assert "not found" in miss.get("error", "")

    # counterexample recorded in project 2 against a project-1-derived global claim
    art = env.tmp / "dti.csv"
    art.write_text("x,y\n1,2\n", encoding="utf-8")
    ok("experiment", "record", "--name", "dti descriptor fails", "--outcome", "mixed", "--metrics", "{}",
       "--artifact", art, project=p2)
    ok("kg", "link", "experiment:dti-descriptor-fails", "CONTRADICTS", "claim:paper-arxiv-9912-00001-innov-0",
       "--status", "experiment_observed", "--source-type", "local_experiment", "--artifact", art, project=p2)
    con = ok("kg", "contradictions", project=p2)
    assert any(c["dst"] == "claim:paper-arxiv-9912-00001-innov-0" for c in con)

    # method-driven transfer: project-1 method vs open problems registered by any project
    ok("project", "problem", write_json(env.tmp / "prob.json", dict(PROBLEM, problem_structures=[
        "unseen-entity-interaction"], mechanisms=["graphical-models"], data_structure=["sequence", "entity descriptor"])),
       project=p2)
    scan = ok("transfer", "scan", "--method", "method:fixture-plm-film-tf-binding-model", "--min-structural", "0",
              project=p1)
    assert any(c["project"] == "drug-target-unseen" for c in scan["open_problems"])
    rec = ok("transfer", "record", "method:fixture-plm-film-tf-binding-model", project=p2)
    lin = ok("graph", "lineage", rec["transfer_id"], project=p2)
    srcs = {e["src"] for e in lin["derived_from"]}
    assert "paper:arxiv:9912.00001" in srcs and "method:fixture-plm-film-tf-binding-model" in srcs
    cov = ok("graph", "coverage", project=p2)
    assert cov["reading_depth"].get("deep", 0) >= 1


def test_refresh_incremental(env):
    w = ok("refresh", "add", "unseen transcription factor binding prediction", "--structure",
           "unseen-entity-interaction")
    first = ok("refresh", "run", w["id"])[0]
    assert first["checkpoint_advanced"] and first["new_papers"]
    known_before = {p["id"] for p in first["new_papers"]}
    # later state of the (synthetic) literature
    fixture_builder.build(env.fx, variant="refresh")
    second = ok("refresh", "run", w["id"], "--since", "2026-05-01")[0]
    new_ids = {p["id"] for p in second["new_papers"]}
    assert "paper:doi:10.5555/cdri.fx.007" in new_ids and not (new_ids & known_before)
    assert any(s["id"] == "paper:doi:10.5555/cdri.fx.006" for s in second["status_changes"])
    node = ok("kg", "show", "paper:doi:10.5555/cdri.fx.006")
    assert node["node"]["props"]["pub_status"] == "published" and node["node"]["props"]["status_history"]
    # everything failing: checkpoint is not advanced and failures are listed
    (env.fx / "routes.json").write_text(json.dumps([{"match": ".", "status": 429}]), encoding="utf-8")
    lst_before = ok("refresh", "list")[0]["last_checked"]
    third = ok("refresh", "run", w["id"])[0]
    assert not third["checkpoint_advanced"] and third["failures"]
    assert ok("refresh", "list")[0]["last_checked"] == lst_before


def test_sessions_resume(env):
    s = ok("session", "start", "landscape", "TF binding unseen TFs", "--intensity", "deep")
    ok("session", "note", "ran plan; S2 rate limited", "--kind", "search")
    ok("session", "todo", "read Methods of fx.001")
    ok("session", "state", "run_id", "caseA")
    b = ok("session", "resume")
    assert b["id"] == s["id"] and b["open_todo"] == ["read Methods of fx.001"] and b["state"]["run_id"] == "caseA"
    ok("session", "todo", "read Methods of fx.001", "--done")
    ok("session", "close", "--summary", "done")
    code, err = run("session", "resume")
    assert code == 2
