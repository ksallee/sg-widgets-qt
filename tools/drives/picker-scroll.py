"""The popup list of a picker: its height, its overlay scrollbar, and a load-more page.

The port of `~/dev/sg-widgets/tools/drives/picker-arrow-scroll.js` read from the list's side
rather than the highlight's, and the answer to what a reader saw: a page landing under the rows
already read used to reset the model, which dropped the view's scroll position and its keyboard
cursor, so the list jumped to the top and the overlay thumb jumped and shrank with it.

    .venv/bin/python tools/qa.py --page entity-multi-picker --drive tools/drives/picker-scroll.py
    .venv/bin/python tools/qa.py --page entity-picker --drive tools/drives/picker-scroll.py --qt5

What it asserts, in the order a reader meets it:

    the list stands at its rows up to `MAX_HEIGHT`, and the popover is sized from that
    the scroll mode is per pixel, so a pixel-drawn thumb and the range agree
    the overlay thumb's top over its span equals `value / (maximum + pageStep)`
    its length over its span equals `pageStep / (maximum + pageStep)`
    a wheel over the list scrolls the list
    Down walks to the load-more row and the highlight stays inside the viewport
    a page lands under the rows already read: the scroll position holds, the cursor takes the
      seat the load-more row was in, and the thumb follows the new range
    the load-more row is drawn once and goes when there is no further page
    the edge fade follows whichever edge has content past it
"""
from __future__ import annotations

import time

from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QWheelEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.list_view import FADE_SIZE, MAX_HEIGHT
from sg_widgets_qt.primitives.scrollbar import overlay_scrollbars_of
from sg_widgets_qt.widgets.picker_control import PickerControl

#: The thumb may sit this far from where the real scrollbar says it should, in parts of one.
THUMB_TOLERANCE = 0.01


def bar_of(control: PickerControl):
    return control.list_surface().verticalScrollBar()


def snap(control: PickerControl) -> dict:
    """What the list, its scrollbar and its overlay read right now."""
    surface = control.list_surface()
    bar = surface.verticalScrollBar()
    pair = overlay_scrollbars_of(surface)
    overlay = pair[0] if pair else None
    handle = overlay.handle_rect() if overlay is not None else None
    span = overlay.height() if overlay is not None else 0
    total = (bar.maximum() - bar.minimum()) + max(1, bar.pageStep())
    return {
        "rows": surface.row_count(),
        "load_more": surface.load_more_visible(),
        "highlighted": surface.highlighted(),
        "list_h": surface.height(),
        "content_h": surface.content_height(),
        "viewport_h": surface.viewport().height(),
        "bar": [bar.minimum(), bar.maximum(), bar.pageStep(), bar.value()],
        "scrollable": bar.maximum() > bar.minimum(),
        "thumb": list(handle.getRect()) if handle is not None and not handle.isEmpty() else None,
        "span": span,
        "want_top": round((bar.value() - bar.minimum()) / total, 4),
        "want_length": round(max(1, bar.pageStep()) / total, 4),
        "fade": list(surface.fade_sizes()),
        "popover_h": control.popover().height(),
    }


def check_thumb(state: dict, where: str, note) -> None:
    """The overlay thumb is the real scrollbar, drawn: its top and its length follow it."""
    if not state["scrollable"]:
        if state["thumb"] is not None:
            note("thumb", f"{where}: a list with nothing past its edges still draws a thumb")
        return
    thumb, span = state["thumb"], state["span"]
    if thumb is None or span <= 0:
        note("thumb", f"{where}: the list scrolls and the overlay draws no thumb")
        return
    top, length = thumb[1] / span, thumb[3] / span
    if abs(top - state["want_top"]) > THUMB_TOLERANCE:
        note(
            "thumb",
            f"{where}: the thumb sits at {top:.3f} of the bar where value/(max+page)"
            f" is {state['want_top']}",
        )
    # The handle has a floor, so a very long list draws a longer thumb than the ratio asks for.
    if length + THUMB_TOLERANCE < state["want_length"]:
        note(
            "thumb",
            f"{where}: the thumb is {length:.3f} of the bar where page/(max+page)"
            f" is {state['want_length']}",
        )


def check_height(state: dict, where: str, note) -> None:
    """The list stands at its rows up to the cap, and the popover is sized from it."""
    wanted = min(MAX_HEIGHT, state["content_h"])
    if abs(state["list_h"] - wanted) > 1:
        note("height", f"{where}: the list is {state['list_h']}px tall, wanted {wanted}")
    if state["popover_h"] < state["list_h"]:
        note("height", f"{where}: the popover is shorter than the list it holds")


