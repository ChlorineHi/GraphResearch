from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "cdri" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixture_builder  # noqa: E402
from cdri_lib import cli  # noqa: E402

TODAY = "2026-06-15"
FIX = Path(__file__).resolve().parent / "fixtures"
SECRET_ENV = ("S2_API_KEY", "NCBI_API_KEY", "GITHUB_TOKEN", "CDRI_MAILTO", "OPENALEX_EMAIL", "UNPAYWALL_EMAIL",
              "CDRI_OFFLINE", "CDRI_EMBEDDINGS")


def run(*args, project=None):
    """Run the CLI in-process; return (exit_code, parsed JSON or raw text)."""
    argv = [str(a) for a in args]
    if project:
        argv = ["--project", str(project)] + argv
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    text = buf.getvalue()
    try:
        return code, json.loads(text)
    except json.JSONDecodeError:
        return code, text


def ok(*args, project=None):
    code, obj = run(*args, project=project)
    assert code == 0, obj
    return obj


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    fx = fixture_builder.build(tmp_path / "http")
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CDRI_HOME", str(home))
    monkeypatch.setenv("CDRI_PROJECT", str(proj))
    monkeypatch.setenv("CDRI_FIXTURES", str(fx))
    monkeypatch.setenv("CDRI_TODAY", TODAY)
    return SimpleNamespace(home=home, proj=proj, fx=fx, tmp=tmp_path)


def write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def git_repo_copy(dest: Path) -> tuple:
    """Copy the synthetic fixture repo and commit it so code links can be pinned to a real local commit."""
    shutil.copytree(FIX / "repo_tfbind", dest)
    g = ["git", "-c", "user.email=fixture@example.invalid", "-c", "user.name=fixture"]
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(g + ["add", "-A"], cwd=dest, check=True)
    subprocess.run(g + ["commit", "-q", "-m", "fixture"], cwd=dest, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True).stdout.strip()
    return dest, sha
