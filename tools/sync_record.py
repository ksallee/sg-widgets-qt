"""Record one ported item in sync/manifest.json.

    python tools/sync_record.py widgets/entity-picker \
        --upstream packages/react/src/registry/sg/components/entity-picker.tsx apps/site/src/props/entity-picker.ts \
        --ported src/sg_widgets_qt/widgets/entity_picker.py docs/widgets/entity-picker.props.json \
        --status complete --note "The row renderer is a keyword, not a snippet."

Upstream paths are relative to the upstream checkout, ported paths to this repo. The manifest keeps,
per upstream file, the sha256 of its content at the time of the record and the upstream commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "sync" / "manifest.json"
UPSTREAM = Path(os.environ.get("SG_WIDGETS_UPSTREAM", os.path.expanduser("~/dev/sg-widgets")))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upstream_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=UPSTREAM, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def load() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"upstream": {"path": "~/dev/sg-widgets", "branch": "dev"}, "items": {}}


def save(data: dict) -> None:
    data["items"] = dict(sorted(data["items"].items()))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("item", help="core/<module>, primitives/<name>, widgets/<name>, demos/<name>, docs/<name>")
    p.add_argument("--upstream", nargs="+", required=True, help="upstream files this item ports")
    p.add_argument("--ported", nargs="+", required=True, help="files in this repo")
    p.add_argument("--status", choices=["complete", "partial", "skipped"], required=True)
    p.add_argument("--note", default="")
    a = p.parse_args(argv)

    missing = [f for f in a.upstream if not (UPSTREAM / f).exists()]
    if missing:
        print("upstream file not found: " + ", ".join(missing), file=sys.stderr)
        return 2
    missing = [f for f in a.ported if not (HERE / f).exists() and a.status != "skipped"]
    if missing:
        print("ported file not found: " + ", ".join(missing), file=sys.stderr)
        return 2

    data = load()
    data["upstream"]["commit"] = upstream_commit()
    data["items"][a.item] = {
        "status": a.status,
        "upstream": {f: sha256(UPSTREAM / f) for f in a.upstream},
        "ported": list(a.ported),
        "commit": data["upstream"]["commit"],
        "note": a.note,
    }
    save(data)
    print(f"{a.item}: {a.status}, {len(a.upstream)} upstream file(s), {len(a.ported)} ported file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
