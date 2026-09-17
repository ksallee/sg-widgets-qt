"""Every editor of the wave under reduced motion: nothing moves and no timer is left running.

`theme.reduced_motion` collapses every transition to opacity at the same durations, which in this
package means an `AnimatedValue` lands on its target at once. This walks the page for them, moves
the ones a gesture would move, and answers whether any animation is still running.

    .venv/bin/python tools/qa.py --page number-editor --reduced-motion \
        --drive tools/drives/editors-reduced-motion.py --shot shots/number-editor-reduced.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import top_levels  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import AnimatedValue
    from sg_widgets_qt.theme import theme_of

    failures: list[str] = []
    theme = theme_of(page)
    if not theme.reduced_motion:
        return {"verdict": "FAIL the page is not under reduced motion"}

    values = list(page.findChildren(AnimatedValue))
    for window in top_levels():
        values.extend(v for v in window.findChildren(AnimatedValue) if v not in values)

    # Ask every one of them to move. Under reduced motion each lands at once, so none of them is
    # left with a timer running after the loop has been spun.
    for value in values:
        value.set(1.0 if value.value < 0.5 else 0.0)
    wait(60)
    running = [v for v in values if v.running]
    if running:
        failures.append(f"{len(running)} of {len(values)} animations are still running")

    # And the hover of a real control, which is the gesture the page makes most.
    hovered = []
    for name in ("date-editor-trigger", "color-editor-swatch", "number-editor-increment"):
        for widget in find(name, all=True) or []:
            setter = getattr(widget, "set_hovered", None)
            if callable(setter):
                setter(True)
                hovered.append(name)
    wait(60)
    still = [v for v in values if v.running]
    if still:
        failures.append(f"a hover left {len(still)} animations running")

    return {
        "verdict": (
            f"PASS {len(values)} animated values, all inert under reduced motion"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "animated": len(values),
        "hovered": hovered,
    }
