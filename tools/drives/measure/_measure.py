"""The Qt half of the measure matrix: the widget tree's own numbers, never the picture.

The twin of `tools/drives/upstream/measure/`, which reads the same numbers off the upstream DOM.
`tools/measure_diff.py` puts the two side by side and prints every element that drifted.

    .venv/bin/python tools/qa.py --page global-search \
        --drive tools/drives/measure/global-search-rest.py | \
        python tools/measure_split.py tools/drives/measure global-search

One record per widget carrying an object name, since a Qt object name is the upstream
`data-slot`, plus one per row a delegate draws and one per part inside it, since a Qt row is
paint and not a widget. Every record carries the same keys the upstream walk answers:

    slot cls where x y w h font-size font-weight opacity
    padding-top padding-right padding-bottom padding-left column-gap row-gap
    border-top-left-radius text

and, because a custom-painted widget has no computed style, three samples off a `grab` of the
surface: `paint-corner` just inside the top-left, `paint-mid` at the centre and `paint-right`
just inside the trailing edge. Those are the composited colours a reader sees, which is what
`tools/measure_diff.py` composites the upstream tokens down to before it compares them.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QPoint, QRect, Qt
from qtpy.QtGui import QFont, QFontMetrics
from qtpy.QtWidgets import QAbstractItemView, QApplication, QLayout, QWidget

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.primitives.row_delegate import (
    CODE_TEXT,
    DRILL_WIDTH,
    GAP,
    INDICATOR_WIDTH,
    ROW_LINE,
    ROW_PAD_X,
    ROW_PAD_Y,
    ROW_PAD_Y_SUB,
    ROW_TEXT,
    RowDelegate,
)
from sg_widgets_qt.theme import theme_of

__all__ = [
    "context_selector_open",
    "context_selector_rest",
    "context_selector_sizes",
    "global_search_loading",
    "global_search_no_match",
    "global_search_open_empty",
    "global_search_open_query",
    "global_search_rest",
    "global_search_rows",
    "global_search_sizes",
    "hierarchical_search_no_match",
    "hierarchical_search_rest",
    "hierarchical_search_rows",
    "measure_page",
    "measure_popups",
]

#: The queries the states are driven with, the same ones the upstream twins type.
SITE_QUERY = "sh"
TREE_QUERY = "sh010_0010 comp"
NO_MATCH = "zzzqqq"

#: The tokens a page's theme is reported under, so a colour finding names the token.
TOKENS = (
    "background",
    "foreground",
    "popover",
    "popover_foreground",
    "muted",
    "muted_foreground",
    "accent",
    "accent_foreground",
    "secondary",
    "secondary_foreground",
    "border",
    "input",
    "ring",
    "destructive",
)


# --- reading a surface ----------------------------------------------------------------------


def _hex(colour: object) -> str:
    """A colour as `#rrggbbaa`, which is how both walks write one."""
    return f"#{colour.red():02x}{colour.green():02x}{colour.blue():02x}{colour.alpha():02x}"


class Shot:
    """One grab of a surface, sampled by point.

    A widget of ours paints itself, so the only way to read the colour it settled on is the
    pixel it put there. The grab is taken once per surface and every sample comes off it.
    """

    def __init__(self, root: QWidget) -> None:
        pixmap = root.grab()
        self.ratio = pixmap.devicePixelRatio() or 1.0
        self.image = pixmap.toImage()

    def at(self, x: int, y: int) -> str:
        """`#rrggbbaa` at a point of the surface, or an empty string outside it."""
        px = int(round(x * self.ratio))
        py = int(round(y * self.ratio))
        if px < 0 or py < 0 or px >= self.image.width() or py >= self.image.height():
            return ""
        colour = self.image.pixelColor(px, py)
        return _hex(colour)


def _weight(font: QFont) -> int:
    """The CSS weight of a font, on either binding: Qt 5 counts 0 to 99, Qt 6 counts in CSS."""
    raw = int(font.weight())
    if raw > 100:
        return raw
    ladder = {0: 100, 12: 200, 25: 300, 50: 400, 57: 500, 63: 600, 75: 700, 81: 800, 87: 900}
    return ladder.get(raw, 400)


def _pixel_size(font: QFont) -> int:
    return font.pixelSize() if font.pixelSize() > 0 else int(round(font.pointSize() * 96 / 72))


def _margins(widget: QWidget) -> tuple:
    """The inset a widget keeps, which is where a Qt widget's padding lives: on its layout."""
    layout = widget.layout()
    box = layout.contentsMargins() if isinstance(layout, QLayout) else widget.contentsMargins()
    return (box.top(), box.right(), box.bottom(), box.left())


