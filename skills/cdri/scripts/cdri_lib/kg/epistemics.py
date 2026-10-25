"""Epistemic status rules. The status of a knowledge item is bounded by the *type* of evidence behind it,
not by what the writer requests. Agent-sourced knowledge can never reach a verified status."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

STATUSES = ["unverified", "hypothesis", "agent_inference", "user_reported", "author_claim",
            "verified", "code_verified", "experiment_observed"]
RANK = {"unverified": 0, "hypothesis": 1, "agent_inference": 2, "user_reported": 3, "author_claim": 4,
        "verified": 5, "code_verified": 5, "experiment_observed": 5}
LABEL = {
    "verified": "Verified Fact", "code_verified": "Verified Fact (code)",
    "experiment_observed": "Verified Fact (local experiment)", "author_claim": "Author Claim",
    "user_reported": "User Reported", "agent_inference": "Agent Interpretation", "hypothesis": "Hypothesis",
    "unverified": "Unsupported / Unverified",
}
SOURCE_TYPES = ["paper_fulltext", "paper_supplement", "paper_abstract", "metadata_api", "code",
                "local_experiment", "user", "agent"]
ALLOWED: Dict[str, List[str]] = {
    "agent": ["agent_inference", "hypothesis", "unverified"],
    "user": ["user_reported", "hypothesis", "unverified"],
    "paper_abstract": ["author_claim", "unverified"],
    "paper_fulltext": ["author_claim", "unverified"],
    "paper_supplement": ["author_claim", "unverified"],
    "metadata_api": ["verified", "author_claim", "unverified"],
    "code": ["code_verified", "agent_inference", "unverified"],
    "local_experiment": ["experiment_observed", "user_reported", "unverified"],
}
DEFAULT_FOR_SOURCE = {"agent": "agent_inference", "user": "user_reported", "paper_abstract": "author_claim",
                      "paper_fulltext": "author_claim", "paper_supplement": "author_claim",
                      "metadata_api": "verified", "code": "code_verified", "local_experiment": "experiment_observed"}


def label(status: str) -> str:
    return LABEL.get(status, status)


def grant(requested: Optional[str], prov: dict,
          ledger_has: Optional[Callable[[str, str], bool]] = None) -> Tuple[str, List[str]]:
    """Return (granted_status, warnings) for one provenance record."""
    warnings: List[str] = []
    st = prov.get("source_type")
    if st not in ALLOWED:
        return "unverified", [f"unknown source_type {st!r}; stored as unverified"]
    requested = requested or DEFAULT_FOR_SOURCE[st]
    if requested not in RANK:
        warnings.append(f"unknown status {requested!r}")
        requested = DEFAULT_FOR_SOURCE[st]
    allowed = ALLOWED[st]
    if requested not in allowed:
        below = [s for s in allowed if RANK[s] <= RANK[requested]]
        new = max(below, key=lambda s: RANK[s]) if below else "unverified"
        warnings.append(f"status {requested} not attainable from source_type={st}; capped at {new}")
        requested = new
    loc = prov.get("location") or ""
    if st in ("paper_fulltext", "paper_supplement") and requested == "author_claim":
        if not loc:
            warnings.append("paper evidence without location (section/page); downgraded to unverified")
            return "unverified", warnings
        ref = prov.get("source_ref") or ""
        if ledger_has is not None and not ledger_has(ref, loc):
            warnings.append(f"section {loc!r} of {ref} is not in the reading ledger; downgraded to unverified")
            return "unverified", warnings
    if st == "code" and requested == "code_verified":
        if not (prov.get("commit") and loc):
            warnings.append("code evidence needs a pinned commit and file location; downgraded to unverified")
            return "unverified", warnings
    if st == "local_experiment" and requested == "experiment_observed":
        if not prov.get("artifact_exists"):
            warnings.append("no existing artifact for local experiment; downgraded to user_reported")
            return "user_reported", warnings
    return requested, warnings


def best(statuses: List[str]) -> str:
    return max(statuses, key=lambda s: RANK.get(s, 0)) if statuses else "unverified"
