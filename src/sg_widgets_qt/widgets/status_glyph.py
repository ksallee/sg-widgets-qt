"""One status icon: the site's own image, a cell of the stock sprite, or a neutral dot.

Ported from `packages/react/src/registry/sg/components/status-glyph.tsx` over core's
`status_glyph` (010_status_icons).

An `image` icon is a self-contained data URI. An `image_map` icon names a cell of the stock
sprite: the cells of the shipped statuses are bundled in core and draw with no site access, any
other cell is read from the site's own copy of the sprite and so needs a site url, and a key with
neither resolves to a dot. An `html` icon is the label itself, so it draws no picture at all;
`fallback` gives it the dot, which is what a list row wants.

The sprite is read once per site url through `images.ImageLoader`, so a table of a hundred rows
costs one read. It was drawn as dark marks for a light page, so on a dark one its lightness turns
over and its hue stays (`docs/design-rules.md` rule 9); a glyph sitting on the status colour has
its own ground in both schemes and is left alone.

    glyph = StatusGlyph(status=statuses["ip"], fallback=True)
    glyph.set_site_url(context.site_url)
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.status import StatusRecord, status_glyph
from sg_widgets_core.status_icons import STOCK_ICON_CELLS, STOCK_SPRITE_PATH

from ..images import ImageLoader, image_loader, invert_lightness
from ..primitives.base import CHIP_GLYPH, ThemedWidget, painter_for
from ..theme import Theme, with_alpha

__all__ = ["DOT_SIZE", "GLYPH_KINDS", "StatusGlyph", "StatusGlyphSource"]

#: The dot that stands in for a status with no icon to draw: `size-2` at 40% of `muted_foreground`.
DOT_SIZE = 8
DOT_OPACITY = 0.4

#: What core resolves a status's icon to.
GLYPH_KINDS: tuple[str, ...] = ("none", "html", "image", "cell", "sprite", "dot")


class StatusGlyphSource(QtCore.QObject):
    """What one status draws, and the picture behind it once it has been read.

    The badge, a row and the bare widget all paint through this, so the sprite is read once per
    site url whatever draws it.
    """

    #: The picture landed, or the status changed. A painter repaints on this.
    changed = QtCore.Signal()

    def __init__(
        self,
        status: StatusRecord | None = None,
        site_url: str = "",
        loader: ImageLoader | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader = loader if loader is not None else image_loader()
        self._status: StatusRecord | None = None
        self._site_url = ""
        self._glyph = status_glyph(None, None)
        self._pixmap: QtGui.QPixmap | None = None
        self._failed = False
        self._url = ""
        self.set_status(status, site_url)

    # --- what it draws ---

    @property
    def status(self) -> StatusRecord | None:
        return self._status

    @property
    def site_url(self) -> str:
        return self._site_url

    @property
    def kind(self) -> str:
        """One of `GLYPH_KINDS`."""
        return self._glyph.kind

    @property
    def image_map_key(self) -> str:
        """The stock key this glyph names, or an empty string."""
        return getattr(self._glyph, "image_map_key", "") or ""

    @property
    def html(self) -> str:
        """The label an `html` icon carries, which replaces the text rather than preceding it."""
        return getattr(self._glyph, "html", "") or ""

    @property
    def pixmap(self) -> QtGui.QPixmap | None:
        """The picture, once it is in memory."""
        return self._pixmap

    @property
    def cell(self) -> QtCore.QRect | None:
        """The rectangle of the sprite this glyph is, for a sprite-backed one."""
        # A bundled cell carries its own rectangle; a sprite-backed one names a key, and the
        # rectangle for that key is the stylesheet rule core read (probe 010).
        cell = getattr(self._glyph, "cell", None) or STOCK_ICON_CELLS.get(self.image_map_key)
        if cell is None:
            return None
        return QtCore.QRect(cell.x, cell.y, cell.w, cell.h)

    def natural_size(self, fallback: int) -> QtCore.QSize:
        """The size this glyph draws at when nothing constrains it."""
        if self.kind in ("cell", "sprite"):
            cell = self.cell
            if cell is not None:
                return cell.size()
        if self.kind == "dot" or (self.kind in ("none", "html") and self._pixmap is None):
            return QtCore.QSize(DOT_SIZE, DOT_SIZE)
        return QtCore.QSize(fallback, fallback)

    def draws(self, fallback: bool = False) -> bool:
        """True when there is something to draw: a picture, a cell, or the dot."""
        if self.kind in ("image", "cell", "sprite"):
            return True
        return self.kind == "dot" or fallback

    # --- the status ---

    def set_status(self, status: StatusRecord | None, site_url: str | None = None) -> None:
        """Resolve a status's glyph and read whatever picture it needs."""
        if site_url is not None:
            self._site_url = str(site_url or "")
        self._status = status
        self._glyph = status_glyph(status, self._site_url or None)
        self._pixmap = None
        self._failed = False
        self._url = self._source_url()
        if self._url:
            self._loader.load(self._url, self._landed)
        self.changed.emit()

    def set_site_url(self, site_url: str) -> None:
        self.set_status(self._status, site_url)

    def _source_url(self) -> str:
        """The url behind this glyph. A sprite cell is the one sprite the site serves."""
        kind = self.kind
        if kind in ("image", "cell"):
            return getattr(self._glyph, "src", "") or ""
        if kind == "sprite":
            style = getattr(self._glyph, "style", {}) or {}
            url = str(style.get("backgroundImage", ""))
            if url.startswith("url(") and url.endswith(")"):
                return url[4:-1]
            return (self._site_url or "").rstrip("/") + STOCK_SPRITE_PATH
        return ""

    def _landed(self, pixmap: QtGui.QPixmap | None) -> None:
        self._pixmap = pixmap
        self._failed = pixmap is None
        self.changed.emit()

    # --- painting ---

    def paint(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        theme: Theme,
        on_color: bool = False,
        fallback: bool = False,
    ) -> None:
        """Draw the glyph inside `rect`, centred and never scaled up past its own size."""
        kind = self.kind
        picture = kind in ("image", "cell", "sprite")
        if picture and self._pixmap is not None and not self._pixmap.isNull():
            self._paint_picture(painter, rect, theme, on_color)
            return
        # A picture the site did not serve leaves a slot where a mark belongs, so it takes the dot
        # rather than nothing. A read still in flight draws neither.
        if kind == "dot" or fallback or (picture and self._failed):
            self._paint_dot(painter, rect, theme)

    def _paint_picture(
        self, painter: QtGui.QPainter, rect: QtCore.QRect, theme: Theme, on_color: bool
    ) -> None:
        source = self._pixmap
        assert source is not None
        cell = self.cell
        if self.kind == "sprite" and cell is not None:
            source = source.copy(cell)
        if theme.dark and not on_color and self.kind in ("cell", "sprite"):
            source = invert_lightness(source)
        box = QtCore.QRect(QtCore.QPoint(0, 0), source.size().scaled(
            rect.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
        ))
        # A cell carries its own size and is drawn at it, never scaled up, since the sprite was
        # authored at that size. An uploaded `image` is sized by the caller's box instead, which
        # is what `<img class="size-4">` does upstream: the site's own icon is any size at all,
        # and a 1px one still has to read as the badge's glyph.
        if self.kind in ("cell", "sprite") and source.width() <= rect.width() and source.height() <= rect.height():
            box = QtCore.QRect(QtCore.QPoint(0, 0), source.size())
        box.moveCenter(rect.center())
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(box, source)
        painter.restore()

    def _paint_dot(self, painter: QtGui.QPainter, rect: QtCore.QRect, theme: Theme) -> None:
        side = min(DOT_SIZE, rect.width(), rect.height())
        if side <= 0:
            return
        box = QtCore.QRect(0, 0, side, side)
        box.moveCenter(rect.center())
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(theme.muted_foreground, DOT_OPACITY))
        painter.drawEllipse(box)
        painter.restore()


