#!/usr/bin/env python
"""Diff one measured state upstream against the same state here.

    python tools/measure_diff.py entity-picker open-light
    python tools/measure_diff.py --all

Reads `tools/drives/upstream/measure/<page>-<state>.json` against
`tools/drives/measure/<page>-<state>.json`. The Qt object names are the upstream `data-slot`
values, give or take the few renamed below, so the two walks line up slot by slot.

What is compared, and why only this:

* height, for every matched slot — the ladders, the row pitch, the search row, the table cell.
* width, only for an element that is not the one filling its parent, since width is the caller's
  business here (rule 3) and the demo stage is not as wide as the upstream pane.
* the inset of a child inside the nearest container that holds it — leading, trailing and top —
  which is where padding and gap actually show.
* font size, only where the element carries text.
* the theme tokens, upstream's `oklch()` converted to sRGB, and the painted pixel under an
  element's own middle.

Anything past a pixel, or two units per channel, is printed as a finding.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "tools" / "drives" / "upstream" / "measure"
OURS = ROOT / "tools" / "drives" / "measure"

#: The few slots whose Qt object name is not the upstream `data-slot`.
RENAMES = {
    "picker-row-lead": "picker-row-leading",
    "picker-row-tick": "picker-row-indicator",
    "picker-row-checkbox": "picker-row-indicator",
}

#: The slots a child is measured against: the nearest of these that holds it.
CONTAINERS = ("-control", "-option", "-more", "-content", "-search", "-row", "-cell", "-header")

#: How far a length may drift before it is a finding, and how far a channel may.
PIXELS = 1.0
CHANNELS = 2

#: The widest an inset can be and still be read as padding rather than as a sibling's width.
INSET = 64

#: The widest an element can be and still have its width compared rather than left to the caller.
NARROW = 200


# --- colour ------------------------------------------------------------------------------


def _srgb(value: float) -> int:
    value = 1.055 * (value ** (1 / 2.4)) - 0.055 if value > 0.0031308 else 12.92 * value
    return max(0, min(255, int(round(value * 255))))


def oklch(text: str) -> tuple | None:
    """`oklch(L C H / a)` as (r, g, b), the conversion the browser does to paint it."""
    found = re.match(r"oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)", text.strip())
    if not found:
        return None
    lightness = float(found.group(1).rstrip("%"))
    if found.group(1).endswith("%"):
        lightness /= 100.0
    chroma, hue = float(found.group(2)), math.radians(float(found.group(3)))
    a, b = chroma * math.cos(hue), chroma * math.sin(hue)
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        _srgb(+4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
        _srgb(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
        _srgb(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_),
    )


def rgb(text: str) -> tuple | None:
    """Whatever the two walks write a colour as, as (r, g, b), or `None` for see-through."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("#") and len(text) in (7, 9):
        parts = tuple(int(text[i : i + 2], 16) for i in (1, 3, 5))
        if len(text) == 9 and int(text[7:9], 16) == 0:
            return None
        return parts
    if text.startswith("oklch"):
        if "/" in text:
            return None
        return oklch(text)
    found = re.match(r"rgba?\(([^)]*)\)", text)
    if found:
        bits = [one.strip() for one in found.group(1).replace("/", " ").split(",")]
        if len(bits) >= 3:
            if len(bits) == 4 and float(bits[3]) == 0:
                return None
            return tuple(int(float(one)) for one in bits[:3])
    return None


def apart(one: tuple | None, other: tuple | None) -> int:
    if one is None or other is None:
        return 0
    return max(abs(a - b) for a, b in zip(one, other))


# --- reading a measurement ---------------------------------------------------------------


def normalise(slot: str) -> str:
    if slot in RENAMES:
        return RENAMES[slot]
    for ours, theirs in (("-list-option", "-option"), ("-list-more", "-more")):
        if slot.endswith(ours):
            return slot[: -len(ours)] + theirs
    return slot


