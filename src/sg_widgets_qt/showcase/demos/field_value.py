"""Every data type a field value renders, including the empty and sentinel cases.

The port of `apps/site/src/demos/field-value/Demo.tsx`. The status table, the status field's schema
and one Shot with a picture come from the demo context on a worker; the rest of the samples are
invented values in the shapes the API returns.

The second section draws the same samples through the delegate face, which is what a table, a grid
and a grouped list paint their cells with.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.render import FieldTextOptions

from ...images import image_loader
from ...primitives.base import painter_for
from ...theme import theme_of, watch_theme
from ...widgets.field_value import (
    FieldValue,
    FieldValueOptions,
    field_value_size_hint,
    paint_field_value,
)
from ...widgets.state_line import StateLine
from ...workers import default_pool
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: The type name beside each value, and the room a row takes.
TYPE_TEXT = 12
ROW_PAD_Y = 8
ROW_PAD_X = 12
LABEL_WIDTH = 160

#: The status field the demo reads its display values from.
STATUS_FIELD = "sg_status_list"


def samples(shot: dict, image: str | None) -> list[tuple[str, str, Any, dict]]:
    """Every data type, as `(label, data_type, value, keywords)`."""
    return [
        ("text", "text", "Plate delivered.\nSecond pass pending.", {}),
        ("list", "list", "Type A", {}),
        ("number", "number", 1001, {}),
        ("float", "float", "1.777778", {}),
        ("float, precision 2", "float", "1.777778", {"precision": 2}),
        ("currency", "currency", 12500, {}),
        ("currency, euro", "currency", 12500, {"currency_symbol": "€"}),
        ("percent", "percent", 50, {}),
        ("duration", "duration", 480, {}),
        ("duration, in days", "duration", 480, {"hours_per_day": 8}),
        ("timecode", "timecode", 3600000, {}),
        ("date", "date", "2026-09-02", {}),
        ("date_time", "date_time", "2026-09-02T15:58:21Z", {}),
        ("checkbox", "checkbox", True, {}),
        ("checkbox", "checkbox", False, {}),
        ("status_list", "status_list", "ip", {}),
        ("entity", "entity", shot, {}),
        (
            "multi_entity",
            "multi_entity",
            [
                {"type": "Asset", "id": 1226, "name": "charAda"},
                {"type": "Asset", "id": 1227, "name": "charBabbage"},
            ],
            {},
        ),
        ("image", "image", image, {}),
        (
            "url, uploaded",
            "url",
            {
                "url": "https://s3.example.com/9f2/sh010_0010_comp_v001.mov?X-Amz-Expires=900",
                "name": "sh010_0010_comp_v001.mov",
                "content_type": "video/quicktime",
                "link_type": "upload",
                "type": "Attachment",
                "id": 1430,
            },
            {},
        ),
        (
            "url, local",
            "url",
            {
                "link_type": "local",
                "name": "plate.exr",
                "local_path_mac": "/Volumes/shows/sh010/plate.exr",
            },
            {},
        ),
        ("entity_type", "entity_type", "Sequence", {}),
        ("uuid", "uuid", "8f14e45f-ea0e-4f29-9a2e-1c0d3a5b7e91", {}),
        ("color", "color", "253,94,99", {}),
        ("color, sentinel", "color", "pipeline_step", {}),
        ("pivot_column", "pivot_column", None, {}),
        ("text, unset", "text", None, {}),
    ]


class _TypeName(QtWidgets.QWidget):
    """The data type in the mono family, which is what each row is named by."""

    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        watch_theme(self, lambda _theme: self.update())

    def _font(self) -> QtGui.QFont:
        return theme_of(self).font(TYPE_TEXT, mono=True)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(LABEL_WIDTH, metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setFont(self._font())
        painter.setPen(theme_of(self).color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop),
            self._text,
        )
        painter.end()


class _DelegateList(QtWidgets.QWidget):
    """The same samples drawn by `paint_field_value`, with no widget per value."""

    def __init__(
        self,
        rows: list[tuple[str, str, Any, dict]],
        statuses: dict,
        field: Any,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("field-value-delegate")
        self._rows = rows
        self._statuses = statuses
        self._field = field
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)
        watch_theme(self, lambda _theme: self.update())

    def _options(self, extra: dict | None = None) -> FieldValueOptions:
        """The same keywords the widget above takes, as the delegate face's options."""
        named = extra or {}
        text = FieldTextOptions(
            hours_per_day=named.get("hours_per_day"),
            decimals=named.get("precision"),
            currency_symbol=named.get("currency_symbol"),
        )
        return FieldValueOptions(
            theme=theme_of(self),
            field=self._field,
            statuses=self._statuses,
            text=text,
            on_ready=self.update,
        )

    def _row_height(self, row: tuple[str, str, Any, dict]) -> int:
        hint = field_value_size_hint(row[2], row[1], self._options(row[3]))
        return hint.height() + 2 * ROW_PAD_Y

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, sum(self._row_height(row) for row in self._rows))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        theme = theme_of(self)
        font = theme.font(TYPE_TEXT, mono=True)
        top = 0
        for row in self._rows:
            height = self._row_height(row)
            painter.setFont(font)
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                QtCore.QRect(0, top, LABEL_WIDTH, height),
                int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                row[0],
            )
            left = LABEL_WIDTH + ROW_PAD_X
            paint_field_value(
                painter,
                QtCore.QRect(left, top, max(0, self.width() - left), height),
                row[2],
                row[1],
                self._options(row[3]),
            )
            top += height
            painter.fillRect(
                QtCore.QRect(0, top - 1, self.width(), 1), theme.color("border")
            )
        painter.end()


