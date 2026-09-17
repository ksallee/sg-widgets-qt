#!/usr/bin/env python
"""Split one measure run into a file per state.

    node tools/qa.mjs ... --drive .../measure/entity-picker.js | \
        python tools/measure_split.py tools/drives/upstream/measure entity-picker

Reads the whole `qa` answer on standard input and writes `<dir>/<page>-<state>.json` for every
state the drive measured, so the diff reads one file per `(page, state)`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    where = Path(sys.argv[1])
    page = sys.argv[2]
    raw = sys.stdin.read()
    start = raw.find("{")
    if start < 0:
        sys.stderr.write(f"{page}: no JSON on standard input\n")
        return 2
    try:
        answer = json.loads(raw[start:])
    except json.JSONDecodeError as error:
        sys.stderr.write(f"{page}: {error}\n")
        return 2
    result = answer.get("result") or {}
    states = result.get("states") or {}
    if not states:
        sys.stderr.write(f"{page}: measured nothing ({result.get('verdict') or answer.get('error')})\n")
        return 1
    where.mkdir(parents=True, exist_ok=True)
    for state, body in states.items():
        (where / f"{page}-{state}.json").write_text(
            json.dumps(body, indent=1, sort_keys=True), encoding="utf-8"
        )
    print(f"{page}: {' '.join(sorted(states))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
