"""Paths, environment, dynamic time windows and research-intensity profiles."""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

SKILL_ROOT = Path(__file__).resolve().parents[2]
ASSETS = SKILL_ROOT / "assets"

# Budgets are upper bounds, never quotas: a run may stop with fewer results.
INTENSITY: Dict[str, Dict[str, int]] = {
    "quick": {"max_queries_per_lane": 2, "per_query": 10, "lanes": 2, "focused_max": 5, "deep_max": 2},
    "standard": {"max_queries_per_lane": 3, "per_query": 20, "lanes": 4, "focused_max": 15, "deep_max": 6},
    "deep": {"max_queries_per_lane": 6, "per_query": 40, "lanes": 4, "focused_max": 40, "deep_max": 12},
}

ENV_KEYS = {
    "mailto": "CDRI_MAILTO",
    "openalex_email": "OPENALEX_EMAIL",
    "unpaywall_email": "UNPAYWALL_EMAIL",
    "s2_api_key": "S2_API_KEY",
    "ncbi_api_key": "NCBI_API_KEY",
    "github_token": "GITHUB_TOKEN",
}


def today() -> _dt.date:
    override = os.environ.get("CDRI_TODAY")
    if override:
        return _dt.date.fromisoformat(override)
    return _dt.date.today()


def months_ago(n: int, ref: Optional[_dt.date] = None) -> _dt.date:
    ref = ref or today()
    y, m = ref.year, ref.month - n
    while m <= 0:
        m += 12
        y -= 1
    day = min(ref.day, 28)
    return _dt.date(y, m, day)


def time_windows(window_months: int = 24, core_years: int = 5) -> Dict[str, str]:
    t = today()
    return {
        "today": t.isoformat(),
        "recent_from": months_ago(window_months, t).isoformat(),
        "core_from": months_ago(12 * core_years, t).isoformat(),
    }


def home() -> Path:
    h = Path(os.environ.get("CDRI_HOME", str(Path.home() / ".cdri")))
    h.mkdir(parents=True, exist_ok=True)
    return h


def cache_dir(kind: str) -> Path:
    d = home() / "cache" / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_dir(project: Optional[str] = None, create: bool = True) -> Path:
    root = Path(project or os.environ.get("CDRI_PROJECT", os.getcwd())).resolve()
    d = root / ".cdri"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def env(name: str) -> Optional[str]:
    key = ENV_KEYS.get(name, name)
    v = os.environ.get(key)
    if not v and name in ("openalex_email", "unpaywall_email"):
        v = os.environ.get("CDRI_MAILTO")
    return v or None


def load_config() -> Dict[str, Any]:
    p = home() / "config.json"
    cfg: Dict[str, Any] = {"window_months": 24, "core_years": 5, "default_intensity": "standard"}
    if p.exists():
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    return cfg


def save_config(cfg: Dict[str, Any]) -> Path:
    banned = {"s2_api_key", "ncbi_api_key", "github_token", "api_key"}
    leaked = [k for k in cfg if k.lower() in banned]
    if leaked:
        raise ValueError(f"secrets must come from environment variables, not config.json: {leaked}")
    p = home() / "config.json"
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def load_asset(name: str) -> Any:
    return json.loads((ASSETS / name).read_text(encoding="utf-8"))


def offline() -> bool:
    return os.environ.get("CDRI_OFFLINE", "") not in ("", "0", "false")
