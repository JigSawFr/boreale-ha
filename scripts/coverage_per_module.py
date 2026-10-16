"""Fails when a module of the integration is not covered by more than 95%
(Home Assistant's quality scale asks it of every module, not of the total).

    python -m pytest --cov=custom_components.playguard --cov-branch --cov-report=json
    python scripts/coverage_per_module.py [coverage.json]
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

FLOOR = 95.0
PACKAGE = Path("custom_components/playguard")


def main(report: str = "coverage.json") -> int:
    files = json.loads(Path(report).read_text(encoding="utf-8"))["files"]
    covered = {Path(name).as_posix(): data["summary"]["percent_covered"] for name, data in files.items()}
    failed = False
    for module in sorted(p.as_posix() for p in PACKAGE.glob("*.py")):
        percent = covered.get(module)
        if percent is None:
            print(f"   none  {module}: not in the report")
            failed = True
            continue
        ok = percent > FLOOR
        failed |= not ok
        print(f"{percent:6.1f}%  {module}{'' if ok else f': {FLOOR:g}% or less'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
