#!/usr/bin/env python3
"""Check that every `cdri <command> [<sub>]` mentioned in the skill's docs and assets exists in the CLI parser."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "cdri" / "scripts"))

from cdri_lib.cli import build_parser  # noqa: E402


def command_tree() -> dict:
    tree = {}
    top = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    for name, sp in top.choices.items():
        subs = [a for a in sp._actions if isinstance(a, argparse._SubParsersAction)]
        tree[name] = set(subs[0].choices) if subs else None
    return tree


def main() -> int:
    tree = command_tree()
    rx = re.compile(r"(?:cdri|\$CDRI)\s+([a-z][a-z-]*)(?:\s+([a-z][a-z-]*))?")
    bad = []
    files = [p for p in (ROOT / "skills" / "cdri").rglob("*") if p.suffix in (".md", ".json", ".py")]
    files += [ROOT / "README.md"] + list((ROOT / "docs").glob("*.md"))
    for p in files:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in rx.finditer(line):
                cmd, sub = m.group(1), m.group(2)
                if cmd not in tree:
                    if cmd in ("lib", "fx", "home", "skill", "install", "py"):
                        continue
                    bad.append(f"{p.relative_to(ROOT)}:{i}: unknown command '{cmd}'")
                elif tree[cmd] and sub and sub not in tree[cmd]:
                    bad.append(f"{p.relative_to(ROOT)}:{i}: unknown subcommand '{cmd} {sub}'")
    print("\n".join(bad) or "all command references resolve")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
