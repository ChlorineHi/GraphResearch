"""Project profile: goal, frozen decisions, facts about assumptions, and the abstract problem signature.

Only the *abstract* problem signature is mirrored to the Global KB (local machine) so that other projects can
discover method-driven transfer opportunities; project data, code and results stay in the project store."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, Optional

from . import config
from .ids import slug
from .kg.store import KnowledgeBase
from .transfer.signature import normalize


def path(project: Optional[str] = None) -> Path:
    return config.project_dir(project) / "project.json"


def load(project: Optional[str] = None) -> Dict[str, Any]:
    p = path(project)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    root = config.project_dir(project).parent
    return {"name": root.name, "goal": "", "frozen_decisions": [], "facts": {}, "problem_signature": None}


def save(data: Dict[str, Any], project: Optional[str] = None) -> Path:
    p = path(project)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def project_node_id(data: Dict[str, Any]) -> str:
    return f"project:{slug(data['name'])}"


def problem_node_id(data: Dict[str, Any]) -> str:
    return f"problem:project-{slug(data['name'])}"


def init(name: Optional[str], goal: str, project: Optional[str] = None, kb: Optional[KnowledgeBase] = None) -> dict:
    data = load(project)
    if name:
        data["name"] = name
    if goal:
        data["goal"] = goal
    save(data, project)
    kb = kb or KnowledgeBase(project)
    kb.upsert_node(project_node_id(data), "Project", data["name"], props={"goal": data["goal"]},
                   status="user_reported", prov={"source_type": "user", "source_ref": "project.json",
                                                 "extractor": "cli"})
    return data


def freeze(decision: str, reason: str, project: Optional[str] = None) -> dict:
    data = load(project)
    data["frozen_decisions"].append({"decision": decision, "reason": reason,
                                     "t": _dt.datetime.now().isoformat(timespec="seconds")})
    save(data, project)
    return data


def set_fact(key: str, value: Any, note: str = "", project: Optional[str] = None) -> dict:
    data = load(project)
    if isinstance(value, str) and value.lower() in ("true", "yes", "1"):
        value = True
    elif isinstance(value, str) and value.lower() in ("false", "no", "0"):
        value = False
    elif isinstance(value, str) and value.lower() == "unknown":
        value = "unknown"
    data["facts"][slug(key, 70) if not key.startswith("_") and key not in ("data_scale",) else key] = value
    if note:
        data.setdefault("facts", {}).setdefault("_notes", {})[slug(key, 70)] = note
    save(data, project)
    return data


def set_problem(sig: Dict[str, Any], project: Optional[str] = None, kb: Optional[KnowledgeBase] = None,
                share_global: bool = True) -> dict:
    kb = kb or KnowledgeBase(project)
    data = load(project)
    norm, warnings = normalize(sig, kb)
    data["problem_signature"] = {k: v for k, v in norm.items() if not k.startswith("_")}
    save(data, project)
    pid, prob = project_node_id(data), problem_node_id(data)
    init(None, "", project, kb)
    prov = {"source_type": "user", "source_ref": "project.json", "extractor": "cli",
            "note": "abstract problem signature (no data)"}
    target = kb.g if share_global else kb.p
    target.upsert_node(prob, "ResearchProblem", sig.get("original_problem") or data["name"],
                       props={"signature": data["problem_signature"], "open": True, "project": data["name"]},
                       status="user_reported", prov=prov, overwrite=True)
    kb.add_edge(pid, "LINKS_TO", prob, status="user_reported", prov=prov)
    for m in data["problem_signature"].get("mechanisms") or []:
        from .transfer.ontology import ensure_mechanism_node
        kb.add_edge(prob, "USES_MECHANISM", ensure_mechanism_node(kb, m), status="user_reported", prov=prov,
                    props={"role": "current approach"})
    return {"problem_id": prob, "signature": data["problem_signature"], "warnings": warnings}


def open_problems(kb: KnowledgeBase) -> list:
    return [n for n in kb.nodes("ResearchProblem") if n["props"].get("open") and n["props"].get("signature")]