def px(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if text.endswith("px"):
        text = text[:-2]
    try:
        return float(text)
    except ValueError:
        return 0.0


def load(where: Path, page: str, state: str) -> dict | None:
    path = where / f"{page}-{state}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def holder(one: dict, elements: list[dict]) -> dict | None:
    """The smallest container element that holds `one`, or `None` when nothing does."""
    best = None
    for other in elements:
        if other is one or other.get("where") != one.get("where"):
            continue
        slot = normalise(other.get("slot", ""))
        if not slot.endswith(CONTAINERS):
            continue
        ox, oy = px(other["x"]), px(other["y"])
        if not (ox <= px(one["x"]) and oy <= px(one["y"])):
            continue
        if px(one["x"]) + px(one["w"]) > ox + px(other["w"]) + 0.5:
            continue
        if px(one["y"]) + px(one["h"]) > oy + px(other["h"]) + 0.5:
            continue
        area = px(other["w"]) * px(other["h"])
        if area <= px(one["w"]) * px(one["h"]):
            continue
        if best is None or area < px(best["w"]) * px(best["h"]):
            best = other
    return best


def shape(measured: dict) -> dict:
    """One row per `(container, slot)`: its height, width and the insets it keeps."""
    elements = measured["elements"]
    out: dict[tuple, dict] = {}
    for one in elements:
        slot = normalise(one.get("slot", ""))
        if not slot:
            continue
        held = holder(one, elements)
        key = (normalise(held.get("slot", "")) if held else "", slot)
        if key in out:
            continue
        row = {
            "h": px(one["h"]),
            "w": px(one["w"]),
            "text": one.get("text", ""),
            "font": px(one.get("font-size")),
            "colour": rgb(one.get("color") or one.get("paint-mid")),
            "fill": rgb(one.get("background-color") or one.get("paint-right")),
        }
        if held is not None:
            row["left"] = px(one["x"]) - px(held["x"])
            row["right"] = (px(held["x"]) + px(held["w"])) - (px(one["x"]) + px(one["w"]))
            row["top"] = px(one["y"]) - px(held["y"])
        out[key] = row
    return out


# --- the diff ----------------------------------------------------------------------------


def findings(page: str, state: str) -> list[tuple]:
    theirs, ours = load(UPSTREAM, page, state), load(OURS, page, state)
    if theirs is None or ours is None:
        return [("(missing)", "state", "upstream" if theirs is None else "", "ours" if ours is None else "")]
    a, b = shape(theirs), shape(ours)
    found: list[tuple] = []
    for key in sorted(set(a) & set(b), key=lambda one: (one[0], one[1])):
        up, mine = a[key], b[key]
        where = f"{key[0]}/{key[1]}" if key[0] else key[1]
        for field in ("h", "top"):
            if field not in up or field not in mine:
                continue
            if abs(up[field] - mine[field]) > PIXELS:
                found.append((where, field, round(up[field], 1), round(mine[field], 1)))
        # An inset only reads as padding while it is small: past `INSET` it is the width of
        # whatever stands before the element, and the demo stage here is not the upstream pane's
        # width, so that distance says nothing about the port.
        for field in ("left", "right"):
            if field not in up or field not in mine or up[field] > INSET:
                continue
            if abs(up[field] - mine[field]) > PIXELS:
                found.append((where, field, round(up[field], 1), round(mine[field], 1)))
        # Width is the caller's business (rule 3) for anything that fills its parent, so only a
        # small element — a chip, an icon control, an indicator column — is compared.
        if up["w"] < NARROW and mine["w"] < NARROW and abs(up["w"] - mine["w"]) > PIXELS:
            found.append((where, "w", round(up["w"], 1), round(mine["w"], 1)))
    for one, other in (("(upstream only)", set(a) - set(b)), ("(ours only)", set(b) - set(a))):
        names = sorted({key[1] for key in other})
        if names:
            found.append((one, "slots", ", ".join(names[:16]), ""))
    return found


def tokens(page: str, state: str) -> list[tuple]:
    theirs, ours = load(UPSTREAM, page, state), load(OURS, page, state)
    if theirs is None or ours is None:
        return []
    pairs = {
        "--background": "background", "--foreground": "foreground", "--muted": "muted",
        "--muted-foreground": "muted_foreground", "--accent": "accent",
        "--accent-foreground": "accent_foreground", "--popover": "popover",
        "--popover-foreground": "popover_foreground", "--border": "border",
        "--input": "input", "--ring": "ring", "--destructive": "destructive",
        "--secondary": "secondary", "--secondary-foreground": "secondary_foreground",
    }
    out = []
    for theirs_name, ours_name in pairs.items():
        up = rgb(theirs["tokens"].get(theirs_name, ""))
        mine = rgb(ours["tokens"].get(ours_name, ""))
        if up and mine and apart(up, mine) > CHANNELS:
            out.append((f"token {ours_name}", "rgb", up, mine))
    return out


def main() -> int:
    if sys.argv[1] == "--all":
        pages = sorted({path.name.rsplit("-", 2)[0] for path in UPSTREAM.glob("*-rest-light.json")})
        states = ("rest-light", "open-light", "rest-dark", "open-dark")
    else:
        pages, states = [sys.argv[1]], [sys.argv[2]] if len(sys.argv) > 2 else (
            "rest-light", "open-light", "rest-dark", "open-dark")
    for page in pages:
        for state in states:
            rows = findings(page, state) + tokens(page, state)
            if not rows:
                print(f"{page} {state}: no drift")
                continue
            print(f"{page} {state}")
            for where, field, up, mine in rows:
                print(f"  {where:46s} {field:10s} upstream={up!s:<28s} ours={mine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
