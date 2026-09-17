"""The shape the ten picker demos are laid out in.

Upstream each demo is a column of sections, one control per row at the pane's full width with its
caption on the line above. The spacings are `docs/design-rules.md` rule 2: 16 between stacked
sections, 8 inside one.

    body = column(self)
    body.addWidget(section("One person", field("One person, clearable", picker), case="single"))
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtWidgets

from .. import chrome

__all__ = ["CAPTION_SIZE", "boxed", "column", "field", "readout", "section"]

#: Between stacked sections, and inside one (rule 2).
SECTION_GAP = 16
INNER_GAP = 8

#: The caption over a control, and the readout under it: the metadata step of rule 6.
CAPTION_SIZE = 12

#: `max-w-80`: narrow enough that the chip fit has something to cut against.
NARROW_WIDTH = 320


def column(parent: QtWidgets.QWidget) -> QtWidgets.QVBoxLayout:
    """The demo's own column: no margins of its own, sections 16 apart."""
    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SECTION_GAP)
    return layout


def field(
    caption: str,
    *widgets: QtWidgets.QWidget,
    name: str | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QWidget:
    """One control at the pane's full width, with its caption on the line above."""
    holder = QtWidgets.QWidget(parent)
    if name is not None:
        holder.setProperty("data_demo", name)
    inner = QtWidgets.QVBoxLayout(holder)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(INNER_GAP)
    if caption:
        inner.addWidget(chrome.TextLine(caption, size=CAPTION_SIZE, parent=holder))
    for widget in widgets:
        widget.setParent(holder)
        inner.addWidget(widget)
    return holder


def section(
    title: str,
    *bodies: QtWidgets.QWidget,
    case: str | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QWidget:
    """One heading over the controls under it."""
    holder = QtWidgets.QWidget(parent)
    if case is not None:
        holder.setProperty("data_demo_case", case)
    inner = QtWidgets.QVBoxLayout(holder)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(INNER_GAP)
    inner.addWidget(chrome.TextLine(title.upper(), size=CAPTION_SIZE, parent=holder))
    for body in bodies:
        body.setParent(holder)
        inner.addWidget(body)
    return holder


def boxed(widget: QtWidgets.QWidget, width: int = NARROW_WIDTH) -> QtWidgets.QWidget:
    """A control held to a narrow box, so the chip fit has something to cut against."""
    holder = QtWidgets.QWidget()
    row = QtWidgets.QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    widget.setParent(holder)
    widget.setMaximumWidth(width)
    row.addWidget(widget)
    row.addStretch(1)
    return holder


def readout(parent: QtWidgets.QWidget | None = None) -> Any:
    """The mono line a demo writes the current value into."""
    line = chrome.TextLine("", size=CAPTION_SIZE, parent=parent)
    line.setProperty("data_demo_readout", True)
    return line


def alive(widget: QtWidgets.QWidget) -> bool:
    """False once Qt has deleted the widget under the Python wrapper a callback still holds."""
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True


def poll_ready(demo: QtWidgets.QWidget, pending: Any, limit_ms: int = 4000) -> QtCore.QTimer:
    """Hold a demo not ready until `pending()` answers False, or the limit runs out."""
    step = 100
    waited = {"ms": 0}
    timer = QtCore.QTimer(demo)
    timer.setInterval(step)

    def tick() -> None:
        waited["ms"] += step
        if not alive(demo) or not pending() or waited["ms"] >= limit_ms:
            timer.stop()
            if alive(demo):
                demo.demo_ready = True

    timer.timeout.connect(tick)
    demo.demo_ready = not pending()
    if not demo.demo_ready:
        timer.start()
    return timer