class FieldValueDemo(QtWidgets.QWidget):
    """Every data type as a widget, then the same values through the delegate face."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("field-value-demo")
        self._context = context
        self._values: list[FieldValue] = []
        self._read_done = False

        self._body = lay.column(self)
        self._state = StateLine(state="empty", label="Loading the site…", pad="none", parent=self)
        self._state.setObjectName("demo-state")
        self._body.addWidget(self._state)
        default_pool().submit(self._read, on_result=self._answered, on_error=self._failed)

    def demo_ready(self) -> bool:
        """True once the read has settled and every picture it named has landed."""
        return self._read_done and image_loader().pending == 0

    def set_size(self, size: str) -> None:
        """The value has no size of its own: a collection's density is what moves it."""

    # --- the read ---

    def _read(self) -> tuple[dict, Any, dict, str | None]:
        client = self._context.client
        table = {record.code: record for record in client.statuses()}
        fields = client.fields("Version")
        found = client.search(
            "Shot", SearchOptions(fields=["code", "image"], page={"size": 1})
        )
        row = found.data[0] if found.data else None
        shot = {
            "type": "Shot",
            "id": row.id if row is not None else 0,
            "name": str(row.values.get("code") or "") if row is not None else "",
        }
        image = row.values.get("image") if row is not None else None
        return table, fields.get(STATUS_FIELD), shot, image if isinstance(image, str) else None

    def _answered(self, answer: Any) -> None:
        if not lay.alive(self):
            return
        table, field, shot, image = answer
        rows = samples(shot, image)
        self._state.setParent(None)
        self._body.addWidget(lay.section("Every data type", self._table(rows, table, field), parent=self))
        self._body.addWidget(
            lay.section(
                "Drawn by a delegate",
                _DelegateList(rows, table, field, self),
                parent=self,
            )
        )
        self._read_done = True

    def _failed(self, error: BaseException) -> None:
        if not lay.alive(self):
            return
        self._state.apply_state("error", message=str(error))
        self._read_done = True

    # --- the table ---

    def _table(self, rows: list, statuses: dict, field: Any) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("field-value-table")
        grid = QtWidgets.QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(ROW_PAD_X)
        grid.setVerticalSpacing(ROW_PAD_Y)
        grid.setColumnStretch(1, 1)
        for index, (label, data_type, value, extra) in enumerate(rows):
            grid.addWidget(_TypeName(label, holder), index, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            made = FieldValue(
                value=value,
                data_type=data_type,
                field=field,
                statuses=statuses,
                context=self._context.context,
                parent=holder,
                **extra,
            )
            self._values.append(made)
            grid.addWidget(made, index, 1, QtCore.Qt.AlignmentFlag.AlignTop)
        return holder


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FieldValueDemo(context, parent)
