"""The status badge in every variant, colour, size and icon kind.

The port of `apps/site/src/demos/status-badge/Demo.tsx`. The statuses and the Version status field
are read through the demo context on a worker; everything under them is built from what core
bundles, so the shipped statuses and the 94 shipped icons draw with no site at all.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import HtmlIcon, ImageMapIcon, StatusRecord, parse_bg_color
from sg_widgets_core.status_icons import NATIVE_STATUSES, STOCK_ICON_KEYS

from ...primitives.label import Label
from ...theme import theme_of, watch_theme
from ...widgets.state_line import StateLine
from ...widgets.status_badge import StatusBadge
from ...widgets.status_glyph import StatusGlyph
from ...workers import default_pool
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: The statuses the cross may take from.
REMOVABLE = ("ip", "apr", "hld")

#: A stock icon the package does not bundle: it draws only from a site's own sprite.
CANCELLED = StatusRecord(
    id=900,
    code="cncl",
    name="Cancelled",
    bg_color=None,
    icon=ImageMapIcon(image_map_key="icon_x_thin_white"),
)

#: No site is reachable from a demo, so this one stands in for the site serving the sprite.
DEMO_SITE = "https://demo.example.com"

#: The field the labels fall back to.
STATUS_FIELD = "sg_status_list"

#: The type whose status field the demo reads.
STATUS_TYPE = "Version"

#: The box the bare glyph is shown on, one step of the control ladder.
GLYPH_BOX = 32


def _native_record(status: Any, index: int) -> StatusRecord:
    """A shipped status as `GET /entity/statuses` returns it. `act` is the one with an html icon."""
    icon = (
        ImageMapIcon(image_map_key=status.image_map_key)
        if status.image_map_key
        else HtmlIcon(html=status.name)
    )
    return StatusRecord(id=index, code=status.code, name=status.name, bg_color=None, icon=icon)


NATIVE_RECORDS = tuple(_native_record(s, i) for i, s in enumerate(NATIVE_STATUSES))


class StatusBadgeDemo(QtWidgets.QWidget):
    """The badge across its variants, over the site's own statuses and the shipped ones."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("status-badge-demo")
        self._context = context
        self._statuses: dict[str, StatusRecord] = {}
        self._field: FieldSchema | None = None
        self._badges: list[StatusBadge] = []
        self._removed: list[str] = []
        #: True once the first read has answered or failed. The stage polls it.
        self.demo_ready = False

        self._body = lay.column(self)
        self._state = StateLine(state="empty", label="Loading statuses…", pad="none", parent=self)
        self._state.setObjectName("demo-state")
        self._body.addWidget(self._state)
        self._body.addWidget(self._offline_sections())

        default_pool().submit(self._read, on_result=self._answered, on_error=self._failed)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds, where the example does not name its own."""
        for badge in self._badges:
            badge.set_size(size)

    # --- the read ---

    def _read(self) -> tuple[list, dict]:
        client = self._context.client
        return client.statuses(), client.fields(STATUS_TYPE)

    def _answered(self, answer: Any) -> None:
        if not lay.alive(self):
            return
        rows, fields = answer
        self._statuses = {}
        for status in rows or []:
            self._statuses.setdefault(status.code, status)
        self._field = (fields or {}).get(STATUS_FIELD)
        self._state.setParent(None)
        self._body.insertWidget(0, self._site_sections())
        self.demo_ready = True

    def _failed(self, error: BaseException) -> None:
        if not lay.alive(self):
            return
        self._state.apply_state("error", message=str(error))
        self.demo_ready = True

    # --- what the site answered ---

    def _badge(self, code: str, **kwargs: Any) -> StatusBadge:
        badge = StatusBadge(
            code=code,
            status=self._statuses.get(code),
            field=self._field,
            site_url=self._context.site_url,
            parent=self,
            **kwargs,
        )
        if "size" not in kwargs:
            self._badges.append(badge)
        return badge

    def _site_sections(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)
        for made in (
            self._sizes(),
            self._variants(),
            self._colours(),
            self._bare_glyphs(),
            self._removable(),
            self._labels(),
            self._icons(),
            self._unknown(),
            self._site_statuses(),
        ):
            column.addWidget(made)
        return holder

    def _sizes(self) -> QtWidgets.QWidget:
        return lay.section(
            "Sizes",
            lay.row(*(self._badge("apr", size=step) for step in ("xs", "sm", "md", "lg"))),
            parent=self,
        )

    def _variants(self) -> QtWidgets.QWidget:
        return lay.section(
            "Variants",
            lay.row(*(self._badge("ip", variant=name) for name in ("both", "icon", "text", "glyph"))),
            parent=self,
        )

    def _colours(self) -> QtWidgets.QWidget:
        codes = ("apr", "ip", "hld", "omt")
        section = lay.section(
            "Neutral, then coloured",
            lay.flow(*(self._badge(code) for code in codes)),
            lay.flow(*(self._badge(code, color=True) for code in codes)),
            parent=self,
        )
        section.setObjectName("case-color")
        return section

    def _bare_glyphs(self) -> QtWidgets.QWidget:
        section = lay.section(
            "The bare glyph on the muted ground, and on its own colour",
            lay.row(self._glyph_tile("muted"), self._glyph_tile("color")),
            parent=self,
        )
        section.setObjectName("case-glyph")
        return section

    def _glyph_tile(self, ground: str) -> QtWidgets.QWidget:
        status = self._statuses.get("apr")
        on_color = ground == "color"
        tile = _Tile(status if on_color else None, self)
        tile.setObjectName("glyph-" + ground)
        box = QtWidgets.QHBoxLayout(tile)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        glyph = StatusGlyph(
            status=status,
            site_url=self._context.site_url,
            fallback=True,
            on_color=on_color,
            parent=tile,
        )
        box.addWidget(glyph, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        return tile

    def _removable(self) -> QtWidgets.QWidget:
        holder = lay.flow(parent=self)
        self._fill_removable(holder)
        section = lay.section(
            "Removable, with the cross inside the pill", holder, parent=self
        )
        section.setObjectName("case-removable")
        self._removable_holder = holder
        return section

    def _fill_removable(self, holder: QtWidgets.QWidget) -> None:
        layout = holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        shown = [code for code in REMOVABLE if code not in self._removed]
        for code in shown:
            badge = self._badge(code, color=True, removable=True)
            badge.removed.connect(self._drop)
            layout.addWidget(badge)
        layout.addWidget(self._badge("rev", color=True, variant="icon", removable=True))
        if not shown:
            back = chrome.button(
                "Put them back", variant="link", size="sm", parent=holder, on_click=self._restore
            )
            back.setObjectName("put-them-back")
            layout.addWidget(back)
        holder.updateGeometry()

    def _drop(self, code: str) -> None:
        if code not in self._removed:
            self._removed.append(code)
        self._fill_removable(self._removable_holder)

    def _restore(self) -> None:
        self._removed.clear()
        self._fill_removable(self._removable_holder)

    def _labels(self) -> QtWidgets.QWidget:
        section = lay.section(
            "Name, and the code instead",
            lay.row(self._badge("rev"), self._badge("rev", label="code")),
            parent=self,
        )
        section.setObjectName("case-label")
        return section

    def _icons(self) -> QtWidgets.QWidget:
        section = lay.section(
            "Uploaded icon, and an html icon",
            lay.row(self._badge("custom"), self._badge("act")),
            parent=self,
        )
        section.setObjectName("case-icons")
        return section

    def _unknown(self) -> QtWidgets.QWidget:
        plain = StatusBadge(code="fin", field=self._field, parent=self)
        unknown = StatusBadge(code="zz_retired", parent=self)
        self._badges.extend((plain, unknown))
        section = lay.section(
            "Label from the schema, and an unknown code", lay.row(plain, unknown), parent=self
        )
        section.setObjectName("case-unknown")
        return section

    def _site_statuses(self) -> QtWidgets.QWidget:
        ordered = sorted(self._statuses.values(), key=lambda s: s.name)
        section = lay.section(
            "This site's statuses, custom ones included",
            lay.flow(*(self._badge(status.code, size="sm") for status in ordered)),
            parent=self,
        )
        section.setObjectName("case-site")
        return section

    # --- what core bundles ---

    def _offline_sections(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)

        shipped = lay.section(
            "The shipped statuses",
            lay.flow(
                *(
                    StatusBadge(code=s.code, status=s, size="sm", parent=self)
                    for s in NATIVE_RECORDS
                )
            ),
            parent=self,
        )
        shipped.setObjectName("case-native")
        column.addWidget(shipped)

        stock = lay.section(
            "The shipped icons",
            lay.flow(*(_stock_badge(key, self) for key in STOCK_ICON_KEYS)),
            parent=self,
        )
        stock.setObjectName("case-stock")
        column.addWidget(stock)

        sprite = lay.section(
            "A sprite cell outside the status set, without and with a site",
            lay.row(
                StatusBadge(code=CANCELLED.code, status=CANCELLED, parent=self),
                StatusBadge(
                    code=CANCELLED.code, status=CANCELLED, site_url=DEMO_SITE, parent=self
                ),
                Label("a site that answers serves the cell; one that does not takes the dot", muted=True, parent=self),
            ),
            parent=self,
        )
        sprite.setObjectName("case-sprite")
        column.addWidget(sprite)
        return holder


class _Tile(QtWidgets.QWidget):
    """The square a bare glyph is shown on: `muted`, or the status's own colour."""

    def __init__(self, status: StatusRecord | None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._rgb = parse_bg_color(status.bg_color) if status is not None else None
        self.setFixedSize(GLYPH_BOX, GLYPH_BOX)
        watch_theme(self, lambda _theme: self.update())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        # Status colour is data, not a token, so it is applied at paint time (design rule 1).
        ground = (
            QtGui.QColor(self._rgb.r, self._rgb.g, self._rgb.b)
            if self._rgb is not None
            else theme.color("muted")
        )
        painter.setBrush(ground)
        radius = float(theme.radius_px("md"))
        painter.drawRoundedRect(QtCore.QRectF(self.rect()), radius, radius)
        painter.end()


def _stock_badge(key: str, parent: QtWidgets.QWidget) -> StatusBadge:
    status = StatusRecord(
        id=0, code=key, name=key, bg_color=None, icon=ImageMapIcon(image_map_key=key)
    )
    return StatusBadge(code=key, status=status, variant="icon", size="sm", parent=parent)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return StatusBadgeDemo(context, parent)
