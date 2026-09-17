"""The model roles our list and table delegates read.

A model answers the parts of a row, and the delegate draws them: the label and the runs the
query matched, a code, a sub-label, a right-aligned secondary, the leading picture, and what
the row is. A caller that has a `QAbstractListModel` already need only add the roles it has.

`Roles.PAINTER` carries a callable a cell or a secondary is drawn by, for a value no string
renders: a status badge, a chip, a thumbnail. It is called `painter(painter, rect, option)`.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Literal

from qtpy.QtCore import Qt

__all__ = ["ROW_KIND_VALUES", "RowKind", "Roles"]

#: What a row is. A `load_more` row asks for the next page, a `heading` names a group, and a
#: `separator` is a rule between two groups. The last two take no highlight.
RowKind = Literal["row", "load_more", "heading", "separator"]
ROW_KIND_VALUES: tuple[RowKind, ...] = ("row", "load_more", "heading", "separator")


class Roles(IntEnum):
    """The roles `RowDelegate` and `CellDelegate` read off a model."""

    #: The main label, a string.
    LABEL = int(Qt.ItemDataRole.UserRole) + 1
    #: The label as `[(text, matched), ...]`. A matched run is drawn in DemiBold.
    RUNS = int(Qt.ItemDataRole.UserRole) + 2
    #: The programmatic name beside the label, in the mono family at 12px.
    CODE = int(Qt.ItemDataRole.UserRole) + 3
    #: The muted line under the label.
    SUB_LABEL = int(Qt.ItemDataRole.UserRole) + 4
    #: The right-aligned column, as text.
    SECONDARY = int(Qt.ItemDataRole.UserRole) + 5
    #: The leading picture, a `QPixmap`.
    PIXMAP = int(Qt.ItemDataRole.UserRole) + 6
    #: The initials drawn on a name-derived hue when there is no picture.
    INITIALS = int(Qt.ItemDataRole.UserRole) + 7
    #: A lucide glyph name drawn in the leading slot, or a status colour as `#rrggbb`.
    GLYPH = int(Qt.ItemDataRole.UserRole) + 8
    #: True, False, or None for a row that takes no indicator.
    CHECKED = int(Qt.ItemDataRole.UserRole) + 9
    #: True on a row that is drawn at half opacity and takes no highlight.
    DISABLED = int(Qt.ItemDataRole.UserRole) + 10
    #: One of `ROW_KIND_VALUES`. Anything else reads as `row`.
    KIND = int(Qt.ItemDataRole.UserRole) + 11
    #: The caller's own payload for the row, handed back with `activated`.
    ENTITY = int(Qt.ItemDataRole.UserRole) + 12
    #: `painter(painter, rect, option)`, drawing a value no string renders.
    PAINTER = int(Qt.ItemDataRole.UserRole) + 13
    #: True on a column that sorts, read by `HeaderDelegate`.
    SORTABLE = int(Qt.ItemDataRole.UserRole) + 14
