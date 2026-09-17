"""The line box each type step sits in, which is what sets a line's height and a list's pitch.

Upstream a type step carries its leading with it: `text-xs` is 12px on a 16px line, `text-sm` 14
on 20, `text-base` 16 on 24, and every box around a line is measured from that line box rather
than from the font. `QFontMetrics.height()` is the platform's answer instead — 18 for 14px on the
font the palettes name — so a line drawn from it stands 2px short of its upstream twin and a list
of them drifts a row every ten. The ladder is named here so both sides measure the same.

    from ..primitives.type_scale import line_box

    height = line_box(14)  # 20, the upstream `text-sm` line
"""
from __future__ import annotations

__all__ = ["LINE_BOX", "line_box"]

#: The upstream pairs of `text-xs` through `text-4xl`: the step, and the line it sits on.
LINE_BOX: dict[int, int] = {
    12: 16,
    14: 20,
    16: 24,
    18: 28,
    20: 28,
    24: 32,
    30: 36,
    36: 40,
}


def line_box(step: int) -> int:
    """The line a type step sits on. A step the ladder does not name takes 4/3 of itself.

    4/3 is the ratio the named pairs settle on above `text-base`, so a step between two of them
    lands where the next one would rather than on the font's own metrics.
    """
    found = LINE_BOX.get(step)
    if found is not None:
        return found
    return int(round(step * 4 / 3))
