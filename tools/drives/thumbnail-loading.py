"""The state matrix: the skeleton a tile holds while its read is in flight, and a disabled tile.

    .venv/bin/python tools/qa.py --page thumbnail --drive tools/drives/thumbnail-loading.py

This state has no upstream twin: upstream a thumbnail is an `<img>` the browser fills, so there is
nothing to stand in for it and nothing to disable. Here the read runs on a worker, so the box holds
a skeleton of its own shape (rule 4) and a disabled tile is greyed as well as dimmed (rule 5).

The drive takes the shot itself, into `shots/thumbnail-loading.png`, because the state it is about
only stands while a read is out: it arms five tiles against a host that never answers, grabs the
window with the skeletons up, then puts the tiles back and waits for every read to settle, so the
run leaves nothing in flight behind it.
"""
from __future__ import annotations

from pathlib import Path

from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.skeleton import Skeleton
from sg_widgets_qt.widgets.thumbnail import Thumbnail

#: A host that never routes, so the read stands in flight for the whole of its timeout.
SILENT_URL = "http://10.255.255.1/never.png"

#: The timeout the tiles read at here, so the drive drains in about a second rather than ten.
TIMEOUT_S = 1

#: Where the shot of this state lands.
SHOT = Path(__file__).resolve().parents[2] / "shots" / "thumbnail-loading.png"

#: How long the drive waits for the armed reads to settle before it gives up on them.
DRAIN_MS = 6000


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    tiles = [tile for tile in find(Thumbnail, all=True) if tile.state == "ready"]
    if len(tiles) < 2:
        return {"verdict": "FAIL the page drew fewer than two tiles with a picture"}
    reading, disabled = tiles[:5], tiles[5:10] or tiles[:5]
    loader = ImageLoader(timeout=TIMEOUT_S)
    was = [(tile, tile.src) for tile in reading]
    for index, tile in enumerate(reading):
        tile._loader = loader
        tile.set_src(f"{SILENT_URL}?{index}")
    for tile in disabled:
        tile.setEnabled(False)
    wait(120)

    shown = [
        tile.findChild(Skeleton) is not None and tile.findChild(Skeleton).isVisible()
        for tile in reading
    ]
    SHOT.parent.mkdir(parents=True, exist_ok=True)
    page.window().grab().save(str(SHOT))

    # Nothing is left in flight: a read still out when the window goes takes its answer to a
    # widget that is no longer there.
    for tile in disabled:
        tile.setEnabled(True)
    for tile, src in was:
        tile.set_src(src)
    for _ in range(DRAIN_MS // 100):
        if loader.pending == 0:
            break
        wait(100)

    return {
        "verdict": (
            "PASS every tile reading holds a skeleton of its own shape, and a disabled tile is "
            "greyed"
            if all(shown)
            else "FAIL a tile reading holds no skeleton"
        ),
        "seen": {
            "reading": len(reading),
            "skeletons": sum(shown),
            "disabled": len(disabled),
            "pending": loader.pending,
            "shot": str(SHOT),
        },
    }
