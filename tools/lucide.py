"""Download the lucide SVGs the widgets draw.

    python tools/lucide.py                  # every name in ICONS
    python tools/lucide.py --only x check   # those names only
    python tools/lucide.py --force          # refetch what is already there

The icons land in `src/sg_widgets_qt/icons/lucide/` beside the lucide ISC licence, which the
script fetches from the lucide repository. `ICONS` is every glyph the upstream React and Svelte
widgets import, in kebab-case, plus the set the Qt widgets need, so the script is re-runnable.

Only `urllib.request`, so the repository takes no dependency on an HTTP client.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src" / "sg_widgets_qt" / "icons" / "lucide"

UNPKG = "https://unpkg.com/lucide-static@latest/icons/{name}.svg"
GITHUB = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{name}.svg"
LICENCE_URL = "https://raw.githubusercontent.com/lucide-icons/lucide/main/LICENSE"

TIMEOUT = 30
USER_AGENT = "sg-widgets-qt/tools/lucide.py"

#: Every glyph the widgets draw. The first block is what the upstream React and Svelte widgets
#: import, converted from PascalCase; the rest is what the Qt widgets, the showcase and the
#: delegates need.
ICONS = (
    "arrow-down",
    "arrow-left-to-line",
    "arrow-up",
    "arrow-up-down",
    "bot",
    "box",
    "braces",
    "building-2",
    "calendar",
    "calendar-clock",
    "check",
    "chevron-down",
    "chevron-left",
    "chevron-right",
    "chevron-up",
    "chevrons-up-down",
    "circle",
    "circle-alert",
    "circle-check",
    "circle-dollar-sign",
    "circle-dot",
    "circle-x",
    "clapperboard",
    "clock",
    "columns-3",
    "copy",
    "dot",
    "ellipsis-vertical",
    "external-link",
    "eye",
    "eye-off",
    "file",
    "file-box",
    "file-text",
    "film",
    "filter",
    "fingerprint",
    "folder",
    "folder-open",
    "git-branch",
    "globe",
    "grip-vertical",
    "hash",
    "history",
    "hourglass",
    "image",
    "inbox",
    "info",
    "key-round",
    "layers",
    "layout-grid",
    "link",
    "link-2",
    "list",
    "list-checks",
    "list-filter",
    "loader",
    "loader-circle",
    "message-square",
    "minus",
    "moon",
    "more-horizontal",
    "palette",
    "pencil",
    "percent",
    "pin-off",
    "play",
    "plus",
    "refresh-cw",
    "rotate-ccw",
    "rows-3",
    "ruler",
    "search",
    "search-x",
    "settings",
    "shapes",
    "sigma",
    "square",
    "square-check",
    "sun",
    "table",
    "tag",
    "timer",
    "toggle-left",
    "trash-2",
    "triangle-alert",
    "type",
    "user",
    "users",
    "video",
    "x",
)


class Offline(Exception):
    """The network did not answer at all."""


def fetch(url: str) -> bytes:
    """The bytes at `url`. Raises `Offline` when nothing answered, `HTTPError` on a status."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310
            return answer.read()
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, OSError) as error:
        raise Offline(str(error)) from error


def fetch_icon(name: str) -> bytes:
    """One icon's SVG, from unpkg, falling back to the raw repository."""
    try:
        return fetch(UNPKG.format(name=name))
    except urllib.error.HTTPError:
        return fetch(GITHUB.format(name=name))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", nargs="+", metavar="NAME", help="fetch these names instead of every one")
    p.add_argument("--force", action="store_true", help="refetch icons already on disk")
    p.add_argument("--list", action="store_true", help="print the names and stop")
    a = p.parse_args(argv)

    names = list(a.only) if a.only else list(ICONS)
    if a.list:
        print("\n".join(names))
        return 0

    TARGET.mkdir(parents=True, exist_ok=True)
    try:
        licence = fetch(LICENCE_URL)
    except Offline as error:
        print(f"the network is unavailable, nothing fetched: {error}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as error:
        print(f"the lucide licence answered {error.code}, nothing fetched", file=sys.stderr)
        return 1
    (TARGET / "LICENSE").write_bytes(licence)

    written = 0
    skipped = 0
    failed: list[str] = []
    for name in names:
        path = TARGET / f"{name}.svg"
        if path.exists() and not a.force:
            skipped += 1
            continue
        try:
            path.write_bytes(fetch_icon(name))
        except Offline as error:
            print(f"the network is unavailable, stopping after {written} icon(s): {error}", file=sys.stderr)
            return 1
        except urllib.error.HTTPError as error:
            failed.append(f"{name} ({error.code})")
            continue
        written += 1

    print(f"{written} written, {skipped} already there, {len(names)} asked for, in {TARGET}")
    if failed:
        print("no such icon upstream: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
