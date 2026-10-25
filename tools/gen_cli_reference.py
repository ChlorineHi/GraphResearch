"""Regenerate skills/cdri/references/cli.md from the argparse definitions (keeps docs in sync with code)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "cdri" / "scripts"))

from cdri_lib.cli import build_parser  # noqa: E402


def _subparsers(p):
    for a in p._actions:
        if isinstance(a, argparse._SubParsersAction):
            return a.choices
    return {}


def _usage(p, prog):
    p.prog = prog
    return " ".join(t for t in p.format_usage().replace("usage: ", "").split() if t != "[-h]")


def main():
    ap = build_parser()
    out = ["# CDRI command reference", "",
           "Generated from the argparse definitions by `tools/gen_cli_reference.py`. "
           "`$CDRI` = `python <skill dir>/scripts/cdri.py`; global option `--project PATH`.", ""]
    for name, sp in _subparsers(ap).items():
        out += [f"## {name}", ""] + ([sp.description, ""] if sp.description else [])
        subs = _subparsers(sp)
        if subs:
            for sub, ssp in subs.items():
                out.append(f"- `{_usage(ssp, f'cdri {name} {sub}')}`")
        else:
            out.append(f"- `{_usage(sp, f'cdri {name}')}`")
        out.append("")
    dest = ROOT / "skills" / "cdri" / "references" / "cli.md"
    dest.write_text("\n".join(out), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