def check_fade(state: dict, where: str, note) -> None:
    """An edge is faded only where the list has content past it."""
    low, high = state["bar"][0], state["bar"][1]
    value = state["bar"][3]
    top, bottom = state["fade"]
    if (value > low) != (top > 0):
        note("fade", f"{where}: the top fade reads {top} at value {value}")
    if (value < high) != (bottom > 0):
        note("fade", f"{where}: the bottom fade reads {bottom} at value {value} of {high}")
    if top > FADE_SIZE or bottom > FADE_SIZE:
        note("fade", f"{where}: a fade of {top}/{bottom} is past the {FADE_SIZE}px it may take")


def wheel(surface, steps: int = 6, wait=None) -> None:
    """Turn the wheel over the list's own viewport, which is what a reader does."""
    viewport = surface.viewport()
    where = viewport.rect().center()
    for _ in range(steps):
        event = QWheelEvent(
            _pointf(where),
            viewport.mapToGlobal(where),
            QPoint(0, -40),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(viewport, event)
        if wait is not None:
            wait(30)


def _pointf(point):
    maker = getattr(point, "toPointF", None)
    return maker() if maker is not None else point


def settle_rows(control: PickerControl, wait, ms: int = 5000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if control.list_surface().row_count() > 0:
            return True
    return False


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(500)
    failures: list = []

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    paged = None
    for control in find(PickerControl, all=True):
        if control.disabled or control.readonly or control.row_model() is None:
            continue
        control.set_open(True)
        if settle_rows(control, wait) and control.has_more:
            paged = control
            break
        control.set_open(False)
        wait(100)
    if paged is None:
        return {"verdict": f"FAIL {page.data_name}: no picker with a further page to read"}

    surface = paged.list_surface()
    bar = bar_of(paged)
    steps: dict = {}

    if surface.verticalScrollMode() != surface.ScrollMode.ScrollPerPixel:
        note("scroll-mode", "the list scrolls per item, so its range is in rows, not pixels")

    steps["open"] = snap(paged)
    check_height(steps["open"], "open", note)
    check_thumb(steps["open"], "open", note)
    check_fade(steps["open"], "open", note)
    if steps["open"]["load_more"] is not True:
        note("load-more", "a list with a further page draws no load-more row")

    wheel(surface, 6, wait)
    wait(150)
    steps["wheeled"] = snap(paged)
    if steps["open"]["scrollable"] and steps["wheeled"]["bar"][3] <= steps["open"]["bar"][3]:
        note("wheel", "a wheel over the list did not scroll it")
    check_thumb(steps["wheeled"], "wheeled", note)
    check_fade(steps["wheeled"], "wheeled", note)

    caret = paged.caret()
    caret.setFocus()
    for _ in range(surface.row_count() + 2):
        QTest.keyClick(caret, Qt.Key.Key_Down)
        wait(30)
    steps["at_end"] = snap(paged)
    if not surface.is_load_more(surface.highlighted()):
        note("load-more", "Down never reached the load-more row")
    seat = surface.highlighted()
    held_value = bar.value()
    held_rows = surface.row_count()

    QTest.keyClick(caret, Qt.Key.Key_Return)
    grew = False
    end = time.time() + 8
    while time.time() < end:
        wait(60)
        if surface.row_count() > held_rows:
            grew = True
            break
    wait(350)
    steps["after_page"] = snap(paged)
    if not grew:
        note("load-more", "Enter on the load-more row loaded no page")
    check_height(steps["after_page"], "after the page", note)
    check_thumb(steps["after_page"], "after the page", note)
    check_fade(steps["after_page"], "after the page", note)
    # The page lands under the rows already read, so nothing a reader was looking at moves.
    drift = abs(bar.value() - held_value)
    if drift > surface.viewport().height():
        note("load-more", f"the list jumped {drift}px when the page landed")
    if surface.highlighted() != seat:
        note(
            "load-more",
            f"the cursor left seat {seat} for {surface.highlighted()} when the page landed",
        )
    rows = surface.row_count()
    more = [i for i in range(rows) if surface.is_load_more(i)]
    if len(more) > 1:
        note("load-more", f"the load-more row is drawn {len(more)} times")
    if surface.load_more_visible() and more and more[0] != rows - 1:
        note("load-more", f"the load-more row sits at {more[0]} of {rows}, not last")

    paged.set_open(False)
    wait(200)
    return {
        "verdict": (
            f"PASS the popup list on {page.data_name} keeps its place, its thumb and its"
            " fade across a load-more page"
            if not failures
            else "FAIL " + "; ".join(failures[:10])
        ),
        "failures": failures,
        "steps": steps,
        "kept": {"value": [held_value, bar.value()], "seat": [seat, surface.highlighted()]},
    }
