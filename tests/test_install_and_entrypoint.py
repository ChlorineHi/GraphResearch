"""Installer (copy, marker, foreign-dir protection, AGENTS.md block, uninstall) and the script entry point."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CDRI_INSTALL_HOME", str(tmp_path / "userhome"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def _installer():
    spec = importlib.util.spec_from_file_location("cdri_install", ROOT / "install.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_install_uninstall_roundtrip(env, monkeypatch):
    inst = _installer()
    dest = env.tmp / "skills"
    assert inst.main(["install", "--platform", "cursor", "--dest", str(dest), "--no-check"]) == 0
    d = dest / "cdri"
    assert (d / "SKILL.md").exists() and (d / inst.MARKER).exists()
    assert (d / "scripts" / "cdri.py").exists() and (d / "assets" / "mechanisms.json").exists()
    assert not list(d.rglob("__pycache__"))
    r = subprocess.run([sys.executable, str(d / "scripts" / "cdri.py"), "route", "跨领域迁移"],
                       capture_output=True, text=True, encoding="utf-8", env=dict(os.environ))
    assert r.returncode == 0 and json.loads(r.stdout)["mode"] == "transfer"
    assert inst.main(["uninstall", "--platform", "cursor"]) == 0
    assert not d.exists()
    assert env.home.exists()            # knowledge base is kept unless --purge-data --yes


def test_install_all_platform_paths_and_uninstall(env, tmp_path):
    inst = _installer()
    home = tmp_path / "userhome"
    proj = tmp_path / "proj_for_rule"
    assert inst.main(["install", "--platform", "all", "--agents-md", "--cursor-rule", "--project-dir", str(proj),
                      "--no-check"]) == 0
    expected = [home / ".claude/skills/cdri", home / ".codex/skills/cdri", home / ".agents/skills/cdri",
                home / ".cursor/skills/cdri", home / ".config/opencode/skill/cdri"]
    assert all((d / "SKILL.md").exists() for d in expected)
    assert inst.BEGIN in (home / ".codex/AGENTS.md").read_text(encoding="utf-8")
    assert (proj / ".cursor/rules/cdri.mdc").exists()
    assert inst.main(["uninstall", "--platform", "all"]) == 0
    assert not any(d.exists() for d in expected)
    assert inst.BEGIN not in (home / ".codex/AGENTS.md").read_text(encoding="utf-8")
    assert not (proj / ".cursor/rules/cdri.mdc").exists()


def test_install_refuses_foreign_directory(env):
    inst = _installer()
    dest = env.tmp / "skills"
    (dest / "cdri").mkdir(parents=True)
    (dest / "cdri" / "mine.txt").write_text("user content", encoding="utf-8")
    inst.main(["install", "--platform", "claude", "--dest", str(dest), "--no-check"])
    assert (dest / "cdri" / "mine.txt").exists()


def test_agents_md_block(env):
    inst = _installer()
    f = env.tmp / "AGENTS.md"
    f.write_text("# My rules\nkeep me\n", encoding="utf-8")
    inst.write_block(f, inst.agents_md_block(Path("/x/cdri")))
    inst.write_block(f, inst.agents_md_block(Path("/y/cdri")))       # idempotent replace
    t = f.read_text(encoding="utf-8")
    assert t.count(inst.BEGIN) == 1 and "/y/cdri" in t.replace("\\", "/") and "keep me" in t
    assert inst.strip_block(f)
    assert "CDRI" not in f.read_text(encoding="utf-8") and "keep me" in f.read_text(encoding="utf-8")


def test_purge_requires_confirmation(env):
    inst = _installer()
    env.home.mkdir(parents=True, exist_ok=True)
    assert inst.main(["uninstall", "--platform", "all", "--purge-data"]) == 1
    assert env.home.exists()


def test_entrypoint_help_and_offline_error(env, monkeypatch):
    script = ROOT / "skills" / "cdri" / "scripts" / "cdri.py"
    e = dict(os.environ)
    e.pop("CDRI_FIXTURES", None)
    e["CDRI_OFFLINE"] = "1"
    r = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, env=e)
    assert r.returncode == 0 and "landscape" in r.stdout
    r = subprocess.run([sys.executable, str(script), "search", "optimal transport", "--source", "openalex"],
                       capture_output=True, text=True, encoding="utf-8", env=e)
    out = json.loads(r.stdout)
    assert out["summary"]["failures"][0]["status"] == "offline"     # reported, not hidden
