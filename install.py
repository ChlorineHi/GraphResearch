#!/usr/bin/env python3
"""Install / uninstall the CDRI skill for Claude Code, Codex CLI, Cursor and OpenCode.

    python install.py install --platform all            # copy to every user-level skills dir
    python install.py install --platform cursor --scope project --project-dir .  --cursor-rule
    python install.py install --platform codex --agents-md --link
    python install.py status
    python install.py uninstall --platform all          # removes only what this installer created
    python install.py uninstall --platform all --purge-data --yes   # also deletes $CDRI_HOME (knowledge base!)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "skills" / "cdri"
MARKER = ".cdri-install.json"
BEGIN, END = "<!-- CDRI:BEGIN -->", "<!-- CDRI:END -->"
HOME = Path(os.environ.get("CDRI_INSTALL_HOME") or Path.home())

USER_TARGETS = {
    "claude": [HOME / ".claude" / "skills"],
    "codex": [HOME / ".codex" / "skills", HOME / ".agents" / "skills"],
    "cursor": [HOME / ".cursor" / "skills"],
    "opencode": [Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "opencode" / "skill"],
}
PROJECT_TARGETS = {"claude": [".claude/skills"], "codex": [".agents/skills"], "cursor": [".cursor/skills"],
                   "opencode": [".opencode/skill"]}


def cdri_home() -> Path:
    return Path(os.environ.get("CDRI_HOME") or str(HOME / ".cdri"))


def registry_path() -> Path:
    return cdri_home() / "installs.json"


def load_registry() -> list:
    p = registry_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_registry(items: list) -> None:
    registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry_path().write_text(json.dumps(items, indent=2), encoding="utf-8")


def targets(platform: str, scope: str, project_dir: Path, dest: str = None) -> list:
    if dest:
        return [Path(dest).expanduser()]
    if scope == "project":
        return [project_dir / p for p in PROJECT_TARGETS[platform]]
    return USER_TARGETS[platform]


def _ignore(_dir, names):
    return [n for n in names if n in ("__pycache__", ".pytest_cache") or n.endswith(".pyc")]


def install_one(base: Path, link: bool, force: bool) -> dict:
    dest = base / "cdri"
    if dest.exists() or dest.is_symlink():
        owned = (dest / MARKER).exists() or any(r["path"] == str(dest) for r in load_registry())
        if not owned and not force:
            return {"path": str(dest), "status": "skipped", "reason": "exists and was not installed by CDRI (--force)"}
        _remove(dest)
    base.mkdir(parents=True, exist_ok=True)
    mode = "copy"
    if link:
        try:
            os.symlink(SRC, dest, target_is_directory=True)
            mode = "symlink"
        except OSError as e:
            if os.name == "nt":
                r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dest), str(SRC)], capture_output=True, text=True)
                mode = "junction" if r.returncode == 0 else "copy"
            if mode == "copy":
                print(f"  link failed ({e}); copying instead", file=sys.stderr)
    if mode == "copy":
        shutil.copytree(SRC, dest, ignore=_ignore)
        (dest / MARKER).write_text(json.dumps({"installed": _dt.datetime.now().isoformat(timespec="seconds"),
                                               "source": str(SRC), "mode": mode}), encoding="utf-8")
    return {"path": str(dest), "status": "installed", "mode": mode}


def _remove(dest: Path) -> None:
    if dest.is_symlink():
        dest.unlink()
    elif os.name == "nt" and dest.exists() and _is_junction(dest):
        os.rmdir(dest)
    elif dest.exists():
        shutil.rmtree(dest)


def _is_junction(p: Path) -> bool:
    try:
        return bool(os.readlink(str(p)))
    except (OSError, ValueError):
        return False


def agents_md_block(skill_path: Path) -> str:
    return (f"{BEGIN}\n## Research skill: CDRI\nFor literature research, cross-domain method transfer, experiment "
            f"diagnosis, data/metric audits or research ideation, read `{skill_path / 'SKILL.md'}` and follow it. "
            f"CLI: `python {skill_path / 'scripts' / 'cdri.py'}`.\n{END}\n")


def write_block(file: Path, block: str) -> None:
    text = file.read_text(encoding="utf-8") if file.exists() else ""
    if BEGIN in text:
        a, b = text.index(BEGIN), text.index(END) + len(END)
        text = text[:a] + block.rstrip("\n") + text[b:]
    else:
        text = (text.rstrip("\n") + "\n\n" if text else "") + block
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")


def strip_block(file: Path) -> bool:
    if not file.exists():
        return False
    text = file.read_text(encoding="utf-8")
    if BEGIN not in text:
        return False
    a, b = text.index(BEGIN), text.index(END) + len(END)
    file.write_text((text[:a].rstrip("\n") + "\n" + text[b:].lstrip("\n")).strip("\n") + "\n", encoding="utf-8")
    return True


CURSOR_RULE = """---
description: Use the CDRI research skill for literature research, cross-domain transfer, diagnosis and audits
alwaysApply: false
---
<!-- installed by CDRI install.py -->
For research tasks (literature landscape, paper deep reading, cross-domain method transfer, diagnosis of failing
experiments, data/metric integrity audits, research ideas, scientific storytelling) read the `cdri` skill
(SKILL.md) and use its CLI. Never fabricate citations; report search failures; label evidence.
"""


def cmd_install(a) -> int:
    plats = list(USER_TARGETS) if a.platform == "all" else [a.platform]
    reg = load_registry()
    results = []
    for p in plats:
        for base in targets(p, a.scope, Path(a.project_dir).resolve(), a.dest):
            r = install_one(base, a.link, a.force)
            r["platform"] = p
            results.append(r)
            if r["status"] == "installed":
                reg = [x for x in reg if x["path"] != r["path"]] + [{"platform": p, "path": r["path"], "mode": r["mode"]}]
            if a.dest:
                break
    if a.agents_md and ("codex" in plats):
        f = HOME / ".codex" / "AGENTS.md" if a.scope == "user" else Path(a.project_dir) / "AGENTS.md"
        inst = next((Path(r["path"]) for r in results if r["platform"] == "codex" and r["status"] == "installed"), SRC)
        write_block(f, agents_md_block(inst))
        reg.append({"platform": "codex", "path": str(f), "mode": "agents_md_block"})
        results.append({"platform": "codex", "path": str(f), "status": "AGENTS.md block written"})
    if a.cursor_rule and ("cursor" in plats):
        f = Path(a.project_dir).resolve() / ".cursor" / "rules" / "cdri.mdc"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(CURSOR_RULE, encoding="utf-8")
        reg.append({"platform": "cursor", "path": str(f), "mode": "cursor_rule"})
        results.append({"platform": "cursor", "path": str(f), "status": "rule written"})
    save_registry(reg)
    for r in results:
        print(f"[{r['platform']}] {r['status']}: {r['path']}" + (f" ({r.get('mode') or r.get('reason')})"
                                                              if r.get("mode") or r.get("reason") else ""))
    if not a.no_check:
        installed = next((Path(r["path"]) for r in results if r["status"] == "installed"), SRC)
        subprocess.run([sys.executable, str(installed / "scripts" / "cdri.py"), "config", "check"])
    print("\nNext: set optional keys (see README: S2_API_KEY, NCBI_API_KEY, CDRI_MAILTO, UNPAYWALL_EMAIL).")
    return 0


def cmd_uninstall(a) -> int:
    plats = set(USER_TARGETS) if a.platform == "all" else {a.platform}
    reg = load_registry()
    keep = []
    for r in reg:
        if r["platform"] not in plats:
            keep.append(r)
            continue
        p = Path(r["path"])
        if r["mode"] == "agents_md_block":
            print(f"[{r['platform']}] AGENTS.md block removed: {p}" if strip_block(p) else f"no block in {p}")
        elif r["mode"] == "cursor_rule":
            if p.exists() and "installed by CDRI" in p.read_text(encoding="utf-8"):
                p.unlink()
                print(f"[cursor] rule removed: {p}")
        else:
            if p.exists() or p.is_symlink():
                if r["mode"] == "copy" and not (p / MARKER).exists():
                    print(f"[{r['platform']}] skipped {p}: marker missing (not removing unknown content)")
                    keep.append(r)
                    continue
                _remove(p)
                print(f"[{r['platform']}] removed {p}")
    # also clean copies with markers that are not in the registry (e.g. registry deleted)
    for p in plats:
        for base in USER_TARGETS[p]:
            d = base / "cdri"
            if (d / MARKER).exists():
                shutil.rmtree(d)
                print(f"[{p}] removed {d}")
    save_registry(keep)
    if a.purge_data:
        h = cdri_home()
        if not a.yes:
            print(f"--purge-data would delete {h} (knowledge base, caches, cards). Re-run with --yes to confirm.")
            return 1
        if h.exists():
            shutil.rmtree(h)
            print(f"removed data directory {h}")
    else:
        print(f"Knowledge base kept at {cdri_home()} (use --purge-data --yes to delete). Project data stays in "
              "<project>/.cdri/.")
    return 0


def cmd_status(a) -> int:
    print(f"source: {SRC}")
    print(f"data:   {cdri_home()}")
    for p, bases in USER_TARGETS.items():
        for base in bases:
            d = base / "cdri"
            state = "installed (copy)" if (d / MARKER).exists() else "linked" if d.is_symlink() or _is_junction(d) \
                else "present (not by CDRI)" if d.exists() else "-"
            print(f"  {p:9s} {d}: {state}")
    for r in load_registry():
        print(f"  registry: {r}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CDRI skill installer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("install")
    i.add_argument("--platform", default="all", choices=["all", *USER_TARGETS])
    i.add_argument("--scope", default="user", choices=["user", "project"])
    i.add_argument("--project-dir", default=".")
    i.add_argument("--dest", help="explicit skills directory (the skill is placed in <dest>/cdri)")
    i.add_argument("--link", action="store_true", help="symlink/junction instead of copy (for development)")
    i.add_argument("--force", action="store_true", help="replace an existing non-CDRI 'cdri' directory")
    i.add_argument("--agents-md", action="store_true", help="add a pointer block to Codex AGENTS.md")
    i.add_argument("--cursor-rule", action="store_true", help="write .cursor/rules/cdri.mdc in --project-dir")
    i.add_argument("--no-check", action="store_true")
    u = sub.add_parser("uninstall")
    u.add_argument("--platform", default="all", choices=["all", *USER_TARGETS])
    u.add_argument("--purge-data", action="store_true")
    u.add_argument("--yes", action="store_true")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    return {"install": cmd_install, "uninstall": cmd_uninstall, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
