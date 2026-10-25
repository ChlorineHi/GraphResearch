"""Resumable research sessions: an append-only notebook of steps per task, stored in <project>/.cdri/sessions.
A session does not run anything by itself; it lets a later agent invocation pick up where the last one stopped."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config
from .ids import slug


def _dir(project: Optional[str]) -> Path:
    d = config.project_dir(project) / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def start(mode: str, goal: str, project: Optional[str] = None, intensity: str = "standard") -> dict:
    sid = _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slug(mode + "-" + goal, 40)
    s = {"id": sid, "mode": mode, "goal": goal, "intensity": intensity, "started": _now(), "status": "open",
         "steps": [], "state": {}, "todo": []}
    save(s, project)
    return s


def save(s: dict, project: Optional[str] = None) -> None:
    (_dir(project) / f"{s['id']}.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


def load(sid: Optional[str] = None, project: Optional[str] = None) -> dict:
    if sid:
        return json.loads((_dir(project) / f"{sid}.json").read_text(encoding="utf-8"))
    opened = [x for x in list_sessions(project) if x["status"] == "open"]
    if not opened:
        raise FileNotFoundError("no open session")
    return load(opened[-1]["id"], project)


def list_sessions(project: Optional[str] = None) -> List[dict]:
    out = []
    for p in sorted(_dir(project).glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": s["id"], "mode": s["mode"], "goal": s["goal"], "status": s["status"],
                    "steps": len(s["steps"]), "todo": len([t for t in s["todo"] if not t.get("done")])})
    return out


def note(text: str, kind: str = "note", sid: Optional[str] = None, project: Optional[str] = None,
         refs: Optional[List[str]] = None) -> dict:
    s = load(sid, project)
    s["steps"].append({"t": _now(), "kind": kind, "text": text, "refs": refs or []})
    save(s, project)
    return s


def set_state(key: str, value: Any, sid: Optional[str] = None, project: Optional[str] = None) -> dict:
    s = load(sid, project)
    s["state"][key] = value
    save(s, project)
    return s


def todo(text: str, sid: Optional[str] = None, project: Optional[str] = None, done: bool = False) -> dict:
    s = load(sid, project)
    for t in s["todo"]:
        if t["text"] == text:
            t["done"] = done
            break
    else:
        s["todo"].append({"text": text, "done": done})
    save(s, project)
    return s


def close(sid: Optional[str] = None, project: Optional[str] = None, summary: str = "") -> dict:
    s = load(sid, project)
    s["status"] = "closed"
    s["closed"] = _now()
    if summary:
        s["steps"].append({"t": _now(), "kind": "summary", "text": summary, "refs": []})
    save(s, project)
    return s


def resume_brief(sid: Optional[str] = None, project: Optional[str] = None) -> dict:
    s = load(sid, project)
    return {"id": s["id"], "mode": s["mode"], "goal": s["goal"], "intensity": s["intensity"],
            "state": s["state"], "open_todo": [t["text"] for t in s["todo"] if not t.get("done")],
            "last_steps": s["steps"][-8:]}
