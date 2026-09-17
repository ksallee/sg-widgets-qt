"""A person, as a round avatar.

Ported from `packages/react/src/registry/sg/components/user-avatar.tsx`.

The initials fall out of the name in core (`initials_of`), and so does the hue behind them
(`name_hue`), so every widget that shows one person shows the same two. The avatar never renders
blank: an image that fails to load falls back to the initials, and with no name at all it is still
a muted circle. An API user is a script account rather than a person, so the circle holds a bot
glyph instead of a picture or initials and the tooltip says so.

    UserAvatar(name="Anna van der Meer", image=row.values["image"], color="auto")
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.render import initials_of, name_hue

from ..icons import paint_icon
from ..images import ImageLoader, grayscale, image_loader
from ..primitives.base import THUMB_SIZE, ThemedWidget, painter_for
from ..primitives.skeleton import Skeleton

__all__ = ["AVATAR_GLYPH", "AVATAR_SIZE_VALUES", "AVATAR_TEXT", "COLOR_VALUES", "UserAvatar"]

#: Avatars follow the first three steps of the thumbnail ladder.
AVATAR_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")

#: The initials' type step inside the circle.
AVATAR_TEXT: dict[str, int] = {"sm": 12, "md": 14, "lg": 14}

#: The bot glyph an API user carries.
AVATAR_GLYPH: dict[str, int] = {"sm": 16, "md": 16, "lg": 20}

#: Whether the initials take the hue their name derives.
COLOR_VALUES: tuple[str, ...] = ("auto", "none")

#: The tint behind initials, as saturation and lightness per scheme. A fixed hue from the name at
#: a light and a dark lightness, so one person reads the same under every theme. Like status
#: colour, it is data rather than a token (design rule 1).
TINT_LIGHT = ((0.55, 0.90), (0.55, 0.34))
TINT_DARK = ((0.35, 0.26), (0.55, 0.80))

#: The glyph a script account shows in place of a face.
API_GLYPH = "bot"

#: What a dimmed person keeps of its contrast.
INACTIVE_OPACITY = 0.5


def _grey(colour: QtGui.QColor) -> QtGui.QColor:
    """One colour with its own luminance and no hue, which is what `grayscale` does to a picture."""
    grey = round(0.2126 * colour.red() + 0.7152 * colour.green() + 0.0722 * colour.blue())
    return QtGui.QColor(grey, grey, grey, colour.alpha())


class UserAvatar(ThemedWidget):
    """One person as a round avatar: a picture, initials, or a bot glyph."""

    #: A read settled: True when a picture landed, False when there was none or it failed.
    loaded = QtCore.Signal(bool)

    def __init__(
        self,
        name: str = "",
        image: str | None = None,
        size: str = "md",
        inactive: bool = False,
        color: str = "none",
        api_user: bool = False,
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("user-avatar")
        self._loader = loader if loader is not None else image_loader()
        self._name = name
        self._image = image
        self._inactive = bool(inactive)
        self._color = color if color in COLOR_VALUES else "none"
        self._api_user = bool(api_user)
        self._pixmap: QtGui.QPixmap | None = None
        self._failed = ""
        self._reading = ""
        self.set_size_step(size if size in AVATAR_SIZE_VALUES else "md")

        self._skeleton = Skeleton(round=True, parent=self)
        self._skeleton.hide()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self._apply_size()
        self._apply_tooltip()
        self._read()

    # --- props ---

    @property
    def name(self) -> str:
        """The display name. Drives the initials, the tooltip and the accessible name."""
        return self._name

    def set_name(self, value: str) -> None:
        self._name = value
        self._apply_tooltip()
        self.update()

    @property
    def image(self) -> str | None:
        """The person's image field. Presigned and short-lived (field_types/image)."""
        return self._image

    def set_image(self, value: str | None) -> None:
        if value == self._image:
            return
        self._image = value
        self._pixmap = None
        self._read()

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in AVATAR_SIZE_VALUES else "md")
        self._apply_size()

    @property
    def inactive(self) -> bool:
        """A disabled person: dimmed and desaturated, never hidden."""
        return self._inactive

    def set_inactive(self, value: bool) -> None:
        self._inactive = bool(value)
        self.update()

    @property
    def color(self) -> str:
        """`auto` tints the initials with the hue the name derives."""
        return self._color

    def set_color(self, value: str) -> None:
        self._color = value if value in COLOR_VALUES else "none"
        self.update()

    @property
    def api_user(self) -> bool:
        """A script account rather than a person."""
        return self._api_user

    def set_api_user(self, value: bool) -> None:
        self._api_user = bool(value)
        self._apply_tooltip()
        self._read()

    # --- what it is showing ---

    @property
    def initials(self) -> str:
        """The letters the circle falls back to, from core."""
        return initials_of(self._name)

    @property
    def hue(self) -> int:
        """The hue this name derives, from core."""
        return name_hue(self._name)

    @property
    def loading(self) -> bool:
        """True while the picture is being read."""
        return bool(self._reading)

    @property
    def pixmap(self) -> QtGui.QPixmap | None:
        return self._pixmap

    @property
    def tinted(self) -> bool:
        """True when the initials are drawn on their own hue."""
        return (
            self._color == "auto"
            and not self._api_user
            and self._pixmap is None
            and bool(self.initials)
        )

    # --- the read ---

    def _source(self) -> str:
        if self._api_user or not self._image or self._image == self._failed:
            return ""
        return str(self._image)

    def _read(self) -> None:
        self._reading = ""
        url = self._source()
        if not url:
            self._sync_skeleton()
            self.update()
            return
        cached = self._loader.pixmap_cached(url)
        if cached is not None or self._loader.has(url):
            self._landed(url, cached)
            return
        self._reading = url
        self._sync_skeleton()
        self._loader.load(url, lambda pixmap, url=url: self._landed(url, pixmap), size=self._side())

    def _landed(self, url: str, pixmap: QtGui.QPixmap | None) -> None:
        if url != self._image:
            return
        self._reading = ""
        # The failing url is held rather than a flag, so a fresh one retries without being reset.
        self._failed = "" if pixmap is not None else url
        self._pixmap = pixmap
        self._sync_skeleton()
        self.update()
        self.loaded.emit(pixmap is not None)

    # --- geometry ---

    def _side(self) -> int:
        return THUMB_SIZE[self.size_step]

    def _apply_size(self) -> None:
        side = self._side()
        self.setFixedSize(side, side)
        self._skeleton.setGeometry(self.rect())
        self.updateGeometry()
        self.update()

    def _apply_tooltip(self) -> None:
        text = f"{self._name} (API user)" if self._api_user else self._name
        self.setToolTip(text)
        self.setAccessibleName(text)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        side = self._side()
        return QtCore.QSize(side, side)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._skeleton.setGeometry(self.rect())

    def _sync_skeleton(self) -> None:
        self._skeleton.setGeometry(self.rect())
        self._skeleton.setVisible(self.loading)

    # --- colours ---

    def _tint(self) -> tuple[QtGui.QColor, QtGui.QColor]:
        """The ground and the ink the initials take, from the name's hue."""
        ground, ink = TINT_DARK if self.theme.dark else TINT_LIGHT
        hue = self.hue / 360.0
        return (
            QtGui.QColor.fromHslF(hue, ground[0], ground[1]),
            QtGui.QColor.fromHslF(hue, ink[0], ink[1]),
        )

    def _surface(self) -> tuple[QtGui.QColor, QtGui.QColor]:
        theme = self.theme
        if self._api_user:
            ground, ink = theme.color("secondary"), theme.color("secondary_foreground")
        elif self.tinted:
            ground, ink = self._tint()
        else:
            ground, ink = theme.color("muted"), theme.color("muted_foreground")
        if self._inactive:
            # A dimmed person is desaturated as well as dimmed, the picture and the tint alike
            # (rule 5), so the hue a name derives never survives the row being discarded.
            return _grey(ground), _grey(ink)
        return ground, ink

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self.loading:
            return
        painter = painter_for(self)
        opacity = self.disabled_opacity()
        if self._inactive:
            opacity *= INACTIVE_OPACITY
        painter.setOpacity(opacity)
        theme = self.theme
        box = QtCore.QRect(0, 0, self._side(), self._side())
        box.moveCenter(self.rect().center())
        ground, ink = self._surface()

        circle = QtGui.QPainterPath()
        circle.addEllipse(QtCore.QRectF(box))
        painter.fillPath(circle, ground)

        if self._pixmap is not None and not self._pixmap.isNull():
            self._paint_picture(painter, box, circle)
        elif self._api_user:
            side = AVATAR_GLYPH[self.size_step]
            slot = QtCore.QRect(0, 0, side, side)
            slot.moveCenter(box.center())
            paint_icon(painter, slot, API_GLYPH, ink)
        elif self.initials:
            painter.setFont(theme.font(AVATAR_TEXT[self.size_step], QtGui.QFont.Weight.Medium))
            painter.setPen(ink)
            painter.drawText(box, int(QtCore.Qt.AlignmentFlag.AlignCenter), self.initials)

        # The ring the circle wears, drawn last so a picture never covers it.
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.drawEllipse(QtCore.QRectF(box).adjusted(0.5, 0.5, -0.5, -0.5))
        painter.end()

    def _paint_picture(
        self, painter: QtGui.QPainter, box: QtCore.QRect, circle: QtGui.QPainterPath
    ) -> None:
        picture = self._pixmap
        assert picture is not None
        if self._inactive or not self.isEnabled():
            # A tile that is mostly a picture greys it as well as dimming it (rule 5).
            picture = grayscale(picture)
        painter.save()
        painter.setClipPath(circle)
        scaled = picture.scaled(
            box.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        target = QtCore.QRect(QtCore.QPoint(0, 0), scaled.size())
        target.moveCenter(box.center())
        painter.drawPixmap(target, scaled)
        painter.restore()
