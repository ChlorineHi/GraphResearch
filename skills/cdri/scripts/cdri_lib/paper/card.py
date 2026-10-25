"""Paper Card: method-level record (A-F) and optional research-story understanding (G).

Mechanical integrity rules enforced here:
- method-level details (B/C/D) sourced from the abstract or introduction are downgraded to unverified;
- paper evidence must cite a location that is in the reading ledger (checked by the KG on write);
- limitations are kept in three separate categories with different epistemic status;
- use of a standard component is not accepted as an innovation without an explicit novelty statement;
- code links can only be 'consistent'/'discrepancy' with a pinned commit and a file path.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .. import config
from ..ids import entity_id, parse_identifier, slug
from ..kg.store import KnowledgeBase
from ..insight.story import ARC
from ..transfer import ontology
from ..transfer.signature import normalize as normalize_signature, signature_id

DEPTHS = ("metadata", "abstract", "fulltext", "deep")
STANDARD_COMPONENTS = re.compile(r"\b(transformer|attention|gnn|graph neural network|gan|diffusion|contrastive|"
                                 r"cnn|convolution|lstm|mlp|resnet|u-?net|vae|autoencoder|dropout|layer ?norm)\b", re.I)
INTRO_LOC = re.compile(r"abstract|introduction|^1\.?\s|summary|highlights", re.I)
METHOD_SECTIONS = ("B_formulation", "C_innovation", "D_implementation")


class CardError(ValueError):
    pass


def _src_to_prov(src: Optional[dict], paper_id: str, depth: str) -> Tuple[Optional[dict], Optional[str]]:
    """Map a card item's source to (provenance, requested_status)."""
    if not src:
        return None, None
    st = src.get("type", "agent")
    prov = {"source_type": st, "source_ref": src.get("ref") or paper_id, "location": src.get("location"),
            "quote": src.get("quote"), "commit": src.get("commit"), "extractor": "agent", "note": src.get("note")}
    requested = {"paper_fulltext": "author_claim", "paper_supplement": "author_claim",
                 "paper_abstract": "author_claim", "code": "code_verified", "agent": "agent_inference",
                 "user": "user_reported"}.get(st)
    return prov, requested


