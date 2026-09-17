"""The GUI thread while the cards read: nothing on the page blocks it.

`docs/design-rules.md`: widgets never block the GUI thread. A card given a reference runs its own
search, its schema reads and its status table on a worker, and the picture behind it on the image
pool, so the loop keeps turning from the first frame to the last picture.

    .venv/bin/python tools/qa.py --page entity-card --drive tools/drives/entity-card-thread.py
    .venv/bin/python tools/qa.py --page entity-card --drive tools/drives/entity-card-thread.py --qt5

Two measurements, both with the mock's latency and its real http thumbnails in flight:

    the longest gap between two turns of the loop while the page builds and reads
    the same while a card is handed a reference it has never read

The timer is the one `tools/drives/picker-thread.py` uses, kept here rather than shared so a drive
stays one file the driver can exec.
"""
from __future__ import annotations

import time

from qtpy import QtCore

from sg_widgets_core.filter import EntityRef
from sg_widgets_qt.images import image_loader
from sg_widgets_qt.widgets.entity_card import EntityCard

#: No turn of the loop may take longer than this while the page is reading.
BUDGET_MS = 50.0


class Heartbeat(QtCore.QObject):
    """A zero-interval timer on the GUI thread, timing the gap between two turns of the loop."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.gaps: list[float] = []
        self._last = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.gaps = []
        self._last = time.monotonic()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = time.monotonic()
        self.gaps.append((now - self._last) * 1000.0)
        self._last = now

    @property
    def worst(self) -> float:
        return max(self.gaps) if self.gaps else 0.0


def case_of(card) -> str:
    walk = card.parentWidget()
    for _ in range(8):
        if walk is None:
            return ""
        if walk.objectName().startswith("case-"):
            return walk.objectName()
        walk = walk.parentWidget()
    return ""


def cards(find) -> list:
    return [card for card in find(EntityCard, all=True) if card.isVisible()]


def wait_for(read, wait, ms: int) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(20)
        if read():
            return True
    return False


def drive(page, wait, find, prefs) -> dict:
    failures: list[str] = []

    def note(detail: str) -> None:
        failures.append(f"loop — {detail}")

    # 1. The page built again, so the whole read is inside the measurement.
    stage = page.stages[0] if page.stages else None
    beat = Heartbeat(page)
    beat.start()
    if stage is not None:
        stage.build()
    wait_for(lambda: page.ready, wait, 15000)
    wait_for(lambda: image_loader().pending == 0, wait, 8000)
    wait(600)
    beat.stop()
    building = {"turns": len(beat.gaps), "worst_ms": round(beat.worst, 1), "ready": page.ready}
    if beat.worst > BUDGET_MS:
        note(f"a turn took {beat.worst:.0f}ms while the page was building and reading")
    if len(beat.gaps) < 20:
        note(f"the loop turned {len(beat.gaps)} times, too few to measure")

    # 2. A card handed a reference of its own, with its search, its schema and its picture out.
    picked = [card for card in cards(find) if case_of(card) == "case-reference"]
    held = [card for card in cards(find) if case_of(card) == "case-sizes" and card.model]
    reading: dict = {}
    if picked and held:
        card = picked[0]
        wanted = EntityRef(type=held[0].model.entity.type, id=held[0].model.entity.id)
        beat.start()
        card.set_entity(wanted)
        landed = wait_for(lambda: not card.loading, wait, 12000)
        wait(400)
        beat.stop()
        reading = {
            "turns": len(beat.gaps),
            "worst_ms": round(beat.worst, 1),
            "answered": landed,
            "name": card.name,
        }
        if beat.worst > BUDGET_MS:
            note(f"a turn took {beat.worst:.0f}ms while a card was reading a reference")
        if not landed:
            failures.append("read — the card never answered the reference it was handed")

    return {
        "verdict": (
            f"PASS the GUI thread on {page.data_name} never stalled past {BUDGET_MS:.0f}ms while"
            " the cards read"
            if not failures
            else "FAIL " + "; ".join(failures[:8])
        ),
        "failures": failures,
        "seen": {"building": building, "reading": reading},
    }