class StatusGlyph(ThemedWidget):
    """One status icon on its own, at the size the caller draws it."""

    #: The picture landed, or there was none to land.
    loaded = QtCore.Signal()

    def __init__(
        self,
        status: StatusRecord | None = None,
        site_url: str = "",
        fallback: bool = False,
        on_color: bool = False,
        size: str = "md",
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("status-glyph")
        self._fallback = bool(fallback)
        self._on_color = bool(on_color)
        self.set_size_step(size if size in CHIP_GLYPH else "md")
        self._source = StatusGlyphSource(status, site_url, loader=loader, parent=self)
        self._source.changed.connect(self._on_source)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    # --- props ---

    @property
    def source(self) -> StatusGlyphSource:
        """What this glyph resolved to, which a badge paints through."""
        return self._source

    @property
    def status(self) -> StatusRecord | None:
        return self._source.status

    def set_status(self, value: StatusRecord | None) -> None:
        self._source.set_status(value)

    @property
    def site_url(self) -> str:
        return self._source.site_url

    def set_site_url(self, value: str) -> None:
        self._source.set_site_url(value)

    @property
    def fallback(self) -> bool:
        """Draw the dot for a status that names no icon."""
        return self._fallback

    def set_fallback(self, value: bool) -> None:
        self._fallback = bool(value)
        self.updateGeometry()
        self.update()

    @property
    def on_color(self) -> bool:
        """The glyph sits on the status colour, so the sprite is left as it is."""
        return self._on_color

    def set_on_color(self, value: bool) -> None:
        self._on_color = bool(value)
        self.update()

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in CHIP_GLYPH else "md")
        self.updateGeometry()
        self.update()

    # --- geometry ---

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        if not self._source.draws(self._fallback):
            return QtCore.QSize(0, 0)
        return self._source.natural_size(CHIP_GLYPH[self.size_step])

    def _on_source(self) -> None:
        self.updateGeometry()
        self.update()
        self.loaded.emit()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        self._source.paint(painter, self.rect(), self.theme, self._on_color, self._fallback)
        painter.end()
