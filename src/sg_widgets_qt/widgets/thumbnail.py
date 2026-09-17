"""A row's thumbnail.

Ported from `packages/react/src/registry/sg/components/thumbnail.tsx`.

The value of an `image` field is the only state marker there is: nothing means the row never had a
picture, and the `/images/status/transient/` prefix means one is still transcoding, so neither is
tested for truthiness (field_types/image). Having none is the ordinary case and reads as one: the
entity type's own glyph on the muted box, never a broken picture. A url that fails to load reads
the same, because the value is presigned and re-minted on every read, so a stale one expiring is a
normal outcome.

The height comes from the size ladder and the width from the aspect, so the widget never sets a
fixed width of its own. `stretch` turns that around for a tile: the picture fills the width it is
given and the aspect sets the height, which is what the top of a card tile is. While the read is in
flight the box holds a skeleton of its own shape.

    Thumbnail(src=row.values["image"], entity_type="Shot", size="lg", playable=True)
    Thumbnail(src=row.values["image"], stretch=True, radius="none")
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.render import image_state

from ..icons import paint_icon
from ..images import ImageLoader, grayscale, image_loader
from ..primitives.base import THUMB_SIZE, ThemedWidget, fill_round_rect, painter_for
from ..primitives.skeleton import Skeleton
from ..theme import with_alpha
from .entity_glyphs import entity_glyph

__all__ = [
    "THUMBNAIL_ASPECT_VALUES",
    "THUMBNAIL_GLYPH",
    "THUMBNAIL_PLAY_BADGE",
    "THUMBNAIL_PLAY_GLYPH",
    "Thumbnail",
]

#: The two shapes a thumbnail takes. The width follows from the height.
THUMBNAIL_ASPECT_VALUES: tuple[str, ...] = ("16:9", "square")

#: The glyph standing in for a picture, a step under the box it sits in.
THUMBNAIL_GLYPH: dict[str, int] = {"sm": 16, "md": 16, "lg": 20, "xl": 24, "2xl": 32}

#: The play badge is decorative chrome, not control iconography, so it scales with the box.
THUMBNAIL_PLAY_BADGE: dict[str, int] = {"sm": 16, "md": 20, "lg": 24, "xl": 32, "2xl": 40}
THUMBNAIL_PLAY_GLYPH: dict[str, int] = {"sm": 10, "md": 12, "lg": 14, "xl": 16, "2xl": 20}

#: The ground the play badge sits on, so a mark reads over any picture.
PLAY_GROUND = 0.7

#: The glyph a row with no entity type of its own falls back to.
NO_TYPE_GLYPH = "image"

#: The mark a picture still transcoding carries.
PENDING_GLYPH = "hourglass"

#: The corners a stretched picture keeps. A tile clips its own, so its picture squares off.
THUMBNAIL_RADIUS_VALUES: tuple[str, ...] = ("md", "none")


class Thumbnail(ThemedWidget):
    """The picture of one row, at a step of the thumbnail ladder."""

    #: A read settled: True when a picture landed, False when there was none or it failed.
    loaded = QtCore.Signal(bool)

    def __init__(
        self,
        src: str | None = None,
        alt: str = "",
        aspect: str = "16:9",
        size: str = "md",
        entity_type: str | None = None,
        playable: bool = False,
        stretch: bool = False,
        radius: str = "md",
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("thumbnail")
        self._loader = loader if loader is not None else image_loader()
        self._src = src
        self._alt = alt
        self._aspect = aspect if aspect in THUMBNAIL_ASPECT_VALUES else "16:9"
        self._entity_type = entity_type
        self._playable = bool(playable)
        self._stretch = bool(stretch)
        self._radius = radius if radius in THUMBNAIL_RADIUS_VALUES else "md"
        self._pixmap: QtGui.QPixmap | None = None
        self._failed = ""
        self._reading = ""
        self.set_size_step(size if size in THUMB_SIZE else "md")

        self._skeleton = Skeleton(radius="md", parent=self)
        self._skeleton.hide()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self._apply_size()
        self._read()

    # --- props ---

    @property
    def src(self) -> str | None:
        """The image field's value. Presigned and re-minted on every read."""
        return self._src

    def set_src(self, value: str | None) -> None:
        if value == self._src:
            return
        self._src = value
        self._pixmap = None
        self._read()

    @property
    def alt(self) -> str:
        """What the picture is, for the tooltip and the accessible name."""
        return self._alt

    def set_alt(self, value: str) -> None:
        self._alt = value
        self.setAccessibleName(value)
        self.setToolTip(value)

    @property
    def aspect(self) -> str:
        return self._aspect

    def set_aspect(self, value: str) -> None:
        self._aspect = value if value in THUMBNAIL_ASPECT_VALUES else "16:9"
        self._apply_size()

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in THUMB_SIZE else "md")
        self._apply_size()

    @property
    def entity_type(self) -> str | None:
        """The row's type, whose glyph stands in when there is no picture."""
        return self._entity_type

    def set_entity_type(self, value: str | None) -> None:
        self._entity_type = value
        self.update()

    @property
    def playable(self) -> bool:
        """Draw a centred play badge over the picture."""
        return self._playable

    def set_playable(self, value: bool) -> None:
        self._playable = bool(value)
        self.update()

    @property
    def stretch(self) -> bool:
        """Fill the width given and take the height from the aspect, which is what a tile wants."""
        return self._stretch

    def set_stretch(self, value: bool) -> None:
        self._stretch = bool(value)
        self._apply_size()

    @property
    def radius(self) -> str:
        """`md`, or `none` where the surface around the picture owns the corners."""
        return self._radius

    def set_radius(self, value: str) -> None:
        self._radius = value if value in THUMBNAIL_RADIUS_VALUES else "md"
        self.update()

    # --- what it is showing ---

    @property
    def state(self) -> str:
        """`none`, `pending` or `ready`, which is what the box draws."""
        if self._src is not None and self._src == self._failed:
            return "none"
        return image_state(self._src)

    @property
    def loading(self) -> bool:
        """True while the picture is being read."""
        return bool(self._reading)

    @property
    def pixmap(self) -> QtGui.QPixmap | None:
        """The picture, once it has landed."""
        return self._pixmap

    # --- the read ---

    def _read(self) -> None:
        self._reading = ""
        if self.state != "ready" or not self._src:
            self._sync_skeleton()
            self.update()
            return
        url = str(self._src)
        cached = self._loader.pixmap_cached(url)
        if cached is not None or self._loader.has(url):
            self._landed(url, cached)
            return
        self._reading = url
        self._sync_skeleton()
        self._loader.load(url, lambda pixmap, url=url: self._landed(url, pixmap), size=self._box_size())

    def _landed(self, url: str, pixmap: QtGui.QPixmap | None) -> None:
        if url != self._src:
            return
        self._reading = ""
        # The failing url is held rather than a flag, so a fresh one retries without being reset.
        self._failed = "" if pixmap is not None else url
        self._pixmap = pixmap
        self._sync_skeleton()
        self.update()
        self.loaded.emit(pixmap is not None)

    # --- geometry ---

    def _box_size(self) -> QtCore.QSize:
        height = THUMB_SIZE[self.size_step]
        width = height if self._aspect == "square" else int(round(height * 16 / 9))
        return QtCore.QSize(width, height)

    def _apply_size(self) -> None:
        box = self._box_size()
        if self._stretch:
            # A stretched picture takes the width it is given; only its height is fixed.
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
            )
            self.setFixedHeight(self.heightForWidth(max(box.width(), self.width())))
        else:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed
            )
            self.setFixedSize(box)
        self._skeleton.setGeometry(self.rect())
        self.updateGeometry()
        self.update()

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return self._stretch

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        if not self._stretch:
            return self._box_size().height()
        return width if self._aspect == "square" else int(round(width * 9 / 16))

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        box = self._box_size()
        if not self._stretch:
            return box
        width = self.width() if self.width() > 0 else box.width()
        return QtCore.QSize(width, self.heightForWidth(width))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._stretch:
            self.setFixedHeight(self.heightForWidth(self.width()))
        self._skeleton.setGeometry(self.rect())

    def _sync_skeleton(self) -> None:
        self._skeleton.setGeometry(self.rect())
        self._skeleton.setVisible(self.loading)

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            self._skeleton.setEnabled(self.isEnabled())

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self.loading:
            return
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        box = self.rect()
        radius = 0.0 if self._radius == "none" else float(theme.radius_px("md"))
        fill_round_rect(
            painter,
            box,
            radius,
            theme.color("muted"),
            None if self._radius == "none" else theme.color("border"),
        )

        if self._pixmap is not None and not self._pixmap.isNull() and self.state == "ready":
            self._paint_picture(painter, box, radius)
        else:
            self._paint_glyph(painter, box)
        if self._playable:
            self._paint_play(painter, box)
        painter.end()

    def _paint_picture(self, painter: QtGui.QPainter, box: QtCore.QRect, radius: float) -> None:
        picture = self._pixmap
        assert picture is not None
        if not self.isEnabled():
            # A tile that is mostly a picture greys it as well as dimming it (rule 5).
            picture = grayscale(picture)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(box), radius, radius)
        painter.save()
        painter.setClipPath(path)
        scaled = picture.scaled(
            box.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        target = QtCore.QRect(QtCore.QPoint(0, 0), scaled.size())
        target.moveCenter(box.center())
        painter.drawPixmap(target, scaled)
        painter.restore()

    def _paint_glyph(self, painter: QtGui.QPainter, box: QtCore.QRect) -> None:
        side = THUMBNAIL_GLYPH[self.size_step]
        slot = QtCore.QRect(0, 0, side, side)
        slot.moveCenter(box.center())
        if self.state == "pending":
            name = PENDING_GLYPH
        else:
            name = entity_glyph(self._entity_type) if self._entity_type else NO_TYPE_GLYPH
        paint_icon(painter, slot, name, self.theme.color("muted_foreground"))

    def _paint_play(self, painter: QtGui.QPainter, box: QtCore.QRect) -> None:
        theme = self.theme
        side = min(THUMBNAIL_PLAY_BADGE[self.size_step], box.width(), box.height())
        badge = QtCore.QRectF(0, 0, side, side)
        badge.moveCenter(QtCore.QPointF(box.center()))
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.setBrush(with_alpha(theme.background, PLAY_GROUND))
        painter.drawEllipse(badge.adjusted(0.5, 0.5, -0.5, -0.5))

        # Lucide's play is an outline; the badge wants it solid, so the triangle is drawn here.
        glyph = float(THUMBNAIL_PLAY_GLYPH[self.size_step])
        centre = badge.center()
        left = centre.x() - glyph * 0.28
        top = centre.y() - glyph * 0.44
        triangle = QtGui.QPainterPath()
        triangle.moveTo(left, top)
        triangle.lineTo(left + glyph * 0.7, centre.y())
        triangle.lineTo(left, top + glyph * 0.88)
        triangle.closeSubpath()
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("foreground"))
        painter.drawPath(triangle)
        painter.restore()
