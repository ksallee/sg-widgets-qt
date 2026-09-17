"""The one row every picker, search and dense list draws.

Rule 9 of `docs/design-rules.md` and the upstream `picker-row.tsx`: a leading picture, an
indicator column that is there whether or not the row is ticked, the label with the matched
runs in DemiBold, a code beside it in the mono family, a muted sub-label, and a right-aligned
secondary. A row with a sub-label stays centred and takes 4px of vertical padding, so its two
lines stand as tall as a one-line row with a picture.

The delegate reads the parts off the model through `roles.Roles`, so a caller brings any
`QAbstractItemModel` and answers the roles it has.
"""
from __future__ import annotations

from collections.abc import Sequence

from qtpy.QtCore import QEvent, QModelIndex, QRect, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
from qtpy.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QToolTip, QWidget

from sg_widgets_core.render import NAME_HUES as CORE_NAME_HUES
from sg_widgets_core.render import initials_of as core_initials_of
from sg_widgets_core.render import name_hue as core_name_hue

from .. import icons
from ..theme import Theme, theme_of, with_alpha
from .base import CHIP_HEIGHT, THUMB_SIZE, elide
from .roles import Roles

__all__ = [
    "CHIP_STEP",
    "CODE_TEXT",
    "DRILL_WIDTH",
    "GAP",
    "INDICATOR_HEIGHT",
    "INDICATOR_WIDTH",
    "LEAD_GLYPH",
    "NAME_HUES",
    "ROW_PAD_X",
    "ROW_PAD_Y",
    "ROW_PAD_Y_SUB",
    "ROW_TEXT",
    "RowDelegate",
    "initials_of",
    "label_weight",
    "name_hue",
]

#: The leading slot follows the thumbnail ladder.
LEAD = THUMB_SIZE

#: A chip inside a row sits one step under the row, rule 3.
CHIP_STEP: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: The drill control at the trailing edge of a row that opens a level: an icon button's hit
#: box, with the chevron drawn at the glyph's own size inside it.
DRILL_WIDTH = 24
DRILL_GLYPH = "chevron-right"

#: A glyph standing in for a picture, a step under the slot it sits in.
LEAD_GLYPH: dict[str, int] = {"sm": 14, "md": 16, "lg": 20}

#: A row's text, on the leaf ladder.
ROW_TEXT: dict[str, int] = {"sm": 12, "md": 14, "lg": 16}

#: The sub-label, the code and the secondary are all the metadata step.
CODE_TEXT = 12

#: The row's own inset, and the tighter vertical inset a two-line row takes.
ROW_PAD_X = 8
ROW_PAD_Y = 6
ROW_PAD_Y_SUB = 4

#: Between the slots of a row, and between the label and the code beside it.
GAP = 8
LABEL_GAP = 6

#: The indicator column, drawn whether or not the row is ticked.
INDICATOR_WIDTH = 16
INDICATOR_HEIGHT = 20

#: The checkbox inside that column.
CHECKBOX = 16

#: Eight hues far enough apart to tell neighbours apart, skipping the muddy yellows.
#: Core's own table, so the delegate and a card tint one name alike.
NAME_HUES = CORE_NAME_HUES


def name_hue(name: str) -> int:
    """A stable hue for a name, core's `name_hue`."""
    return core_name_hue(name)


def initials_of(name: str, limit: int = 2) -> str:
    """The first letter of the first word, and of the last where there are two. Core's own."""
    return core_initials_of(name, limit)


