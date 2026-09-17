"""thumbnail: every step of the ladder, both shapes, and each way a picture can be missing.

    .venv/bin/python tools/qa.py --page thumbnail --drive tools/drives/walk/thumbnail.py

A thumbnail is read, not pressed, so the walk reads what each example claims: a picture that
landed, a square against a wide one, the play mark, the glyph a type falls back to, a source that
is still transcoding, one that will never load, and the inert tile. Then the view controls move and
every tile is read again, because a picture dropped on a rebuild is the defect this catches.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, case_widget, popups, set_view, wait_for  # noqa: E402

from sg_widgets_qt.images import image_loader  # noqa: E402
from sg_widgets_qt.widgets.thumbnail import Thumbnail  # noqa: E402

STEPS = ("sm", "md", "lg", "xl", "2xl")


def tiles(root) -> list:
    return list(root.findChildren(Thumbnail)) if root is not None else []


def landed(wait, ms: int = 20000) -> bool:
    return wait_for(lambda: image_loader().pending == 0, wait, ms)


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("thumbnail-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no thumbnail demo"}
    wait_for(lambda: demo.demo_ready(), wait, 25000)
    landed(wait)
    wait(300)

    every = tiles(demo)
    walk.check("the page draws tiles", len(every) >= 12, ">= 12", len(every))

    # --- the ladder -----------------------------------------------------------------------------
    steps = sorted({tile.size for tile in every})
    walk.check(
        "every step of the ladder is on show",
        all(step in steps for step in STEPS),
        list(STEPS),
        steps,
    )
    for step in STEPS:
        at = [tile for tile in every if tile.size == step]
        walk.check(f"the {step} step draws a tile", at, "a tile", len(at))
    widths = {step: max(tile.width() for tile in every if tile.size == step) for step in STEPS}
    walk.check(
        "each step is wider than the one under it",
        all(widths[a] < widths[b] for a, b in zip(STEPS, STEPS[1:])),
        "a rising ladder",
        widths,
    )

    # --- the two shapes ---------------------------------------------------------------------------
    shapes = sorted({tile.aspect for tile in every})
    walk.check("both shapes are on show", len(shapes) >= 2, ">= 2", shapes)
    square = [tile for tile in every if tile.aspect == "square"]
    walk.check("a square tile is drawn", square, "a tile", len(square))
    if square:
        box = square[0]
        walk.check(
            "a square tile is as tall as it is wide",
            abs(box.width() - box.height()) <= 1,
            f"{box.width()} square",
            (box.width(), box.height()),
        )

    # --- the play mark ------------------------------------------------------------------------------
    playable = [tile for tile in every if tile.playable]
    walk.check("the playable tiles are marked", len(playable) >= len(STEPS), f">= {len(STEPS)}", len(playable))

    # --- a picture that landed -----------------------------------------------------------------------
    with_picture = [tile for tile in every if tile.src and tile.pixmap is not None]
    walk.check("a picture the site named landed", with_picture, "a picture", len(with_picture))
    walk.check(
        "no tile is left loading",
        not any(tile.loading for tile in every),
        "nothing loading",
        [tile.alt for tile in every if tile.loading],
    )

    # --- the ways a picture can be missing --------------------------------------------------------------
    empty = tiles(case_widget(page, "empty"))
    walk.check("the empty example draws its tiles", len(empty) >= 8, ">= 8", len(empty))
    walk.check(
        "a tile with no source says so rather than staying blank",
        all(not tile.loading for tile in empty),
        "nothing loading",
        [tile.alt for tile in empty if tile.loading],
    )
    kinds = sorted({tile.entity_type for tile in empty if tile.entity_type})
    walk.check("a type falls back to its own glyph", len(kinds) >= 4, ">= 4 types", kinds)
    # `pending` is a source the site has not transcoded yet; `none` is one that will not load.
    broken = [tile for tile in empty if tile.src and tile.pixmap is None]
    walk.check(
        "a source that will not load ends in a state of its own",
        broken and all(tile.state in ("none", "pending") for tile in broken),
        "none or pending",
        [(tile.src[:24], tile.state) for tile in broken],
    )
    walk.check(
        "the still-transcoding source and the broken one read apart",
        len({tile.state for tile in broken}) == 2,
        "two states",
        sorted({tile.state for tile in broken}),
    )
    inert = [tile for tile in empty if not tile.isEnabled()]
    walk.check("the inert tile is inert", inert, "a tile", len(inert))

    # --- the view controls ----------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("thumbnail-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready(), wait, 25000)
        landed(wait)
        wait(300)
        rebuilt = tiles(again)
        walk.check("header: the tiles came back", len(rebuilt) >= 12, ">= 12", len(rebuilt))
        walk.check(
            "header: the pictures came back with them",
            any(tile.pixmap is not None for tile in rebuilt),
            "a picture",
            sum(1 for tile in rebuilt if tile.pixmap is not None),
        )
        walk.check(
            "header: the ladder still names every step",
            all(step in {tile.size for tile in rebuilt} for step in STEPS),
            list(STEPS),
            sorted({tile.size for tile in rebuilt}),
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS every step of the ladder and both shapes are drawn, the pictures the site named"
        " landed, the play mark is on the playable tiles, each way a picture can be missing ends"
        " in a state of its own, and the tiles come back through a rebuild"
    )
