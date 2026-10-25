"""Commands not exercised by the scenario tests: citation expansion (incl. failure path), code grep, signature
normalization, metric info, provenance / fair-benchmark checklists, DOT / JSON / GraphML export, and a check that
every command referenced in the skill docs exists."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from conftest import git_repo_copy, ok, run, write_json

ROOT = Path(__file__).resolve().parents[1]


def test_cite_expand_both_directions(env):
    r = ok("cite", "expand", "doi:10.5555/cdri.fx.001", "--direction", "both")
    dirs = {x["direction"] for x in r["records"]}
    assert dirs == {"backward", "forward"}
    assert all(l["status"] == "ok" for l in r["log"])
    p = ok("kg", "show", r["paper"])
    assert any(e["type"] == "CITES" for e in p["out"]) and any(e["type"] == "CITES" for e in p["in"])


def test_cite_expand_failure_is_reported_not_crashing(env, tmp_path, monkeypatch):
    (tmp_path / "routes.json").write_text(json.dumps([{"match": "api\\.openalex\\.org", "status": 429}]),
                                          encoding="utf-8")
    monkeypatch.setenv("CDRI_FIXTURES", str(tmp_path))
    r = ok("cite", "expand", "doi:10.5555/cdri.fx.001")
    assert r["records"] == [] and r["log"][0]["status"] == "rate_limited"


def test_code_locate_grep_hyperparameters_and_signature_normalize(env):
    assert ok("code", "locate", "arxiv:9912.00001")["candidates"] == []          # nothing fetched yet: no guessing
    ok("paper", "fetch", "arxiv:9912.00001")
    assert ok("code", "locate", "arxiv:9912.00001")["candidates"] == ["https://github.com/cdri-fixture/tfbind-fixture"]
    repo, sha = git_repo_copy(env.tmp / "repo")
    hits = ok("code", "grep", repo, "backward|lr:")
    files = {h["file"] for h in hits}
    assert "train.py" in files and "config.yaml" in files                        # non-Python files are searched too
    an = ok("code", "analyze", repo, "--full")
    cli_item = next(i for i in an["items"] if "config_cli" in i["roles"])
    assert cli_item["hyperparameters"]["lr"] == 0.001 and cli_item["hyperparameters"]["batch_size"] == 256
    cfg = next(c for c in an["configs"] if c["file"] == "config.yaml")
    assert cfg["hyperparameters"]["dropout"] in (0.1, "0.1")
    sig = write_json(env.tmp / "sig.json", {"source_domain": "Computational Biology", "mechanisms": ["OT", "optimal transport"],
                                            "required_assumptions": ["Meaningful Ground Cost"]})
    n = ok("signature", "normalize", sig)
    text = json.dumps(n)
    assert "optimal-transport" in text and "computational_biology" in text


def test_metric_info_and_checklists(env):
    m = ok("audit", "metric-info", "Spearman's rho")
    assert m and "spearman" in json.dumps(m).lower()
    tpl = ok("audit", "provenance", "--profile", "bio")
    assert "genome_build" in tpl["template"] and "split_strategy_and_unit" in tpl["template"]
    filled = dict(tpl["template"])
    filled["genome_build"] = {"value": "hg38", "evidence": "", "status": "verified"}
    chk = ok("audit", "provenance", "--check", write_json(env.tmp / "prov.json", filled))
    assert "genome_build" in chk["verified_without_evidence"] and not chk["complete"]
    assert any("split" in c for c in ok("audit", "checklist"))


def test_graph_export_formats(env):
    ok("cite", "expand", "doi:10.5555/cdri.fx.001", "--direction", "both")
    dot = run("graph", "export", "--view", "citation", "--format", "dot")[1]
    assert dot.lstrip().startswith("digraph") and "CITES" in dot
    gj = run("graph", "export", "--view", "citation", "--format", "json")[1]
    assert isinstance(gj, dict) and gj.get("nodes") and (gj.get("edges") or gj.get("links"))
    gml = run("graph", "export", "--view", "citation", "--format", "graphml")[1]
    assert "<graphml" in gml and "CITES" in gml
    for view in ("problem-limitation", "evidence"):
        assert run("graph", "export", "--view", view, "--format", "mermaid")[0] == 0


def test_all_documented_commands_exist():
    spec = importlib.util.spec_from_file_location("check_refs", ROOT / "tools" / "check_command_refs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0
