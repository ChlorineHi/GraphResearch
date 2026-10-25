"""Source failures stay visible without repeating blocked requests or false healthy pings."""

import json

import pytest

from conftest import ok
from cdri_lib import http
from cdri_lib.report.render import landscape
from cdri_lib.retrieval import planner, sources
from cdri_lib.retrieval.records import Record
from cdri_lib.retrieval.run import execute


def plan_for(source):
    plan = planner.plan("[SYNTHETIC FIXTURE] research", intensity="quick")
    plan["queries"] = [{"qid": f"q{i}", "lane": "in_domain", "text": f"synthetic question {i}",
                        "sources": [source, "crossref"], "rationale": "synthetic coverage test"}
                       for i in range(3)]
    return plan


@pytest.mark.parametrize("source,status", [("semantic_scholar", "rate_limited"), ("dblp", "blocked")])
def test_source_pauses_only_for_current_run_and_other_sources_continue(env, monkeypatch, source, status):
    calls = {source: 0, "crossref": 0}
    def unavailable(*args, **kwargs):
        calls[source] += 1
        raise http.HTTPFailure(status, "synthetic unavailable source")
    def available(*args, **kwargs):
        calls["crossref"] += 1
        return [Record(title="[SYNTHETIC FIXTURE] available", source_db="crossref",
                       doi="10.5555/cdri.fx.resilience")]
    monkeypatch.setitem(sources.SEARCHERS, source, unavailable)
    monkeypatch.setitem(sources.SEARCHERS, "crossref", available)
    plan = plan_for(source)
    result = execute(plan, run_id="resilience", ingest=False)
    assert calls == {source: 1, "crossref": 3}
    assert result["status"] == "partial" and result["unique_records"] == 1
    assert result["available_sources"] == ["crossref"]
    assert result["by_db"][source] == {status: 1, "skipped_source": 2}
    assert result["attempted_calls"] == 4 and result["skipped_calls"] == 2
    assert len(result["failures"]) == 3 and result["source_recovery"][0]["db"] == source
    assert sum(f["attempted"] for f in result["failures"]) == 1
    skipped = [f for f in result["failures"] if not f["attempted"]]
    assert all(f["cause_status"] == status for f in skipped)
    logs = [json.loads(line) for line in (env.proj / ".cdri/runs/resilience/log.jsonl").read_text().splitlines()]
    assert len(logs) == 6 and sum(row["attempted"] for row in logs) == 4
    assert "部分来源失败" in landscape("resilience")
    # A later run may probe again. There is no permanent disablement or hidden process-wide state.
    execute(plan, run_id="retry", ingest=False)
    assert calls[source] == 2


def test_filtered_run_records_scope_without_claiming_excluded_sources_succeeded(env, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("explicitly excluded source was called")
    monkeypatch.setitem(sources.SEARCHERS, "semantic_scholar", forbidden)
    monkeypatch.setitem(sources.SEARCHERS, "crossref", lambda *a, **kw: [])
    result = execute(plan_for("semantic_scholar"), only_sources=["crossref"], run_id="filtered", ingest=False)
    assert result["status"] == "complete" and not result["failures"]
    assert result["unique_records"] == 0  # a successful empty search is not an outage
    assert result["excluded_sources"] == ["semantic_scholar"]
    assert result["source_filter"] == ["crossref"]
    assert set(result["by_db"]) == {"crossref"}
    assert "未查询不等于成功" in landscape("filtered")


def test_all_failed_sources_are_not_reported_as_success(env, monkeypatch):
    def unavailable(*args, **kwargs):
        raise http.HTTPFailure("rate_limited", "synthetic 429", 429)
    monkeypatch.setitem(sources.SEARCHERS, "semantic_scholar", unavailable)
    result = execute(plan_for("semantic_scholar"), only_sources=["semantic_scholar"],
                     run_id="failed", ingest=False)
    assert result["status"] == "failed" and result["available_sources"] == []
    assert result["attempted_calls"] == 1 and result["skipped_calls"] == 2
    assert "所有已尝试来源均失败" in landscape("failed")


def test_ping_validates_payload_and_sends_semantic_scholar_key(env, monkeypatch):
    seen = {}
    def response(url, **kwargs):
        seen[url] = kwargs
        if "dblp.org" in url:
            body = b"<html><title>Making sure you're not a bot!</title></html>"
        elif "export.arxiv.org" in url:
            body = b'<feed xmlns="http://www.w3.org/2005/Atom" />'
        else:
            body = b'{"results": []}'
        return http.Response(url=url, code=202 if "dblp.org" in url else 200, body=body)
    monkeypatch.setattr(http, "get", response)
    monkeypatch.setenv("S2_API_KEY", "synthetic-test-key")
    result = ok("config", "check", "--ping")
    assert result["ping"]["dblp"].startswith("blocked:")
    assert result["ping"]["arxiv"] == "ok"
    s2 = next(options for url, options in seen.items() if "semanticscholar" in url)
    assert s2["headers"] == {"x-api-key": "synthetic-test-key"}
    assert "synthetic-test-key" not in json.dumps(result)


def test_ping_invalid_xml_is_an_error_not_a_crash(env, monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, **kw: http.Response(url, 200, b"not xml"))
    monkeypatch.setattr(http, "get_json", lambda *a, **kw: {})
    assert ok("config", "check", "--ping")["ping"]["arxiv"].startswith("error:")
