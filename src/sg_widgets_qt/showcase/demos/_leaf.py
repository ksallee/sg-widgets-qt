"""Every leaf primitive at once: each variant, each step of each ladder, each state.

`build` returns the one widget the showcase's first page shows under the hello demo, and
`tools/qa.py` screenshots.

    from sg_widgets_qt.showcase.demos._leaf import build
    page.setWidget(build())
"""
from __future__ import annotations

from qtpy import QtCore, QtWidgets

from ...primitives.badge import Badge, Chip
from ...primitives.base import CHIP_HEIGHT
from ...primitives.button import BUTTON_VARIANT_VALUES, Button
from ...primitives.checkbox import Checkbox, Switch, Toggle, ToggleGroup
from ...primitives.input import Input, Textarea
from ...primitives.label import Kbd, Label, Separator
from ...primitives.skeleton import Skeleton

__all__ = ["build"]

#: Between sections inside a card, rule 2.
SECTION_GAP = 12

#: Between items in a row, rule 2.
ROW_GAP = 8

#: Between stacked form fields, rule 2.
FIELD_GAP = 16


def _row(*widgets: QtWidgets.QWidget, spacing: int = ROW_GAP) -> QtWidgets.QWidget:
    holder = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return holder


def _heading(text: str) -> QtWidgets.QWidget:
    holder = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(Label(text))
    layout.addWidget(Separator())
    return holder


def _buttons() -> list[QtWidgets.QWidget]:
    rows: list[QtWidgets.QWidget] = []
    for variant in BUTTON_VARIANT_VALUES:
        rows.append(
            _row(
                Button(variant.title(), variant=variant),
                Button("Add", icon="plus", variant=variant),
                Button("Open", trailing_icon="chevron-down", variant=variant),
                Button(variant.title(), variant=variant, size="sm"),
                Button(variant.title(), variant=variant, size="xs"),
                Button(variant.title(), variant=variant, size="lg"),
                Button(icon="settings", variant=variant, size="icon"),
                Button(icon="settings", variant=variant, size="icon-sm"),
                Button(icon="settings", variant=variant, size="icon-xs"),
                Button(icon="settings", variant=variant, size="icon-lg"),
            )
        )
    busy = Button("Saving", icon="check")
    busy.set_busy(True)
    expanded = Button("Filters", trailing_icon="chevron-down", variant="outline")
    expanded.set_expanded(True)
    disabled = Button("Disabled", icon="trash-2", variant="destructive")
    disabled.setEnabled(False)
    rows.append(_row(busy, expanded, disabled))
    return rows


def _inputs() -> list[QtWidgets.QWidget]:
    rows: list[QtWidgets.QWidget] = []
    for step in ("sm", "md", "lg"):
        field = Input(placeholder=f"Search shots ({step})", size=step)
        field.set_leading_icon("search")
        rows.append(field)
    invalid = Input(placeholder="Needs a value", invalid=True)
    readonly = Input(size="md", readonly=True)
    readonly.setText("Read only")
    rows.append(_row(invalid, readonly))
    area = Textarea(placeholder="A note about this version")
    rows.append(area)
    return rows


def _badges() -> list[QtWidgets.QWidget]:
    rows: list[QtWidgets.QWidget] = []
    for variant in ("default", "secondary", "outline", "destructive"):
        rows.append(
            _row(*(Badge(variant.title(), variant=variant, size=step) for step in CHIP_HEIGHT))
        )
    rows.append(
        _row(*(Badge("Remove", size=step, icon="tag", removable=True) for step in CHIP_HEIGHT))
    )
    rows.append(
        _row(
            *(
                Chip("Anna van der Meer", size=step, icon="user", removable=step != "xs")
                for step in CHIP_HEIGHT
            )
        )
    )
    return rows


def _choices() -> list[QtWidgets.QWidget]:
    partial = Checkbox("Some shots", tri_state=True)
    partial.set_check_state(1)
    checked = Checkbox("Only mine")
    checked.set_checked(True)
    off = Checkbox("Include archived")
    disabled = Checkbox("Locked")
    disabled.setEnabled(False)
    group = ToggleGroup(
        [("list", "List", "list"), ("grid", "Grid", "layout-grid"), ("table", "Table", "table")],
        value="grid",
    )
    return [
        _row(checked, partial, off, disabled),
        _row(Switch(True), Switch(False), Toggle("Bold", icon="type", pressed=True), Toggle("Wrap"), group),
    ]


def _skeletons() -> list[QtWidgets.QWidget]:
    return [
        _row(
            Skeleton(width=40, height=40, round=True),
            Skeleton(width=160, height=14),
            Skeleton(width=80, height=14),
            Skeleton(width=32, height=32, radius="md"),
        ),
        _row(Kbd("Ctrl"), Kbd("K"), Kbd("Esc"), Kbd("Enter"), Label("opens the palette", muted=True)),
    ]


def build(parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """Every leaf primitive, laid out in one column."""
    page = QtWidgets.QWidget(parent)
    page.setObjectName("leaf-gallery")
    column = QtWidgets.QVBoxLayout(page)
    column.setContentsMargins(16, 16, 16, 16)
    column.setSpacing(FIELD_GAP)

    sections = (
        ("Buttons", _buttons()),
        ("Inputs", _inputs()),
        ("Badges and chips", _badges()),
        ("Checkbox, switch and toggle", _choices()),
        ("Skeletons and keys", _skeletons()),
    )
    for title, rows in sections:
        block = QtWidgets.QWidget(page)
        inner = QtWidgets.QVBoxLayout(block)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(SECTION_GAP)
        inner.addWidget(_heading(title))
        for row in rows:
            inner.addWidget(row)
        column.addWidget(block)

    column.addStretch(1)
    page.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
    )
    page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
    return page
