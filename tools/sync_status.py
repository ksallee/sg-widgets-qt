"""Report what drifted between the upstream checkout and sync/manifest.json.

    python tools/sync_status.py            # human report
    python tools/sync_status.py --json     # machine report, the shape /sync reads

Three lists: items whose upstream files changed since they were recorded, upstream items nothing
here ports yet, and items recorded as partial or skipped. An item is "changed" when any of its
upstream files hashes differently or was deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "sync" / "manifest.json"
UPSTREAM = Path(os.environ.get("SG_WIDGETS_UPSTREAM", os.path.expanduser("~/dev/sg-widgets")))

# Where the upstream keeps each kind of item, and how an item name is read off a path.
KINDS = {
    "core": ("packages/core/src", re.compile(r"^(?!index$)([a-z0-9-]+)\.ts$")),
    "primitives": ("packages/react/src/components/ui", re.compile(r"^([a-z0-9-]+)\.tsx?$")),
    "widgets": ("packages/react/src/registry/sg/components", re.compile(r"^([a-z0-9-]+)\.tsx?$")),
    "demos": ("apps/site/src/demos", re.compile(r"^(?!_)([a-z0-9-]+)$")),
    "docs": ("apps/site/src/content/docs/widgets", re.compile(r"^(?!index$)([a-z0-9-]+)\.mdx$")),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upstream_items() -> dict[str, str]:
    """Every item the upstream has, keyed `kind/name`, valued by its main path."""
    out: dict[str, str] = {}
    for kind, (folder, pattern) in KINDS.items():
        root = UPSTREAM / folder
        if not root.exists():
            continue
        for entry in sorted(root.iterdir()):
            m = pattern.match(entry.name)
            if m:
                out[f"{kind}/{m.group(1)}"] = str(entry.relative_to(UPSTREAM))
    return out


def upstream_log(since: str | None) -> list[str]:
    if not since:
        return []
    out = subprocess.run(
        ["git", "log", "--oneline", f"{since}..HEAD"], cwd=UPSTREAM, capture_output=True, text=True
    )
    return [line for line in out.stdout.splitlines() if line]


def report() -> dict:
    data = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"upstream": {}, "items": {}}
    items = data.get("items", {})
    changed: dict[str, list[str]] = {}
    for name, item in items.items():
        drift = []
        for path, digest in item.get("upstream", {}).items():
            full = UPSTREAM / path
            if not full.exists():
                drift.append(f"{path} (deleted)")
            elif sha256(full) != digest:
                drift.append(path)
        if drift:
            changed[name] = drift
    known = set(items)
    new = {name: path for name, path in upstream_items().items() if name not in known}
    incomplete = {name: item for name, item in items.items() if item.get("status") != "complete"}
    return {
        "upstream_commit_recorded": data.get("upstream", {}).get("commit"),
        "upstream_log_since": upstream_log(data.get("upstream", {}).get("commit")),
        "changed": changed,
        "new": new,
        "incomplete": {name: {"status": i["status"], "note": i.get("note", "")} for name, i in incomplete.items()},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    r = report()
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    print(f"recorded upstream commit: {r['upstream_commit_recorded'] or 'none'}")
    if r["upstream_log_since"]:
        print(f"\nupstream commits since ({len(r['upstream_log_since'])}):")
        for line in r["upstream_log_since"][:40]:
            print("  " + line)
    print(f"\nchanged ({len(r['changed'])}):")
    for name, files in r["changed"].items():
        print(f"  {name}: " + ", ".join(files))
    print(f"\nnot ported yet ({len(r['new'])}):")
    for name, path in r["new"].items():
        print(f"  {name}  <- {path}")
    print(f"\npartial or skipped ({len(r['incomplete'])}):")
    for name, i in r["incomplete"].items():
        print(f"  {name}: {i['status']}" + (f", {i['note']}" if i["note"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
