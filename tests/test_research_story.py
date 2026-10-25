"""Synthetic paper-story understanding: persistence, retrieval and evidence boundaries."""

from copy import deepcopy

import pytest

from cdri_lib.insight.story import ARC
from cdri_lib.kg import semantic
from cdri_lib.kg.store import KnowledgeBase
from cdri_lib.paper.card import ingest, validate
from cdri_lib.report.render import paper


PID = "paper:doi:10.5555/cdri.fx.story"


def story_card():
    return {
        "paper_id": PID, "title": "[SYNTHETIC FIXTURE] An informative failure",
        "reading_depth": "fulltext", "method": {"name": "Fixture story model"},
        "G_research_story": {
            "summary": "A controlled failure challenges an assumed objective.",
            "selection_reason": "Explains a failure rather than increasing a leaderboard score.",
            "comparison_scope": ["single-paper analysis; novelty not compared"],
            "contribution_types": ["failure_explanation"],
            "arc": {step: {"text": f"Synthetic interpretation of {step}",
                           "evidence": [{"location": "3 Results", "role": "synthetic evidence"}]}
                    for step in ARC},
            "beyond_sota": "Identifies an evaluation blind spot.",
            "counterfactual_without_sota": "The controlled counterexample remains informative.",
            "alternative_explanations": ["An untested preprocessing artifact remains possible."],
            "transferable_lessons": [{"lesson": "descriptor degeneracy diagnostic",
                                      "conditions": "matched information at inference",
                                      "misuse_risk": "an analogous failure need not share the cause"}],
            "status": "verified", "source": {"type": "metadata_api"},
        },
    }


def add_ledger(kb):
    kb.g.ledger_add(PID, "3 Results", 100, "synthetic-hash", "cli_read")


def test_story_ingest_retrieve_report_and_reuse_across_projects(env):
    kb = KnowledgeBase()
    add_ledger(kb)
    result = ingest(story_card(), kb)
    sid = result["research_story_id"]
    record = kb.get_node(sid)
    assert result["ingested"] and record["scope"] == "global"
    assert record["status"] == "agent_inference"  # requested verified/source cannot self-certify
    assert {p["source_type"] for p in kb.provenance(sid)} == {"agent"}
    assert record["props"]["research_story"]["counterfactual_without_sota"]
    assert any(hit["id"] == sid for hit in semantic.search(kb, "descriptor degeneracy diagnostic")["hits"])
    assert any(hit["id"] == sid for hit in kb.search_nodes("descriptor degeneracy diagnostic"))
    assert {e["src"] for e in kb.edges(dst=sid, etype="LINKS_TO")} == {PID, result["method_id"]}
    report = paper(PID, kb)
    assert "Research Story" in report and "counterexample remains informative" in report
    assert "3 Results" in report and "实际录用原因未知" in report
    other = KnowledgeBase(project=str(env.tmp / "other-project"))
    assert other.get_node(sid)["props"]["claim_type"] == "research_story"


@pytest.mark.parametrize("missing", ["ledger", "arc_step", "source_location", "null_sources", "counterfactual"])
def test_story_missing_evidence_is_not_certified(env, missing):
    kb = KnowledgeBase()
    card = story_card()
    if missing != "ledger":
        add_ledger(kb)
    if missing == "arc_step":
        card["G_research_story"]["arc"]["critical_evidence"] = None
    elif missing == "source_location":
        card["G_research_story"]["arc"]["critical_evidence"]["evidence"][0]["location"] = "Unread appendix"
    elif missing == "null_sources":
        card["G_research_story"]["arc"]["critical_evidence"]["evidence"] = None
    elif missing == "counterfactual":
        card["G_research_story"].pop("counterfactual_without_sota")
    result = ingest(card, kb, save=False)
    assert result["research_story"]["gaps"]
    assert kb.get_node(result["research_story_id"])["status"] == "unverified"
    assert "未解决缺口" in paper(PID, kb)


def test_legacy_cards_and_malformed_story(env):
    kb = KnowledgeBase()
    legacy = story_card()
    legacy.pop("G_research_story")
    result = ingest(legacy, kb, save=False)
    assert result["ingested"] and result["research_story_id"] is None
    assert not any(gap.startswith("G_research_story") for gap in result["gaps"])
    malformed = deepcopy(legacy)
    malformed["G_research_story"] = ["a narrative without structure"]
    assert validate(malformed, kb)["errors"]
    assert not ingest(malformed, kb, save=False)["ingested"]


def test_new_reading_does_not_auto_promote_an_interpretation(env):
    kb = KnowledgeBase()
    first = ingest(story_card(), kb, save=False)
    add_ledger(kb)
    updated = ingest(story_card(), kb, save=False)
    sid = first["research_story_id"]
    assert updated["research_story"]["status"] == "agent_inference"
    assert kb.get_node(sid)["status"] == "unverified"
    promoted = kb.promote(sid, "agent_inference", {"source_type": "agent", "source_ref": PID,
                                                  "location": "3 Results"})
    assert promoted["promoted"] and promoted["status"] == "agent_inference"