def _items(section: Any) -> List[Tuple[str, dict]]:
    """Flatten a card section into (path, item) pairs for every dict carrying 'text'/'statement'."""
    out: List[Tuple[str, dict]] = []

    def walk(v: Any, path: str) -> None:
        if isinstance(v, dict):
            if "text" in v or "statement" in v or "latex" in v:
                out.append((path, v))
            for k, x in v.items():
                if k != "source" and isinstance(x, (dict, list)):
                    walk(x, f"{path}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
    walk(section, "")
    return out


def _validate_research_story(story: Any, pid: str, depth: str, kb: KnowledgeBase) -> dict:
    """Narrative interpretations remain inferences; unread/incomplete analyses stay unverified."""
    errors, warnings, gaps, locations = [], [], [], []
    if not isinstance(story, dict):
        return {"errors": ["G_research_story must be an object"], "warnings": [], "gaps": [],
                "status": "unverified", "evidence_locations": []}
    for field in ("summary", "selection_reason", "beyond_sota", "counterfactual_without_sota"):
        if not isinstance(story.get(field), str) or not story[field].strip():
            gaps.append(f"G_research_story.{field}")
    arc = story.get("arc", {})
    if not isinstance(arc, dict):
        errors.append("G_research_story.arc must be an object")
        arc = {}
    for step in ARC:
        item = arc.get(step)
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            gaps.append(f"G_research_story.arc.{step}")
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            gaps.append(f"G_research_story.arc.{step}.evidence")
            continue
        for source in evidence:
            location = source.get("location") if isinstance(source, dict) else None
            if not isinstance(location, str) or not location.strip() or not kb.g.ledger_has(pid, location):
                gaps.append(f"G_research_story.arc.{step}.unread_or_missing_location")
            elif location not in locations:
                locations.append(location)
    for field in ("comparison_scope", "contribution_types", "alternative_explanations", "transferable_lessons"):
        if not isinstance(story.get(field), list) or not story[field]:
            gaps.append(f"G_research_story.{field}")
    if depth not in ("fulltext", "deep"):
        gaps.append("G_research_story.fulltext_reading")
    if gaps:
        warnings.append("G_research_story is incomplete or cites unread evidence; stored as unverified. "
                        "Narrative analysis does not establish novelty or reasons for publication.")
    return {"errors": errors, "warnings": warnings, "gaps": gaps,
            "status": "unverified" if errors or gaps else "agent_inference", "evidence_locations": locations}


def validate(card: Dict[str, Any], kb: KnowledgeBase) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    gaps: List[str] = []
    if not card.get("paper_id"):
        raise CardError("paper_id is required")
    pid = parse_identifier(card["paper_id"]).canonical
    card["paper_id"] = pid
    depth = card.get("reading_depth", "abstract")
    if depth not in DEPTHS:
        errors.append(f"reading_depth must be one of {DEPTHS}")
    ledger = kb.g.ledger(pid)
    read_kinds = set()
    if ledger:
        try:
            from .fulltext import load
            meta = load(pid)
            titles = {r["section"] for r in ledger}
            full = "__FULL__" in titles
            read_kinds = {s["kind"] for s in meta["sections"] if full or s["title"] in titles}
        except FileNotFoundError:
            pass
    if depth in ("fulltext", "deep") and not ledger:
        warnings.append(f"reading_depth={depth} but no reading-ledger entry for {pid}: downgraded to 'abstract'. "
                        "Use `cdri paper section` or `cdri paper confirm` first.")
        depth = "abstract"
    if depth == "deep" and "methods" not in read_kinds:
        warnings.append("reading_depth=deep but no Methods-kind section is in the ledger: downgraded to 'fulltext'")
        depth = "fulltext"
    card["reading_depth"] = depth
    for sec in ("A_question", "B_formulation", "C_innovation", "D_implementation", "E_evidence", "F_signature"):
        if not card.get(sec):
            gaps.append(sec)
    for sec in METHOD_SECTIONS:
        for path, it in _items(card.get(sec)):
            src = it.get("source") or {}
            loc = src.get("location") or ""
            if src.get("type") == "paper_abstract" or (src.get("type", "").startswith("paper") and INTRO_LOC.search(loc)):
                it["_forced_status"] = "unverified"
                warnings.append(f"{sec}{path}: method detail sourced from abstract/introduction ({loc or 'abstract'}) "
                                "-> unverified. Cite Methods/Supplement/code.")
            if not src:
                it["_forced_status"] = "unverified"
                warnings.append(f"{sec}{path}: no source -> unverified")
    for i, inn in enumerate(card.get("C_innovation") or []):
        st = inn.get("statement", "")
        if (inn.get("standard_component") or STANDARD_COMPONENTS.search(st)) and not inn.get("novel_vs_prior"):
            warnings.append(f"C_innovation[{i}]: uses a standard component ({st[:60]!r}) without 'novel_vs_prior'; "
                            "using an existing architecture is not by itself an innovation")
            inn["_forced_status"] = "unverified"
        if not inn.get("inductive_bias"):
            gaps.append(f"C_innovation[{i}].inductive_bias")
    impl = card.get("D_implementation") or {}
    repo = impl.get("repo") or {}
    for i, cl in enumerate(impl.get("code_links") or []):
        if cl.get("status") in ("consistent", "discrepancy") and not (repo.get("commit") and cl.get("path")):
            warnings.append(f"code_links[{i}]: '{cl.get('status')}' requires repo.commit and path -> unverified")
            cl["status"] = "unverified"
    if not repo.get("url"):
        gaps.append("D_implementation.repo (official code not located; implementation unverified)")
    lim = (card.get("E_evidence") or {}).get("limitations") or {}
    if lim and not isinstance(lim, dict):
        errors.append("E_evidence.limitations must be an object with author_acknowledged / "
                      "inferred_from_results / agent_proposed")
    for i, it in enumerate(lim.get("inferred_from_results") or [] if isinstance(lim, dict) else []):
        if not it.get("basis"):
            warnings.append(f"limitations.inferred_from_results[{i}] has no 'basis' (which result supports it)")
    for i, it in enumerate(lim.get("author_acknowledged") or [] if isinstance(lim, dict) else []):
        if not str((it.get("source") or {}).get("type", "")).startswith("paper"):
            warnings.append(f"limitations.author_acknowledged[{i}] must cite the paper; moved to agent_proposed")
            lim.setdefault("agent_proposed", []).append(it)
            it["_moved"] = True
    if isinstance(lim, dict):
        lim["author_acknowledged"] = [x for x in lim.get("author_acknowledged") or [] if not x.get("_moved")]
    sig_norm, sig_w = ({}, [])
    if card.get("F_signature"):
        sig_norm, sig_w = normalize_signature(card["F_signature"], kb)
        warnings += sig_w
    research_story = None
    if "G_research_story" in card:
        research_story = _validate_research_story(card["G_research_story"], pid, depth, kb)
        errors += research_story["errors"]
        warnings += research_story["warnings"]
        gaps += research_story["gaps"]
    return {"paper_id": pid, "reading_depth": depth, "errors": errors, "warnings": warnings, "gaps": gaps,
            "signature": sig_norm, "research_story": research_story}


def _status_for(it: dict, depth: str, paper_id: str) -> Tuple[Optional[dict], Optional[str]]:
    prov, req = _src_to_prov(it.get("source"), paper_id, depth)
    if it.get("_forced_status"):
        req = it["_forced_status"]
    return prov, req


def ingest(card: Dict[str, Any], kb: KnowledgeBase, save: bool = True) -> Dict[str, Any]:
    report = validate(card, kb)
    if report["errors"]:
        return {"ingested": False, **report}
    pid = report["paper_id"]
    depth = report["reading_depth"]
    w: List[str] = []
    stats: Dict[str, int] = {}

    def node(nid, ntype, label, item=None, props=None, status=None):
        prov, req = _status_for(item or {}, depth, pid) if item else (None, status)
        r = kb.upsert_node(nid, ntype, label, props=props or {}, status=req if item else status, prov=prov)
        w.extend(r["warnings"])
        stats[ntype] = stats.get(ntype, 0) + 1
        return nid

    def edge(src, etype, dst, item=None, props=None, status=None):
        prov, req = _status_for(item or {}, depth, pid) if item else (None, status)
        r = kb.add_edge(src, etype, dst, props=props, status=req if item else status, prov=prov)
        w.extend(r["warnings"])
        return r

    paper = kb.get_node(pid)
    if not paper:
        node(pid, "Paper", card.get("title") or pid, props={"note": "created from card; metadata not yet verified"},
             status="unverified")
    kb.upsert_node(pid, "Paper", (paper or {}).get("label") or card.get("title") or pid,
                   props={"reading_depth": depth, "card": True}, overwrite=True)
    method = card.get("method") or {}
    mname = method.get("name") or (card.get("title") or pid)
    mid = entity_id("method", mname)
    node(mid, "Method", mname, props={"aliases": method.get("aliases", []), "paper": pid})
    for a in method.get("aliases", []):
        kb.upsert_node(mid, "Method", mname, aliases=[a])
    edge(pid, "USES_METHOD", mid, props={"introduced_here": method.get("introduced_here", True)},
         item={"source": {"type": "paper_fulltext" if depth in ("fulltext", "deep") else "paper_abstract",
                          "location": method.get("location") or ("Methods" if depth in ("fulltext", "deep")
                                                                 else "abstract")}})
    A = card.get("A_question") or {}
    if A.get("problem"):
        prob = A["problem"]
        prid = entity_id("problem", prob.get("id") or prob["text"][:70])
        node(prid, "ResearchProblem", prob["text"][:200], item=prob,
             props={"importance": (A.get("importance") or {}).get("text"),
                    "prior_limitations": [x.get("text") for x in A.get("prior_limitations") or []],
                    "what_changed": A.get("what_changed")})
        edge(pid, "SOLVES", prid, item=prob)
        edge(mid, "SOLVES", prid, item=prob)
    B = card.get("B_formulation") or {}
    for a in B.get("assumptions") or []:
        aid = "assumption:" + ontology.assumption_id(a.get("id") or a["text"])
        node(aid, "Assumption", a["text"][:200], props={"stated_by_paper": a.get("source", {}).get("type") != "agent"},
             status="vocabulary")
        edge(mid, "DEPENDS_ON_ASSUMPTION", aid, item=a)
    for op in B.get("operators") or []:
        oid = entity_id("operator", op.get("name") or op["text"][:60])
        node(oid, "MathematicalOperator", op.get("name") or op["text"][:80], status="vocabulary",
             props={"description": op.get("text")})
        edge(mid, "USES_OPERATOR", oid, item=op)
    eqs = B.get("equations") or []
    if eqs or B:
        kb.upsert_node(mid, "Method", mname, props={"formulation": {
            k: (v.get("text") if isinstance(v, dict) else v) for k, v in B.items()
            if k in ("inputs", "outputs", "supervision", "objective", "variables", "constraints")},
            "equations": [{"label": e.get("label"), "latex": e.get("latex"), "role": e.get("role"),
                           "depends_on": e.get("depends_on"), "location": (e.get("source") or {}).get("location")}
                          for e in eqs]})
    for i, inn in enumerate(card.get("C_innovation") or []):
        cid = f"claim:{slug(pid, 50)}-innov-{i}"
        node(cid, "ScientificClaim", inn.get("statement", "")[:200], item=inn,
             props={"kind": inn.get("kind"), "novel_vs_prior": inn.get("novel_vs_prior"),
                    "prior_work": inn.get("prior_work"), "why_fits": inn.get("why_fits"),
                    "scope": inn.get("scope"), "claim_type": "innovation"})
        edge(pid, "MAKES_CLAIM", cid, item=inn)
        if inn.get("inductive_bias"):
            bid = entity_id("bias", inn["inductive_bias"][:70])
            node(bid, "InductiveBias", inn["inductive_bias"][:200], status="vocabulary")
            edge(mid, "HAS_INDUCTIVE_BIAS", bid, item=inn)
        for pw in inn.get("prior_work") or []:
            ppid = parse_identifier(pw).canonical
            if kb.get_node(ppid):
                edge(mid, "EXTENDS", ppid, item=inn)
    D = card.get("D_implementation") or {}
    repo = D.get("repo") or {}
    repo_id = None
    if repo.get("url"):
        from ..ids import github_repo
        gh = github_repo(repo["url"])
        repo_id = f"repo:github:{gh[0]}/{gh[1]}" if gh else entity_id("repo", repo["url"])
        node(repo_id, "GitHubRepository", repo["url"], props={"commit": repo.get("commit"),
             "official": repo.get("official", True)}, status="vocabulary")
        edge(pid, "IMPLEMENTED_BY", repo_id, item={"source": {"type": "paper_fulltext" if repo.get("location") else "agent",
                                                              "location": repo.get("location")}})
    impl_props = {it.get("aspect", f"item{i}"): it.get("text") for i, it in enumerate(D.get("items") or [])}
    if impl_props:
        kb.upsert_node(mid, "Method", mname, props={"implementation": impl_props})
    for i, cl in enumerate(D.get("code_links") or []):
        if not cl.get("path"):
            continue
        cmid = f"code:{(repo_id or 'repo:local').split(':', 1)[1]}@{(repo.get('commit') or 'unpinned')[:12]}:" \
               f"{cl['path']}::{cl.get('symbol') or ''}"
        node(cmid, "CodeModule", f"{cl['path']}::{cl.get('symbol') or ''}",
             props={"lines": cl.get("lines"), "permalink": cl.get("permalink"), "repo": repo_id}, status="vocabulary")
        if repo_id:
            edge(repo_id, "HAS_CODE_MODULE", cmid, status="vocabulary")
        st = cl.get("status", "unverified")
        item = {"source": {"type": "code", "location": f"{cl['path']}:{cl.get('lines') or ''}",
                           "commit": repo.get("commit"), "quote": cl.get("note")}} if st != "unverified" else \
            {"source": {"type": "agent", "note": "formula-code correspondence not verified"}}
        if st == "unverified":
            item["_forced_status"] = "unverified"
        edge(mid, "IMPLEMENTED_BY", cmid, item=item,
             props={"formula": cl.get("formula"), "match": st, "note": cl.get("note")})
    E = card.get("E_evidence") or {}
    for i, ex in enumerate(E.get("experiments") or []):
        rid = f"result:{slug(pid, 50)}-{i}"
        node(rid, "ExperimentalResult", (ex.get("text") or ex.get("hypothesis_tested") or f"experiment {i}")[:200],
             item=ex, props={k: ex.get(k) for k in ("hypothesis_tested", "result", "is_ablation", "is_ood",
                                                     "protocol", "negative")})
        edge(pid, "REPORTS_RESULT", rid, item=ex)
        for ds in ex.get("datasets") or []:
            did = entity_id("dataset", ds)
            node(did, "Dataset", ds, status="vocabulary")
            edge(rid, "EVALUATED_ON", did, item=ex)
        for mt in ex.get("metrics") or []:
            mtid = entity_id("metric", mt)
            node(mtid, "Metric", mt, status="vocabulary")
            edge(rid, "MEASURED_BY", mtid, item=ex)
    for i, nr in enumerate(E.get("negative_results") or []):
        rid = f"result:{slug(pid, 50)}-neg-{i}"
        node(rid, "ExperimentalResult", nr.get("text", "")[:200], item=nr, props={"negative": True})
        edge(pid, "REPORTS_RESULT", rid, item=nr)
    lim = E.get("limitations") or {}
    cat_status = {"author_acknowledged": None, "inferred_from_results": "agent_inference",
                  "agent_proposed": "hypothesis"}
    for cat, forced in cat_status.items():
        for i, it in enumerate(lim.get(cat) or []):
            lid = f"limitation:{slug(pid, 50)}-{cat}-{i}"
            item = dict(it)
            if forced:
                item["source"] = {"type": "agent", "note": f"{cat}; basis: {it.get('basis') or it.get('rationale')}"}
                item["_forced_status"] = forced
            node(lid, "Limitation", it.get("text", "")[:200], item=item,
                 props={"category": cat, "basis": it.get("basis"), "rationale": it.get("rationale")})
            edge(mid, "HAS_LIMITATION", lid, item=item, props={"category": cat})
    sig = report.get("signature")
    if sig:
        w += ingest_signature(kb, mid, sig, card.get("F_signature", {}).get("source"), pid)
    story_id = None
    if report["research_story"] is not None:
        story = card["G_research_story"]
        story_id = f"claim:{slug(pid, 50)}-research-story"
        evidence = report["research_story"]
        # Store the complete analysis in a field included by both semantic and keyword retrieval.
        prov = {"source_type": "agent", "source_ref": pid,
                "location": "; ".join(evidence["evidence_locations"]), "extractor": "agent",
                "note": "research-story interpretation; not author testimony or acceptance evidence"}
        r = kb.upsert_node(story_id, "ScientificClaim", f"Research story: {card.get('title') or pid}"[:200],
                           props={"claim_type": "research_story", "paper": pid, "method": mid,
                                  "research_story": story, "evidence_gaps": evidence["gaps"],
                                  "rationale": json.dumps(story, ensure_ascii=False)},
                           status=evidence["status"], prov=prov, overwrite=True)
        w += r["warnings"]
        stats["ScientificClaim"] = stats.get("ScientificClaim", 0) + 1
        for src in (pid, mid):
            r = kb.add_edge(src, "LINKS_TO", story_id, status=evidence["status"], prov=prov,
                            props={"role": "research_story_interpretation"})
            w += r["warnings"]
    if save:
        cdir = config.home() / "cards"
        cdir.mkdir(exist_ok=True)
        (cdir / f"{slug(pid, 90)}.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ingested": True, "method_id": mid, "research_story_id": story_id,
            **report, "write_warnings": sorted(set(w)), "nodes_written": stats}


def ingest_signature(kb: KnowledgeBase, method_id: str, sig: Dict[str, Any], source: Optional[dict],
                     paper_id: Optional[str]) -> List[str]:
    """Store a normalized signature and its mechanism / structure / assumption / domain edges."""
    w: List[str] = []
    sid = signature_id(method_id)
    prov = {"source_type": "agent", "source_ref": paper_id or method_id, "location": (source or {}).get("location"),
            "extractor": "agent", "note": "method signature is an agent abstraction of the paper"}
    r = kb.upsert_node(sid, "MethodSignature", f"Signature of {method_id.split(':', 1)[1]}",
                       props={k: v for k, v in sig.items() if not k.startswith("_")}, status="agent_inference",
                       prov=prov, overwrite=True)
    w += r["warnings"]
    kb.add_edge(method_id, "HAS_SIGNATURE", sid, status="agent_inference", prov=prov)
    disc = {d["id"]: d["label"] for d in sig.get("_discovered_mechanisms", [])}
    for m in sig["mechanisms"]:
        nid = ontology.ensure_mechanism_node(kb, m, disc.get(m), discovered=m in disc, prov=prov if m in disc else None)
        kb.add_edge(method_id, "USES_MECHANISM", nid, status="agent_inference", prov=prov)
    for s in sig["problem_structures"]:
        seed = ontology.seed_structures().get(s)
        snid = f"structure:{s}"
        kb.upsert_node(snid, "ProblemStructure", seed["label"] if seed else s, status="vocabulary")
        kb.add_edge(method_id, "INSTANCE_OF_STRUCTURE", snid, status="agent_inference", prov=prov)
    for a in sig["required_assumptions"]:
        aid = f"assumption:{a}"
        kb.upsert_node(aid, "Assumption", a.replace("-", " "), status="vocabulary")
        kb.add_edge(method_id, "DEPENDS_ON_ASSUMPTION", aid, status="agent_inference", prov=prov)
    if sig.get("source_domain"):
        did = f"domain:{slug(sig['source_domain'])}"
        kb.upsert_node(did, "Domain", sig["source_domain"], status="vocabulary")
        kb.add_edge(method_id, "IN_DOMAIN", did, status="agent_inference", prov=prov)
    return w


def template() -> Dict[str, Any]:
    return json.loads((config.ASSETS / "templates" / "paper_card.json").read_text(encoding="utf-8"))
