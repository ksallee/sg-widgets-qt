"""One linked row, as a chip, an inline link or bare text.

Ported from `packages/react/src/registry/sg/components/entity-chip.tsx` onto the chip of
`primitives/badge.py`.

`name` is the target's `cached_display_name` and is filled on every type measured, so a chip needs
no second call (probe 060). A row with no name shows `Type #id`, which is always addressable, in
the monospace treatment the design rules give ids. With no url of its own the chip addresses the
row's own page on the site, `<site>/detail/<Type>/<id>`, which core builds from the context's site
url (entity_types/Project).

    chip = EntityChip(entity=EntityRef("Shot", 862, "sh010_0010"), context=context, removable=True)
    chip.removed.connect(drop)
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.context import SgContext, context_from_client
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.presentation import entity_detail_url

from ..icons import paint_icon
from ..images import ImageLoader, image_loader
from ..primitives.badge import Chip
from ..primitives.base import CHIP_GLYPH, CHIP_HEIGHT, CHIP_TEXT
from ..primitives.hover_card import HoverCard, HoverCardContent
from ..theme import with_alpha
from .entity_glyphs import entity_glyph

__all__ = ["ENTITY_CHIP_VARIANT_VALUES", "EntityChip", "default_preview_builder"]

#: Boxed chip, inline link, or the bare name.
ENTITY_CHIP_VARIANT_VALUES: tuple[str, ...] = ("chip", "link", "text")

#: The keys that activate a chip, and the ones that remove it.
ACTIVATE_KEYS = (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Space)
REMOVE_KEYS = (QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace)

PreviewBuilder = Callable[[EntityRef, "list[str]", "SgContext | None"], QtWidgets.QWidget]


class EntityChip(Chip):
    """One linked row: its glyph or thumbnail, its name, and where it points."""

    #: The chip's own content was pressed.
    clicked = QtCore.Signal()
    #: The cross was pressed. Carries the `EntityRef`.
    removed = QtCore.Signal(object)

    #: A chip measures itself during construction, so what the measure reads has a class default.
    _chip_variant = "chip"
    _entity: EntityRef | None = None
    _href: object = None
    _on_click: Callable[[], None] | None = None

    def __init__(
        self,
        entity: EntityRef | None = None,
        thumbnail: str | None = None,
        variant: str = "chip",
        href: object = None,
        site_url: str = "",
        preview: list[str] | None = None,
        context: SgContext | None = None,
        client: object = None,
        size: str = "md",
        removable: bool = False,
        remove_label: str = "",
        on_click: Callable[[], None] | None = None,
        on_remove: Callable[[EntityRef], None] | None = None,
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self._entity = entity
        self._chip_variant = variant if variant in ENTITY_CHIP_VARIANT_VALUES else "chip"
        self._href = href
        self._site_url = site_url
        self._preview = list(preview or [])
        self._context = context if context is not None else _context_of(client)
        self._thumbnail = thumbnail
        self._remove_label = remove_label
        self._loader = loader if loader is not None else image_loader()
        self._on_click = None
        self._on_remove: Callable[[EntityRef], None] | None = None
        self._preview_builder: PreviewBuilder | None = None
        self._card: HoverCard | None = None
        super().__init__(
            text="",
            variant="secondary",
            size=size if size in CHIP_HEIGHT else "md",
            removable=removable,
            parent=parent,
        )
        self.setObjectName("entity-chip")
        self.set_on_click(on_click)
        self.set_on_remove(on_remove)
        self._refresh()
        self._read_thumbnail()
        self._rebuild_card()

    # --- props ---

    @property
    def entity(self) -> EntityRef | None:
        """Type, id and optional name, as an entity field returns it."""
        return self._entity

    def set_entity(self, value: EntityRef | None) -> None:
        self._entity = value
        self._refresh()
        self._rebuild_card()

    @property
    def thumbnail(self) -> str | None:
        """A picture for the linked row, which replaces the type glyph."""
        return self._thumbnail

    def set_thumbnail(self, value: str | None) -> None:
        if value == self._thumbnail:
            return
        self._thumbnail = value
        self.set_pixmap(None)
        self._read_thumbnail()

    @property
    def variant(self) -> str:
        """`chip`, `link` or `text`."""
        return self._chip_variant

    def set_variant(self, value: str) -> None:
        self._chip_variant = value if value in ENTITY_CHIP_VARIANT_VALUES else "chip"
        self._refresh()

    @property
    def href(self) -> object:
        """A url, a resolver, or None for the row's own page on the site."""
        return self._href

    def set_href(self, value: object) -> None:
        self._href = value
        self._refresh()

    @property
    def site_url(self) -> str:
        """The site the row's own page lives on. Defaults to the context's."""
        return self._site_url or (self._context.site_url if self._context is not None else "")

    def set_site_url(self, value: str) -> None:
        self._site_url = value
        self._refresh()

    @property
    def preview(self) -> list[str]:
        """Field paths the hover card shows. Needs a context."""
        return list(self._preview)

    def set_preview(self, value: list[str] | None) -> None:
        self._preview = list(value or [])
        self._rebuild_card()

    @property
    def context(self) -> SgContext | None:
        """The widget context, for the site url and for the hover card's read."""
        return self._context

    def set_context(self, value: SgContext | None) -> None:
        self._context = value
        self._refresh()
        self._rebuild_card()

    def set_client(self, value: object) -> None:
        """Read through a bare client. One context is built per client and shared."""
        self.set_context(_context_of(value))

    def set_size(self, value: str) -> None:
        super().set_size(value if value in CHIP_HEIGHT else "md")
        self._refresh()

    @property
    def remove_label(self) -> str:
        """The accessible name of the cross."""
        return self._remove_label or f"Remove {self.label}"

    def set_remove_label(self, value: str) -> None:
        self._remove_label = value

    @property
    def on_click(self) -> Callable[[], None] | None:
        """The callable a press calls, beside the `clicked` signal."""
        return self._on_click

    def set_on_click(self, value: Callable[[], None] | None) -> None:
        if self._on_click is not None:
            try:
                self.clicked.disconnect(self._on_click)
            except (RuntimeError, TypeError):
                pass
        self._on_click = value
        if value is not None:
            self.clicked.connect(value)
        self._refresh()

    @property
    def on_remove(self) -> Callable[[EntityRef], None] | None:
        """The callable the cross calls, beside the `removed` signal."""
        return self._on_remove

    def set_on_remove(self, value: Callable[[EntityRef], None] | None) -> None:
        if self._on_remove is not None:
            try:
                self.removed.disconnect(self._on_remove)
            except (RuntimeError, TypeError):
                pass
        self._on_remove = value
        if value is not None:
            self.removed.connect(value)

    def set_preview_builder(self, builder: PreviewBuilder | None) -> None:
        """What the hover card holds.

        Called as `builder(entity, preview, context)` and returns the widget the card shows.
        None restores the default, an EntityCard on the row the chip points at.
        """
        self._preview_builder = builder
        self._rebuild_card()

    # --- what it resolved to ---

    @property
    def named(self) -> bool:
        """True when the entity carried a display name."""
        return bool(self._entity is not None and self._entity.name)

    @property
    def label(self) -> str:
        """The name, or `Type #id`, which is always addressable."""
        if self._entity is None:
            return ""
        if self.named:
            return str(self._entity.name)
        return f"{self._entity.type} #{self._entity.id}"

    @property
    def url(self) -> str:
        """Where the chip points, or an empty string for an inert one."""
        if self._entity is None or self._chip_variant == "text":
            return ""
        if callable(self._href):
            return str(self._href(self._entity) or "")
        if isinstance(self._href, str):
            return self._href
        return entity_detail_url(self.site_url, self._entity) or ""

    @property
    def interactive(self) -> bool:
        """True when a press does something: a url to follow or a callable to run."""
        return bool(self.url) or self._on_click is not None

    @property
    def hover_card(self) -> HoverCard | None:
        """The card the chip previews through, while there is one."""
        return self._card

    @property
    def boxed(self) -> bool:
        """True for the chip variant, the one with a surface of its own."""
        return self._chip_variant == "chip"

    # --- the thumbnail ---

    def _read_thumbnail(self) -> None:
        if not self._thumbnail:
            return
        url = str(self._thumbnail)
        side = CHIP_GLYPH[self.size_step]
        self._loader.load(
            url,
            lambda pixmap, url=url: self._thumbnail_landed(url, pixmap),
            size=QtCore.QSize(side, side),
        )

    def _thumbnail_landed(self, url: str, pixmap: QtGui.QPixmap | None) -> None:
        if url != self._thumbnail:
            return
        self.set_pixmap(pixmap)

    # --- the hover card ---

    def _rebuild_card(self) -> None:
        if self._card is not None:
            self._card.close()
            self._card.deleteLater()
            self._card = None
        if not self._preview or self._entity is None:
            return
        self._card = HoverCard(self, self._preview_content(), open_delay=200, close_delay=100)

    def _preview_content(self) -> QtWidgets.QWidget:
        builder = self._preview_builder if self._preview_builder is not None else default_preview_builder
        return builder(self._entity, list(self._preview), self._context)

    # --- layout ---

    def _refresh(self) -> None:
        self._text = self.label
        self.setAccessibleName(self.label)
        self.setToolTip(self.label)
        self._apply_focus_policy()
        self.updateGeometry()
        self.update()

    def has_leading(self) -> bool:
        return self._chip_variant != "text"

    def _apply_focus_policy(self) -> None:
        policy = QtCore.Qt.FocusPolicy
        reachable = self._removable or self.interactive
        self.setFocusPolicy(policy.TabFocus if reachable else policy.NoFocus)

    def _left_pad(self) -> int:
        return super()._left_pad() if self.boxed else 0

    def _right_pad(self) -> int:
        return super()._right_pad() if self.boxed else 0

    def _font(self) -> QtGui.QFont:
        """Medium at the chip's type step, monospace with tabular figures for a bare id."""
        step = CHIP_TEXT[self.size_step]
        font = self.theme.font(
            step, QtGui.QFont.Weight.Medium, mono=not self.named, tabular=not self.named
        )
        if self._chip_variant == "link" and self.url and self.hovered:
            font.setUnderline(True)
        return font

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        hint = super().sizeHint()
        if self.boxed:
            return hint
        line = QtGui.QFontMetrics(self._font()).height()
        return QtCore.QSize(hint.width(), max(line, CHIP_GLYPH[self.size_step]))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        hint = self.sizeHint()
        return QtCore.QSize(min(hint.width(), hint.height()), hint.height())

    def _box(self) -> QtCore.QRect:
        if self.boxed:
            return super()._box()
        return self.rect()

    # --- colours ---

    def _surface(self) -> tuple[QtGui.QColor | None, QtGui.QColor | None, QtGui.QColor]:
        theme = self.theme
        if not self.boxed:
            return None, None, theme.color("foreground")
        if self.interactive and self.hovered:
            return theme.color("accent"), theme.color("border"), theme.color("accent_foreground")
        return theme.color("secondary"), theme.color("border"), theme.color("secondary_foreground")

    # --- interaction ---

    def on_hover_changed(self, value: bool) -> None:
        # A link underlines on hover, so the font changes with the state and the text re-measures.
        if self._chip_variant == "link":
            self.update()

    def _activate(self) -> None:
        url = self.url
        if url:
            # The row's own page is on another origin, so it opens outside this application.
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        self.clicked.emit()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if (
            self.isEnabled()
            and self.interactive
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and not (self._removable and self._cross_hit().contains(event.pos()))
        ):
            self.set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.pressed and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.set_pressed(False)
            if self._removable and self._cross_hit().contains(event.pos()):
                self._emit_removed()
            elif self.rect().contains(event.pos()) and self.interactive:
                self._activate()
            event.accept()
            return
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self.isEnabled():
            key = event.key()
            if self._removable and key in REMOVE_KEYS:
                self._emit_removed()
                event.accept()
                return
            if key in ACTIVATE_KEYS:
                if self.interactive:
                    self._activate()
                    event.accept()
                    return
                if self._removable:
                    self._emit_removed()
                    event.accept()
                    return
        QtWidgets.QWidget.keyPressEvent(self, event)

    def _emit_removed(self) -> None:
        if self._entity is not None:
            self.removed.emit(self._entity)

    # --- painting ---

    def set_elide_tooltip(self, text: str, fits: bool) -> None:
        """The whole label, always: a chip names the row it points at whether or not it fits."""
        self.setToolTip(self.label)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._entity is None:
            return
        super().paintEvent(event)

    def paint_leading(
        self, painter: QtGui.QPainter, rect: QtCore.QRect, ink: QtGui.QColor
    ) -> None:
        if self.pixmap is not None and not self.pixmap.isNull():
            super().paint_leading(painter, rect, ink)
            return
        glyph = entity_glyph(self._entity.type if self._entity is not None else None)
        paint_icon(painter, rect, glyph, with_alpha(ink, 0.7))


def default_preview_builder(
    entity: EntityRef | None,
    preview: list[str],
    context: SgContext | None,
) -> QtWidgets.QWidget:
    """The hover card's contents: an EntityCard on the row the chip points at.

    The card reads the row itself through the context's cache, so a second chip on the same row
    costs nothing. With no context to read through, the card is the row's name and the paths that
    were asked for.
    """
    if entity is None or context is None:
        where = f"{entity.type} #{entity.id}" if entity is not None else ""
        name = str(entity.name) if entity is not None and entity.name else where
        return HoverCardContent(name, "\n".join([where, *preview]))
    from .entity_card import EntityCard

    return EntityCard(context=context, entity=entity, fields=list(preview), size="sm")


def _context_of(client: object) -> SgContext | None:
    """The shared context for a bare client, so a chip handed one shares the page's caches."""
    if client is None:
        return None
    return context_from_client(client)  # type: ignore[arg-type]