def _spacing(widget: QWidget) -> object:
    layout = widget.layout()
    return layout.spacing() if isinstance(layout, QLayout) else "normal"


def _radius(widget: QWidget) -> object:
    """The corner a widget paints, where it names the step it took."""
    step = getattr(widget, "radius_step", None)
    if not isinstance(step, str):
        return ""
    try:
        return theme_of(widget).radius_px(step)
    except (KeyError, AttributeError):
        return ""


def _label(widget: QWidget) -> str:
    for name in ("text", "label", "placeholderText"):
        found = getattr(widget, name, None)
        try:
            value = found() if callable(found) else found
        except TypeError:
            continue
        if isinstance(value, str) and value:
            return value[:48]
    return ""


def element(widget: QWidget, root: QWidget, where: str, shot: Shot) -> dict:
    """One widget, in the shape the upstream walk answers."""
    at = widget.mapTo(root, QPoint(0, 0))
    # `width()` and `height()`, never `size()`: a widget of ours has a `size` keyword of its
    # own (`sm`, `md`, `lg`), and that property shadows `QWidget.size`.
    wide, high = widget.width(), widget.height()
    top, right, bottom, left = _margins(widget)
    gap = _spacing(widget)
    font = widget.font()
    return {
        "slot": widget.objectName(),
        "cls": type(widget).__name__,
        "where": where,
        "x": at.x(),
        "y": at.y(),
        "w": wide,
        "h": high,
        "font-size": _pixel_size(font),
        "font-weight": _weight(font),
        "opacity": 1.0 if widget.isEnabled() else 0.5,
        "padding-top": top,
        "padding-right": right,
        "padding-bottom": bottom,
        "padding-left": left,
        "column-gap": gap,
        "row-gap": gap,
        "border-top-left-radius": _radius(widget),
        "paint-corner": shot.at(at.x() + 2, at.y() + 2),
        "paint-mid": shot.at(at.x() + wide // 2, at.y() + high // 2),
        "paint-right": shot.at(at.x() + wide - 3, at.y() + high // 2),
        "text": _label(widget),
    }


def _blank(slot: str, cls: str, where: str, rect: QRect, shot: Shot, **rest: object) -> dict:
    """A record for something painted rather than laid out: a row, a part of a row."""
    made = {
        "slot": slot,
        "cls": cls,
        "where": where,
        "x": rect.x(),
        "y": rect.y(),
        "w": rect.width(),
        "h": rect.height(),
        "font-size": 0,
        "font-weight": 0,
        "opacity": 1.0,
        "padding-top": 0,
        "padding-right": 0,
        "padding-bottom": 0,
        "padding-left": 0,
        "column-gap": "normal",
        "row-gap": "normal",
        "border-top-left-radius": "",
        "paint-corner": shot.at(rect.x() + 2, rect.y() + 2),
        "paint-mid": shot.at(rect.center().x(), rect.center().y()),
        "paint-right": shot.at(rect.right() - 2, rect.center().y()),
        "text": "",
    }
    made.update(rest)  # type: ignore[arg-type]
    return made


# --- the rows a delegate draws --------------------------------------------------------------


def _parts(delegate: RowDelegate, rect: QRect, index: object, theme: object) -> list:
    """Where a row's leading slot, its text block and its trailing marks land.

    The delegate paints them rather than laying them out, so the insets of `row_delegate` are
    walked here the way `_paint_row` walks them, which is what makes a part comparable with
    the upstream `picker-row-*` span of the same name.
    """
    sub = str(index.data(Roles.SUB_LABEL) or "")
    pad_y = ROW_PAD_Y_SUB if sub else ROW_PAD_Y
    if delegate.density == "compact":
        pad_y = max(0, pad_y // 2)
    box = rect.adjusted(ROW_PAD_X, pad_y, -ROW_PAD_X, -pad_y)
    left, right = box.left(), box.right() + 1
    out: list = []
    if delegate.indicator == "checkbox":
        out.append(("picker-row-checkbox", QRect(left, box.top(), INDICATOR_WIDTH, box.height())))
        left += INDICATOR_WIDTH + GAP
    if delegate.thumbnail:
        side = delegate._lead_size()  # noqa: SLF001 - the ladder the delegate settled on
        out.append(("picker-row-lead", QRect(left, box.top(), side, side)))
        left += side + GAP
    if delegate.indicator == "tick":
        right -= INDICATOR_WIDTH + GAP
        out.append(
            ("picker-row-tick", QRect(right + GAP, box.top(), INDICATOR_WIDTH, box.height()))
        )
    if index.data(Roles.DRILLABLE):
        right -= DRILL_WIDTH + GAP
        out.append(("picker-row-drill", QRect(right + GAP, box.top(), DRILL_WIDTH, box.height())))
    secondary = str(index.data(Roles.SECONDARY) or "")
    if secondary:
        width = QFontMetrics(theme.font(CODE_TEXT)).horizontalAdvance(secondary)
        right -= width + GAP
        out.append(("picker-row-secondary", QRect(right + GAP, box.top(), width, box.height())))
    out.append(("picker-row-text", QRect(left, box.top(), max(0, right - left), box.height())))
    if sub:
        label = ROW_LINE[delegate.size]
        out.append(
            (
                "picker-row-sub-label",
                QRect(left, box.top() + label, max(0, right - left), box.height() - label),
            )
        )
    return out


def rows_of(view: QAbstractItemView, root: QWidget, where: str, shot: Shot, limit: int = 10) -> list:
    """One record per drawn row, and one per part inside it."""
    model = view.model()
    delegate = view.itemDelegate()
    if model is None or not isinstance(delegate, RowDelegate):
        return []
    theme = theme_of(view)
    name = view.objectName() or "list"
    origin = view.viewport().mapTo(root, QPoint(0, 0))
    out: list = []
    for row in range(min(limit, model.rowCount())):
        index = model.index(row, 0)
        rect = view.visualRect(index)
        if rect.height() <= 0:
            continue
        where_rect = rect.translated(origin)
        kind = str(index.data(Roles.KIND) or "row")
        slot = {"heading": f"{name}-heading", "load_more": f"{name}-more"}.get(
            kind, f"{name}-option"
        )
        hint = delegate.sizeHint(_option(view), index).height()
        out.append(
            _blank(
                slot,
                "row",
                where,
                where_rect,
                shot,
                row=row,
                **{"hint-h": hint},
                text=str(index.data(Qt.ItemDataRole.DisplayRole) or "")[:48],
                **{"font-size": _pixel_size(theme.font(ROW_TEXT[delegate.size]))},
            )
        )
        if kind != "row":
            continue
        for part, part_rect in _parts(delegate, where_rect, index, theme):
            out.append(_blank(part, "row-part", where, part_rect, shot, row=row))
    return out


def _option(view: QAbstractItemView) -> object:
    """A style option carrying the view, which is what the delegate reads its theme from."""
    from qtpy.QtWidgets import QStyleOptionViewItem

    option = QStyleOptionViewItem()
    option.initFrom(view)
    option.widget = view
    option.rect = QRect(0, 0, view.viewport().width(), 0)
    return option


# --- the walk -------------------------------------------------------------------------------


def walk(root: QWidget, where: str) -> list:
    """Every named widget under a surface, then every row its lists draw."""
    shot = Shot(root)
    out: list = []
    for widget in [root, *root.findChildren(QWidget)]:
        if widget is not root and not widget.isVisible():
            continue
        if not widget.objectName():
            continue
        out.append(element(widget, root, where, shot))
    for view in root.findChildren(QAbstractItemView):
        if view.isVisible():
            out.extend(rows_of(view, root, where, shot))
    return out


def tokens_of(widget: QWidget) -> dict:
    """The palette the surface is wearing, so a colour finding can name the token."""
    theme = theme_of(widget)
    out: dict = {}
    for name in TOKENS:
        colour = theme.color(name)
        out[name] = _hex(colour)
    out["radius"] = theme.radius_px("lg")
    out["radius-md"] = theme.radius_px("md")
    out["radius-sm"] = theme.radius_px("sm")
    out["radius-xl"] = theme.radius_px("xl")
    return out


def measure_page(page: QWidget, case: str = "rest") -> dict:
    """The page's own tree, in the shape `tools/measure_diff.py` reads."""
    return {"case": case, "tokens": tokens_of(page), "elements": walk(page, "pane")}


def measure_popups(page: QWidget | None = None) -> list:
    """Every top-level surface standing over the window: a dialog, a popover, a menu.

    The showcase window itself is not one. Offscreen there is no active window, so the window
    the page sits in is what the walk steps over.
    """
    held = page.window() if page is not None else QApplication.activeWindow()
    out: list = []
    for other in QApplication.topLevelWidgets():
        if other is held or not other.isVisible() or other.width() <= 0:
            continue
        if page is not None and other.isAncestorOf(page):
            continue
        out.extend(walk(other, "popup"))
    return out


def measured(page: QWidget, case: str) -> dict:
    """The page and every popup over it, as one state."""
    out = measure_page(page, case)
    out["elements"].extend(measure_popups(page))
    return out


# --- the states -----------------------------------------------------------------------------


def settle(control: object, wait: object, ms: int = 12000) -> None:
    """Spin until the read in flight has answered or failed."""
    deadline = time.monotonic() + ms / 1000.0
    while control.loading and time.monotonic() < deadline:
        wait(25)


def _answered(control: object, wait: object, query: str) -> None:
    control.input().setText(query)
    control.flush()
    settle(control, wait)
    wait(500)


def global_search_rest(page, wait, find, prefs=None) -> dict:
    wait(600)
    return {"verdict": "PASS", "states": {"rest": measured(page, "rest")}}


def global_search_open_empty(page, wait, find, prefs=None) -> dict:
    palette = find("global-search-palette")
    palette.set_open(True)
    wait(700)
    return {"verdict": "PASS", "states": {"open-empty": measured(page, "open-empty")}}


def global_search_open_query(page, wait, find, prefs=None) -> dict:
    palette = find("global-search-palette")
    palette.set_open(True)
    wait(400)
    _answered(palette.search_control(), wait, SITE_QUERY)
    wait(300)
    return {"verdict": "PASS", "states": {"open-query": measured(page, "open-query")}}


def global_search_loading(page, wait, find, prefs=None) -> dict:
    control = find("global-search-inline").search_control()
    control.input().setText(SITE_QUERY)
    # The pause is 250ms and the demo's read waits 300ms, so the skeletons are up at 320ms.
    wait(320)
    return {"verdict": "PASS", "states": {"loading": measured(page, "loading")}}


def global_search_rows(page, wait, find, prefs=None) -> dict:
    _answered(find("global-search-inline").search_control(), wait, SITE_QUERY)
    return {"verdict": "PASS", "states": {"rows": measured(page, "rows")}}


def global_search_no_match(page, wait, find, prefs=None) -> dict:
    _answered(find("global-search-inline").search_control(), wait, NO_MATCH)
    return {"verdict": "PASS", "states": {"no-match": measured(page, "no-match")}}


def global_search_sizes(page, wait, find, prefs=None) -> dict:
    wait(500)
    return {"verdict": "PASS", "states": {"sizes": measured(page, "sizes")}}


def hierarchical_search_rest(page, wait, find, prefs=None) -> dict:
    settle(find("hierarchical-search").search_control(), wait)
    wait(600)
    return {"verdict": "PASS", "states": {"rest": measured(page, "rest")}}


def hierarchical_search_rows(page, wait, find, prefs=None) -> dict:
    _answered(find("hierarchical-search").search_control(), wait, TREE_QUERY)
    return {"verdict": "PASS", "states": {"rows": measured(page, "rows")}}


def hierarchical_search_no_match(page, wait, find, prefs=None) -> dict:
    _answered(find("hierarchical-search").search_control(), wait, NO_MATCH)
    return {"verdict": "PASS", "states": {"no-match": measured(page, "no-match")}}


def context_selector_rest(page, wait, find, prefs=None) -> dict:
    wait(600)
    return {"verdict": "PASS", "states": {"rest": measured(page, "rest")}}


def context_selector_open(page, wait, find, prefs=None) -> dict:
    selector = find("context-selector")
    selector.set_open(True)
    settle(selector.tasks_control(), wait)
    wait(700)
    return {"verdict": "PASS", "states": {"open": measured(page, "open")}}


def context_selector_sizes(page, wait, find, prefs=None) -> dict:
    wait(500)
    return {"verdict": "PASS", "states": {"sizes": measured(page, "sizes")}}
