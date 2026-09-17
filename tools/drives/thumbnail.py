"""The thumbnail: the ladder, the aspect, the skeleton, the placeholder and the greyed tile.

    .venv/bin/python tools/qa.py --page thumbnail --drive tools/drives/thumbnail.py
    .venv/bin/python tools/qa.py --page thumbnail --drive tools/drives/thumbnail.py --qt5

The port of `~/dev/sg-widgets/tools/drives/thumbnail-empty.js`, which reads the glyph of every
empty cell off the DOM. Two claims are this port's own and have no upstream: the box holds a
skeleton of its own shape while the read is in flight, since the read runs on a worker rather than
on an `<img>`; and a disabled tile greys its picture as well as dimming it (rule 5).

A url is armed at the discard port, which refuses at once, so the failure path is walked without
the drive waiting on a network.
"""
from __future__ import annotations

from qtpy import QtGui

from sg_widgets_qt.primitives.base import THUMB_SIZE
from sg_widgets_qt.primitives.skeleton import Skeleton
from sg_widgets_qt.widgets.thumbnail import Thumbnail

#: The ladder rule 3 gives a thumbnail: the three list steps, then the card and the detail pane.
LADDER = {"sm": 24, "md": 32, "lg": 40, "xl": 64, "2xl": 96}

#: A url no site answers: the discard port refuses the connection at once.
DEAD_URL = "http://127.0.0.1:9/never.png"

#: How long the failure is given to come back.
FAIL_MS = 4000


def _saturation(image: QtGui.QImage) -> float:
    """The mean saturation of a tile, which is what taking the colour out of it drops."""
    total = count = 0
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            colour = image.pixelColor(x, y)
            if colour.alpha() == 0:
                continue
            total += colour.saturation()
            count += 1
    return total / count if count else 0.0


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    failures: list[str] = []
    seen: dict = {}

    tiles = find(Thumbnail, all=True)
    if not tiles:
        return {"verdict": "FAIL the page drew no thumbnail"}
    seen["tiles"] = len(tiles)

    # --- the ladder and the aspect ---

    steps: dict = {}
    for tile in tiles:
        key = f"{tile.size}-{tile.aspect}"
        if key in steps:
            continue
        wanted_height = LADDER[tile.size]
        wanted_width = wanted_height if tile.aspect == "square" else round(wanted_height * 16 / 9)
        steps[key] = [tile.width(), tile.height()]
        if tile.height() != wanted_height:
            failures.append(f"a {tile.size} tile stands {tile.height()} high, wanted {wanted_height}")
        if tile.width() != wanted_width:
            failures.append(
                f"a {tile.size} {tile.aspect} tile is {tile.width()} wide, wanted {wanted_width}"
            )
        if THUMB_SIZE[tile.size] != wanted_height:
            failures.append(f"the {tile.size} step is {THUMB_SIZE[tile.size]}, wanted {wanted_height}")
    seen["ladder"] = steps
    for step in ("sm", "md", "lg", "xl", "2xl"):
        if not any(key.startswith(step + "-") for key in steps):
            failures.append(f"the page drew no {step} tile to measure")

    # --- the three states the page already carries ---

    states = sorted({tile.state for tile in tiles})
    seen["states"] = states
    for wanted in ("none", "pending", "ready"):
        if wanted not in states:
            failures.append(f"no tile in the {wanted} state on the page")

    # --- the skeleton while a read is in flight ---

    loaded = [tile for tile in tiles if tile.state == "ready" and tile.pixmap is not None]
    if not loaded:
        failures.append("the page drew no tile with a picture to read against")
        return {"verdict": "FAIL " + "; ".join(failures), "seen": seen}

    tile = loaded[0]
    was = tile.src
    with_picture = tile.grab().toImage()
    tile.set_src(DEAD_URL)
    # Read before the loop is spun: a refused connection comes back inside a frame, and the
    # skeleton is what stands in the box for however long the read takes.
    skeleton = tile.findChild(Skeleton)
    seen["loading"] = {
        "loading": tile.loading,
        "skeleton": skeleton is not None and skeleton.isVisible(),
        "shape": [skeleton.width(), skeleton.height()] if skeleton is not None else None,
    }
    if not tile.loading:
        failures.append("the tile is not reading after a fresh url")
    if skeleton is None or not skeleton.isVisible():
        failures.append("no skeleton stands in the box while the read is in flight")
    elif skeleton.size() != tile.rect().size():
        failures.append("the skeleton is not the shape of the box it stands in")

    # --- the placeholder glyph once the url has failed ---

    for _ in range(FAIL_MS // 100):
        if not tile.loading:
            break
        wait(100)
    empty = tile.grab().toImage()
    seen["failed"] = {
        "loading": tile.loading,
        "state": tile.state,
        "pixmap": tile.pixmap is not None,
        "skeleton": skeleton is not None and skeleton.isVisible(),
    }
    if tile.loading:
        failures.append("the read never settled")
    if tile.state != "none":
        failures.append(f"a url that failed reads as {tile.state}, wanted none")
    if tile.pixmap is not None:
        failures.append("a url that failed left a picture behind")
    if empty == with_picture:
        failures.append("the tile draws the same with a picture and without one")

    # --- the greyed tile ---

    tile.set_src(was)
    for _ in range(FAIL_MS // 100):
        if not tile.loading:
            break
        wait(100)
    wait(50)
    lit = _saturation(tile.grab().toImage())
    tile.setEnabled(False)
    wait(50)
    dim = _saturation(tile.grab().toImage())
    seen["disabled"] = {"opacity": tile.disabled_opacity(), "saturation": [round(lit, 1), round(dim, 1)]}
    if tile.disabled_opacity() != 0.5:
        failures.append(f"a disabled tile draws at {tile.disabled_opacity()}, wanted 0.5")
    if dim >= lit:
        failures.append(f"a disabled tile keeps its colour: {round(lit, 1)} became {round(dim, 1)}")
    tile.setEnabled(True)
    wait(50)

    return {
        "verdict": (
            "PASS the ladder is 24/32/40/64/96 at its aspect, the box holds a skeleton of its own "
            "shape while the read is in flight, a url that failed reads as no picture, and a "
            "disabled tile is greyed as well as dimmed"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