class RowDelegate(QStyledItemDelegate):
    """Draws the row of rule 9 from the model roles in `roles.py`.

    `indicator` says what the tick column holds and where it sits: `checkbox` leads the row,
    `tick` trails it, `none` leaves the column out. `thumbnail` turns the leading slot off for
    a dense list. `density` of `compact` halves the vertical inset.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        size: str = "md",
        thumbnail: bool = True,
        round_thumbnail: bool = False,
        indicator: str = "none",
        density: str = "default",
        load_more_text: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._size = size
        self._thumbnail = thumbnail
        self._round = round_thumbnail
        self._indicator = indicator
        self._density = density
        self._load_more_text = load_more_text
        self._bare_glyph = False
        self._elided: set[int] = set()

    # --- the keywords --------------------------------------------------------------------

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the rung the picture and the text stand on."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value

    @property
    def thumbnail(self) -> bool:
        """Whether the row keeps a leading slot."""
        return self._thumbnail

    def set_thumbnail(self, value: bool) -> None:
        self._thumbnail = bool(value)

    @property
    def round_thumbnail(self) -> bool:
        """Whether the leading picture is a circle, which is what a person's avatar is."""
        return self._round

    def set_round_thumbnail(self, value: bool) -> None:
        self._round = bool(value)

    @property
    def bare_glyph(self) -> bool:
        """Whether a glyph the caller supplied is drawn on its own, with no picture box."""
        return self._bare_glyph

    def set_bare_glyph(self, value: bool) -> None:
        """A row the caller gave a glyph has no picture to stand in for, so it draws none.

        Upstream draws the picture box only where a picture was expected and has not landed;
        a level of a tree or an assigned task names its glyph and shows that alone.
        """
        self._bare_glyph = bool(value)

    @property
    def indicator(self) -> str:
        """`none`, `checkbox` or `tick`."""
        return self._indicator

    def set_indicator(self, value: str) -> None:
        self._indicator = value

    @property
    def density(self) -> str:
        """`default` or `compact`, which halves the vertical inset."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value

    @property
    def load_more_text(self) -> int:
        """The step the load-more row's label stands on.

        A search widget's row is `text-sm`, the body step; a picker's is `text-xs`, the
        metadata one, so the two are told apart here rather than each drawing its own row.
        """
        return self._load_more_text if self._load_more_text else ROW_TEXT[self._size]

    def set_load_more_text(self, value: int | None) -> None:
        self._load_more_text = value

    # --- metrics -------------------------------------------------------------------------

    def _theme(self, option: QStyleOptionViewItem) -> Theme:
        widget = getattr(option, "widget", None)
        return theme_of(widget if widget is not None else self.parent())

    def _pad_y(self, has_sub: bool) -> int:
        pad = ROW_PAD_Y_SUB if has_sub else ROW_PAD_Y
        return max(1, pad // 2) if self._density == "compact" else pad

    def _lead_size(self) -> int:
        return LEAD[self._size]

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        theme = self._theme(option)
        kind = _kind(index)
        width = max(0, option.rect.width())
        if kind == "separator":
            return QSize(width, 5)
        if kind == "heading":
            metrics = QFontMetrics(theme.font(CODE_TEXT, QFont.Weight.Medium))
            return QSize(width, metrics.height() + 2 * ROW_PAD_Y)
        if kind == "load_more":
            metrics = QFontMetrics(theme.font(self.load_more_text))
            return QSize(width, metrics.height() + 2 * ROW_PAD_Y)

        if callable(index.data(Roles.ROW_PAINTER)):
            chip = CHIP_HEIGHT[CHIP_STEP.get(self._size, "sm")]
            return QSize(width, chip + 2 * self._pad_y(False))

        sub = _text(index, Roles.SUB_LABEL)
        label_height = QFontMetrics(theme.font(ROW_TEXT[self._size])).height()
        height = label_height
        if sub:
            height += QFontMetrics(theme.font(CODE_TEXT)).height()
        lead = self._lead_size() if self._thumbnail else 0
        if self._indicator != "none":
            lead = max(lead, INDICATOR_HEIGHT)
        return QSize(width, max(height, lead) + 2 * self._pad_y(bool(sub)))

    # --- painting ------------------------------------------------------------------------

    def paint(  # noqa: C901
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        theme = self._theme(option)
        kind = _kind(index)
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        if kind == "separator":
            line = QRect(rect.left(), rect.center().y(), rect.width(), 1)
            painter.fillRect(line, theme.color("border"))
            painter.restore()
            return

        if kind == "heading":
            painter.setFont(theme.font(CODE_TEXT, QFont.Weight.Medium))
            painter.setPen(theme.color("muted_foreground"))
            box = rect.adjusted(ROW_PAD_X, 0, -ROW_PAD_X, 0)
            painter.drawText(
                box,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                elide(painter, _text(index, Roles.LABEL) or _display(index), box.width()),
            )
            painter.restore()
            return

        self._paint_background(painter, option, theme, rect)

        if kind == "load_more":
            painter.setFont(theme.font(self.load_more_text))
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                rect,
                int(Qt.AlignmentFlag.AlignCenter),
                _text(index, Roles.LABEL) or _display(index) or "Load more",
            )
            painter.restore()
            return

        if bool(index.data(Roles.DISABLED)):
            painter.setOpacity(0.5)

        self._paint_row(painter, option, index, theme, rect)
        painter.restore()

    def drill_rect(self, rect: QRect, index: QModelIndex) -> QRect:
        """Where the drill control of a row sits, so a view can tell a press on it apart."""
        if not bool(index.data(Roles.DRILLABLE)):
            return QRect()
        pad_y = self._pad_y(bool(_text(index, Roles.SUB_LABEL)))
        box = rect.adjusted(ROW_PAD_X, pad_y, -ROW_PAD_X, -pad_y)
        right = box.right() + 1
        if self._indicator == "tick":
            right -= INDICATOR_WIDTH + GAP
        return QRect(right - DRILL_WIDTH, box.top(), DRILL_WIDTH, box.height())

    def _paint_background(
        self, painter: QPainter, option: QStyleOptionViewItem, theme: Theme, rect: QRect
    ) -> None:
        """The highlight. One colour for the keyboard cursor and the selection, per rule 5.

        Upstream's row carries `data-highlighted:bg-accent` and nothing else: the pointer
        moves the keyboard cursor onto the row it is over, so hover and the cursor are the
        same state and wear the same fill rather than a second, weaker one.
        """
        if not option.state & QStyle.StateFlag.State_Selected:
            return
        fill = theme.color("accent")
        radius = theme.radius_px("sm")
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)
        painter.restore()

    def _paint_row(  # noqa: C901
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        theme: Theme,
        rect: QRect,
    ) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        ink = theme.color("accent_foreground" if selected else "foreground")
        muted = theme.color("muted_foreground") if not selected else with_alpha(ink, 0.7)
        sub = _text(index, Roles.SUB_LABEL)
        pad_y = self._pad_y(bool(sub))
        box = rect.adjusted(ROW_PAD_X, pad_y, -ROW_PAD_X, -pad_y)
        left, right = box.left(), box.right() + 1

        # A row the caller draws whole takes the inset and nothing else: no leading slot, no
        # label column. The palette's recents are that row.
        whole = index.data(Roles.ROW_PAINTER)
        if callable(whole):
            painter.save()
            whole(painter, QRect(box), option)
            painter.restore()
            return

        if self._indicator == "checkbox":
            column = QRect(left, box.top(), INDICATOR_WIDTH, box.height())
            self._paint_checkbox(painter, column, index, theme)
            left += INDICATOR_WIDTH + GAP

        if self._thumbnail:
            side = self._lead_size()
            slot = QRect(left, box.top() + (box.height() - side) // 2, side, side)
            self._paint_lead(painter, slot, index, theme)
            left += side + GAP

        if self._indicator == "tick":
            column = QRect(right - INDICATOR_WIDTH, box.top(), INDICATOR_WIDTH, box.height())
            self._paint_tick(painter, column, index, ink)
            right -= INDICATOR_WIDTH + GAP

        if bool(index.data(Roles.DRILLABLE)):
            column = QRect(right - DRILL_WIDTH, box.top(), DRILL_WIDTH, box.height())
            glyph = LEAD_GLYPH[self._size]
            mark = QRect(0, 0, glyph, glyph)
            mark.moveCenter(column.center())
            icons.paint_icon(painter, mark, DRILL_GLYPH, muted)
            right -= DRILL_WIDTH + GAP

        secondary = _text(index, Roles.SECONDARY)
        painter_role = index.data(Roles.PAINTER)
        if callable(painter_role):
            width = min(box.width() // 2, 160)
            cell = QRect(right - width, box.top(), width, box.height())
            painter.save()
            painter_role(painter, cell, option)
            painter.restore()
            right -= width + GAP
        elif secondary:
            painter.setFont(theme.font(CODE_TEXT))
            # A pixel of slack: the elider measures a shade wider than the advance.
            width = min(painter.fontMetrics().horizontalAdvance(secondary) + 2, box.width() // 2)
            cell = QRect(right - width, box.top(), width, box.height())
            painter.setPen(muted)
            painter.drawText(
                cell,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                elide(painter, secondary, cell.width()),
            )
            right -= width + GAP

        text_box = QRect(left, box.top(), max(0, right - left), box.height())
        self._paint_text(painter, text_box, index, theme, ink, muted, sub)

    def _paint_text(
        self,
        painter: QPainter,
        box: QRect,
        index: QModelIndex,
        theme: Theme,
        ink: QColor,
        muted: QColor,
        sub: str,
    ) -> None:
        base = theme.font(ROW_TEXT[self._size])
        bold = theme.font(ROW_TEXT[self._size], QFont.Weight.DemiBold)
        label_height = QFontMetrics(base).height()
        sub_height = QFontMetrics(theme.font(CODE_TEXT)).height() if sub else 0
        top = box.top() + max(0, (box.height() - label_height - sub_height) // 2)

        runs = _runs(index)
        crumb = base
        base = theme.font(ROW_TEXT[self._size], label_weight(runs))
        code = _text(index, Roles.CODE)
        code_width = 0
        if code:
            painter.setFont(theme.font(CODE_TEXT, mono=True))
            code_width = painter.fontMetrics().horizontalAdvance(code) + 2
        room = max(0, box.width() - (code_width + LABEL_GAP if code else 0))
        # The code sits beside the label, not at the far edge, so the two read as one line.
        width = min(_runs_width(painter, runs, base, bold, crumb) + 2, room)

        line = QRect(box.left(), top, width, label_height)
        cut = _draw_runs(painter, line, runs, base, bold, ink, muted, crumb)

        if code:
            code_box = QRect(box.left() + width + LABEL_GAP, top, code_width, label_height)
            painter.setFont(theme.font(CODE_TEXT, mono=True))
            painter.setPen(muted)
            painter.drawText(
                code_box,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                elide(painter, code, code_box.width()),
            )

        if sub:
            sub_box = QRect(box.left(), top + label_height, box.width(), sub_height)
            # The sub-label marks its matched runs too, so a row matched on its login or its
            # email shows why it came back, as upstream's `MatchText` does there.
            sub_runs = _sub_runs(index, sub)
            quiet = theme.font(CODE_TEXT)
            heavy = theme.font(CODE_TEXT, QFont.Weight.DemiBold)
            painter.setFont(quiet)
            cut = _draw_runs(painter, sub_box, sub_runs, quiet, heavy, muted, muted) or cut

        if cut:
            self._elided.add(index.row())
        else:
            self._elided.discard(index.row())

    def _paint_lead(
        self, painter: QPainter, slot: QRect, index: QModelIndex, theme: Theme
    ) -> None:
        radius = float(slot.width()) / 2.0 if self._round else float(theme.radius_px("sm"))
        picture = index.data(Roles.PIXMAP)
        if isinstance(picture, QPixmap) and not picture.isNull():
            scaled = picture.scaled(
                slot.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            path = QPainterPath()
            path.addRoundedRect(QRectF(slot), radius, radius)
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(
                slot.left() - max(0, (scaled.width() - slot.width()) // 2),
                slot.top() - max(0, (scaled.height() - slot.height()) // 2),
                scaled,
            )
            painter.restore()
            return

        letters = _text(index, Roles.INITIALS)
        if letters:
            hue = name_hue(_text(index, Roles.LABEL) or _display(index) or letters)
            fill = QColor.fromHsl(hue, 140, 90 if theme.dark else 170)
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(slot, radius, radius)
            painter.setFont(theme.font(max(10, slot.height() // 3), QFont.Weight.Medium))
            painter.setPen(QColor(255, 255, 255) if theme.dark else QColor(20, 20, 20))
            painter.drawText(slot, int(Qt.AlignmentFlag.AlignCenter), letters)
            painter.restore()
            return

        glyph = _text(index, Roles.GLYPH)
        painter.save()
        if not (self._bare_glyph and glyph and not glyph.startswith("#")):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(with_alpha(theme.muted, 1.0))
            painter.drawRoundedRect(slot, radius, radius)
        if glyph.startswith("#"):
            side = LEAD_GLYPH[self._size] // 2
            dot = QRect(slot.center().x() - side, slot.center().y() - side, side * 2, side * 2)
            painter.setBrush(QColor(glyph))
            painter.drawEllipse(dot)
        elif glyph and icons.has_icon(glyph):
            side = LEAD_GLYPH[self._size]
            box = QRect(
                slot.center().x() - side // 2 + 1, slot.center().y() - side // 2 + 1, side, side
            )
            icons.paint_icon(painter, box, glyph, theme.color("muted_foreground"))
        painter.restore()

    def _paint_checkbox(
        self, painter: QPainter, column: QRect, index: QModelIndex, theme: Theme
    ) -> None:
        checked = index.data(Roles.CHECKED)
        box = QRect(
            column.left(),
            column.top() + (column.height() - CHECKBOX) // 2,
            CHECKBOX,
            CHECKBOX,
        )
        radius = float(theme.radius_px("sm"))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.color("primary"))
            painter.drawRoundedRect(box, radius, radius)
            icons.paint_icon(painter, box.adjusted(1, 1, -1, -1), "check", theme.color("primary_foreground"))
        else:
            painter.setPen(theme.color("input"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                box.adjusted(0, 0, -1, -1), max(0.0, radius - 0.5), max(0.0, radius - 0.5)
            )
        painter.restore()

    def _paint_tick(
        self, painter: QPainter, column: QRect, index: QModelIndex, ink: QColor
    ) -> None:
        if not index.data(Roles.CHECKED):
            return
        side = INDICATOR_WIDTH
        box = QRect(column.left(), column.top() + (column.height() - side) // 2, side, side)
        icons.paint_icon(painter, box, "check", ink)

    # --- the tooltip ---------------------------------------------------------------------

    def helpEvent(  # noqa: N802
        self,
        event: QEvent,
        view: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        """The full value as the tooltip while the row is elided, and nothing while it fits."""
        if event.type() == QEvent.Type.ToolTip and index.isValid():
            if index.row() in self._elided:
                label = _text(index, Roles.LABEL) or _display(index)
                sub = _text(index, Roles.SUB_LABEL)
                QToolTip.showText(event.globalPos(), "\n".join(x for x in (label, sub) if x), view)
                return True
            QToolTip.hideText()
            return True
        return super().helpEvent(event, view, option, index)


# --- reading the model -------------------------------------------------------------------


def _kind(index: QModelIndex) -> str:
    value = index.data(Roles.KIND)
    return value if isinstance(value, str) and value else "row"


def _display(index: QModelIndex) -> str:
    value = index.data(Qt.ItemDataRole.DisplayRole)
    return "" if value is None else str(value)


def _text(index: QModelIndex, role: Roles) -> str:
    value = index.data(role)
    return "" if value is None else str(value)


def label_weight(runs: Sequence[tuple[str, bool, bool]]) -> QFont.Weight:
    """The weight the label's own runs are drawn at.

    A label behind crumbs takes one step, so the leaf reads as the row and the trail as where
    it sits; upstream puts `font-medium` on the name for the same reason, rule 6's one step.
    A matched run is heavier again, wherever it falls.
    """
    crumbed = any(len(run) > 2 and run[2] for run in runs)
    return QFont.Weight.Medium if crumbed else QFont.Weight.Normal


def _sub_runs(index: QModelIndex, sub: str) -> list[tuple[str, bool, bool]]:
    """The sub-label as runs, or one plain run of it where the model marks none."""
    value = index.data(Roles.SUB_RUNS)
    if isinstance(value, Sequence) and not isinstance(value, str):
        out: list[tuple[str, bool, bool]] = []
        for run in value:
            if isinstance(run, Sequence) and not isinstance(run, str) and len(run) >= 2:
                out.append((str(run[0]), bool(run[1]), False))
        if out:
            return out
    return [(sub, False, False)]


def _runs(index: QModelIndex) -> list[tuple[str, bool, bool]]:
    """The label as `(text, matched, muted)` runs, or one plain run of the label.

    A run carrying a third item is drawn in `muted_foreground`, which is what a breadcrumb
    before the label is. A two-item run is the plain case and reads as unmuted.
    """
    value = index.data(Roles.RUNS)
    if isinstance(value, Sequence) and not isinstance(value, str):
        out: list[tuple[str, bool, bool]] = []
        for run in value:
            if isinstance(run, Sequence) and not isinstance(run, str) and len(run) >= 2:
                out.append((str(run[0]), bool(run[1]), bool(run[2]) if len(run) > 2 else False))
        if out:
            return out
    return [(_text(index, Roles.LABEL) or _display(index), False, False)]


def _runs_width(
    painter: QPainter,
    runs: list[tuple[str, bool, bool]],
    base: QFont,
    bold: QFont,
    dim_font: QFont | None = None,
) -> int:
    """How wide the runs stand, each in the weight it is drawn in, on the painter's device."""
    device = painter.device()
    normal, heavy = QFontMetrics(base, device), QFontMetrics(bold, device)
    quiet = QFontMetrics(dim_font, device) if dim_font is not None else normal
    return sum(
        (heavy if matched else (quiet if dim else normal)).horizontalAdvance(text)
        for text, matched, dim in runs
    )


def _draw_runs(
    painter: QPainter,
    box: QRect,
    runs: list[tuple[str, bool, bool]],
    base: QFont,
    bold: QFont,
    ink: QColor,
    muted: QColor | None = None,
    dim_font: QFont | None = None,
) -> bool:
    """Draw the runs left to right, matched ones in DemiBold. True when the label was cut."""
    painter.setPen(ink)
    x = box.left()
    right = box.right() + 1
    cut = False
    for text, matched, dim in runs:
        if not text or x >= right:
            cut = cut or bool(text)
            continue
        painter.setPen(muted if dim and muted is not None else ink)
        if matched:
            painter.setFont(bold)
        else:
            painter.setFont(dim_font if dim and dim_font is not None else base)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text)
        run_box = QRect(x, box.top(), min(width, right - x), box.height())
        shown = text
        if width > right - x:
            shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, run_box.width())
            cut = True
        painter.drawText(
            run_box, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), shown
        )
        x += width
    return cut
