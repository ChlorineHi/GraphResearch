#!/usr/bin/env python3
"""Entry point for the CDRI command line (`python cdri.py --help`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdri_lib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
