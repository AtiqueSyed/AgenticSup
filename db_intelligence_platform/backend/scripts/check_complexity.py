#!/usr/bin/env python3
"""Fail the build if any block has cyclomatic complexity >= MAX_COMPLEXITY.

Usage:  python scripts/check_complexity.py [path] [--max N]
"""

import sys
from pathlib import Path

from radon.complexity import cc_visit
from radon.visitors import Function

MAX_COMPLEXITY = 10


def blocks(path: Path):
    for file in sorted(path.rglob("*.py")):
        if "__pycache__" in file.parts:
            continue
        for block in cc_visit(file.read_text(encoding="utf-8")):
            yield file, block


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("-") else Path("src")
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else MAX_COMPLEXITY

    offenders = [
        (file, block)
        for file, block in blocks(target)
        if block.complexity >= limit and isinstance(block, Function)
    ]

    for file, block in offenders:
        print(f"{file}:{block.lineno} {block.name} has complexity {block.complexity} (>= {limit})")

    if offenders:
        print(f"\nFAIL: {len(offenders)} block(s) at or above complexity {limit}")
        return 1

    print(f"OK: every block in {target} is below complexity {limit}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
