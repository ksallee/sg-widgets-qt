"""Read the ink of every line of text on screen and say which of it cannot be read.

The class of defect this catches is a control that hands its text to Qt's own drawing, a
`QLineEdit`, a `QPlainTextEdit`, a `QLabel` or a view's delegate, and reads its palette once, at
build time, under whatever theme was nearest then. A popover is a top-level window of its own and
wears its anchor's theme when it opens, so a part built before that moment keeps a light ink on a
dark ground, or a light ground under a light ink, and the reader sees nothing.

A painter reads `self.theme` live and cannot drift, so nothing here looks at painted leaves
directly: it looks at the pixels they left. Three passes:

`palette_faults` is static. For every field Qt draws itself it compares the ink in the widget's
own palette to the surface the nearest theme says is under it. It needs no screenshot and is what
`tests/qt` asserts.

`pixel_faults` grabs every window on show, crops the painted part of each text-bearing widget out
of its own window's picture, and asks whether anything in the crop stands out from the ground. A
widget that says it holds text and shows no ink against its own ground is the defect, whatever
painted it.

`surface_faults` reads the other half of the same picture: a plain container whose ground the
theme's own ink could not be read on. Nothing on such a ground is drawn wrong, the chips over it
wear the theme's white, and none of it can be read, which is what a scroll area's scrolled widget
filled from the application's grey does to a section of a dark popover.

`ink-sweep.py` beside this file is the whole page read this way, in whatever theme the driver was
given; a walk drive puts this directory on `sys.path` and records one check where the page is at
its busiest, in the theme the defect shows in:

    from _ink import check_ink
    check_ink(walk)

    .venv/bin/python tools/qa.py --dark --page context-selector --drive tools/drives/ink-sweep.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sg_widgets_qt.primitives.base import ThemedMixin  # noqa: E402
from sg_widgets_qt.theme import contrast_ratio, theme_of  # noqa: E402

__all__ = [
    "MIN_CONTRAST",
    "MIN_INK_PIXELS",
    "READABLE",
    "candidates",
    "check_ink",
    "composite",
    "faults",
    "palette_faults",
    "pixel_faults",
    "scan",
    "surface_faults",
    "surfaces",
]

#: What the ink in a field's palette has to stand out from the theme's surface by, as a WCAG
#: ratio, before the static pass lets it through. Body text is `foreground` on `background`,
#: which is 15:1 or better in every palette, and the weakest ink the tokens carry is
#: `muted_foreground`. Under 2 nothing is a dim ink; it is the wrong ink.
MIN_CONTRAST = 2.0

#: How many pixels of a crop have to stand out from its ground before the text on it counts as
#: drawn. A line of body text in a field as wide as a page is a few dozen pixels of ink in twenty
#: thousand of ground, so this is a count and never a share, and it is low: a page number is one
#: digit, a dozen pixels of stem. The defect this looks for leaves none at all.
MIN_INK_PIXELS = 6

#: What one pixel has to reach against the ground to count as ink rather than as its edge.
READABLE = 3.0

#: The rim dropped from a crop before it is read, so a field's own border and a row's selection
#: edge are not mistaken for its ink.
CROP_INSET = 3

#: A crop smaller than this in either direction holds no readable run of text. A widget scrolled
#: down to a few pixels of itself is a sliver of its own ground, never a line anyone can read.
MIN_CROP = 10

#: How much of a widget has to be on screen before what is on screen is read. A table a page long
#: shows a band of itself between two rows at some scroll positions, and a band of a row's padding
#: says nothing about the text above and below it.
SEEN_SHARE = 0.6

#: The roles a widget's ink comes from, per kind.
_TEXT_ROLE = QtGui.QPalette.ColorRole.Text
_WINDOW_TEXT_ROLE = QtGui.QPalette.ColorRole.WindowText


def _is_visible(widget: QtWidgets.QWidget) -> bool:
    return bool(widget.isVisible() and widget.width() > 0 and widget.height() > 0)


def _text_of(widget: QtWidgets.QWidget) -> str:
    """What a widget says it is showing, or an empty string where it shows nothing."""
    if isinstance(widget, QtWidgets.QHeaderView):
        # A header view holds the table's model, so its rows are the body's cells and not the
        # labels it draws. What it draws is the header data of its own orientation.
        model = widget.model()
        if model is None:
            return ""
        parts = [
            str(model.headerData(section, widget.orientation()) or "")
            for section in range(min(widget.count(), 40))
        ]
        return " ".join(part for part in parts if part)
    if isinstance(widget, QtWidgets.QAbstractItemView):
        model = widget.model()
        if model is None:
            return ""
        rows = min(model.rowCount(), 40)
        parts = [str(model.index(row, 0).data() or "") for row in range(rows)]
        return " ".join(part for part in parts if part)
    for reader in ("text", "toPlainText"):
        found = getattr(widget, reader, None)
        if callable(found):
            try:
                value = found()
            except TypeError:  # `text` on a class that takes an argument.
                continue
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _kinds() -> tuple:
    return (
        QtWidgets.QLabel,
        QtWidgets.QLineEdit,
        QtWidgets.QPlainTextEdit,
        QtWidgets.QTextEdit,
        QtWidgets.QAbstractItemView,
        QtWidgets.QAbstractButton,
    )


def roots() -> list[QtWidgets.QWidget]:
    """Every top-level window on show, the main one first."""
    found = [one for one in QtWidgets.QApplication.topLevelWidgets() if _is_visible(one)]
    found.sort(key=lambda one: 0 if isinstance(one, QtWidgets.QMainWindow) else 1)
    return found


def candidates() -> list[QtWidgets.QWidget]:
    """Every visible widget on screen that hands a run of text to Qt's own drawing."""
    out: list[QtWidgets.QWidget] = []
    seen: set[int] = set()
    for root in roots():
        for widget in [root, *root.findChildren(QtWidgets.QWidget)]:
            if id(widget) in seen or not _is_visible(widget):
                continue
            if not isinstance(widget, _kinds()):
                continue
            seen.add(id(widget))
            out.append(widget)
    return out


def _name(widget: QtWidgets.QWidget) -> str:
    own = widget.objectName()
    return f"{type(widget).__name__}({own})" if own else type(widget).__name__


def _owner(widget: QtWidgets.QWidget) -> str:
    """The nearest named ancestor, which is what a fault is reported against."""
    node = widget.parentWidget()
    while node is not None:
        if node.objectName():
            return node.objectName()
        node = node.parentWidget()
    return widget.window().objectName() or type(widget.window()).__name__


# --- the static pass -------------------------------------------------------------------------


def _surface(widget: QtWidgets.QWidget) -> str:
    """Which token names the ground under a widget: a popup wears `popover`, a page `background`."""
    window = widget.window()
    if window is not None and window is not QtWidgets.QApplication.activeWindow():
        flags = window.windowFlags()
        if flags & QtCore.Qt.WindowType.Tool or flags & QtCore.Qt.WindowType.Popup:
            return "popover"
    return "background"


def _fields(widget: QtWidgets.QWidget) -> bool:
    """True for the boxes whose ink is a colour in their own palette."""
    return isinstance(
        widget, (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)
    )


def palette_faults() -> list[dict]:
    """Every field whose own palette holds an ink that cannot be read on the theme's ground.

    Only the fields Qt draws itself are read: a painted leaf takes its ink from `self.theme` at
    paint time and cannot hold a stale one.
    """
    out: list[dict] = []
    for widget in candidates():
        if not _fields(widget):
            continue
        theme = theme_of(widget)
        ground = theme.color(_surface(widget))
        palette = widget.palette()
        for group in (
            QtGui.QPalette.ColorGroup.Active,
            QtGui.QPalette.ColorGroup.Inactive,
        ):
            ink = palette.color(group, _TEXT_ROLE)
            ratio = contrast_ratio(ink, ground)
            if ratio < MIN_CONTRAST:
                out.append(
                    {
                        "widget": _name(widget),
                        "under": _owner(widget),
                        "group": str(group).rsplit(".", 1)[-1],
                        "ink": ink.name(),
                        "ground": ground.name(),
                        "ratio": round(ratio, 2),
                        "why": "the ink in the field's palette cannot be read on the theme's ground",
                    }
                )
                break
    return out


# --- the pixel pass --------------------------------------------------------------------------


def composite() -> dict[int, QtGui.QImage]:
    """Every window on show, grabbed once, by the id of the window it came from.

    A popover is a top-level of its own and paints its own surface, so a widget inside one is
    read out of that window's picture rather than out of the page's: the ground under the text is
    then the surface the popover painted and not whatever the page happened to have there.
    """
    out: dict[int, QtGui.QImage] = {}
    for window in roots():
        shot = window.grab().toImage()
        out[id(window)] = shot.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    return out


def _seen_rect(widget: QtWidgets.QWidget) -> QtCore.QRect:
    """The part of a widget that is actually painted, in its own window's coordinates.

    A widget scrolled half out of its pane paints only the half inside it, and reading the whole
    rectangle would read a screenful of nothing as a run of text that vanished.
    """
    region = widget.visibleRegion().boundingRect()
    if region.isEmpty():
        return QtCore.QRect()
    window = widget.window()
    top_left = widget.mapTo(window, region.topLeft())
    return QtCore.QRect(top_left, region.size())


def _crop(image: QtGui.QImage, rect: QtCore.QRect) -> list[int]:
    """The opaque pixels of one rectangle of a window's picture, as packed RGB."""
    box = rect.adjusted(CROP_INSET, CROP_INSET, -CROP_INSET, -CROP_INSET)
    box = box.intersected(image.rect())
    if box.width() < MIN_CROP or box.height() < MIN_CROP:
        return []
    out: list[int] = []
    for y in range(box.top(), box.bottom() + 1):
        for x in range(box.left(), box.right() + 1):
            packed = image.pixel(x, y)
            if (packed >> 24) & 0xFF < 200:  # The translucent room a popover keeps for its shadow.
                continue
            out.append(packed & 0xFFFFFF)
    return out


def _color(packed: int) -> QtGui.QColor:
    return QtGui.QColor((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF)


def pixel_faults(threshold: float = READABLE) -> list[dict]:
    """Every widget that says it holds text and shows no ink against its own ground.

    The ground is the colour that covers most of the part of the widget that is painted; the ink
    is whatever stands furthest from it and covers enough of the crop to be a glyph rather than
    the antialiasing around one.
    """
    pictures = composite()
    out: list[dict] = []
    for widget in candidates():
        text = _text_of(widget)
        if not text:
            continue
        image = pictures.get(id(widget.window()))
        if image is None or image.isNull():
            continue
        seen = _seen_rect(widget)
        if seen.isEmpty():
            continue
        if seen.height() < widget.height() * SEEN_SHARE:
            continue
        pixels = _crop(image, seen)
        if len(pixels) < MIN_CROP * MIN_CROP:
            continue
        counts = Counter(pixels)
        ground = _color(counts.most_common(1)[0][0])
        if _fields(widget) and contrast_ratio(
            widget.palette().color(QtGui.QPalette.ColorGroup.Active, _TEXT_ROLE), ground
        ) >= threshold:
            # A field's ink is a colour in its palette, which the static pass reads exactly. One
            # digit of it is a stem a pixel wide, every pixel of it a blend with the ground, and
            # counting those would call a readable `1` invisible.
            continue
        drawn = 0
        best = 1.0
        ink = ground
        for packed, count in counts.items():
            found = _color(packed)
            ratio = contrast_ratio(found, ground)
            if ratio >= threshold:
                drawn += count
            if ratio > best and count >= 4:
                best, ink = ratio, found
        if drawn < MIN_INK_PIXELS:
            out.append(
                {
                    "widget": _name(widget),
                    "under": _owner(widget),
                    "text": text[:60],
                    "ground": ground.name(),
                    "ink": ink.name(),
                    "ratio": round(best, 2),
                    "why": "the widget holds text and none of it stands out from its ground",
                }
            )
    return out


def _paints_itself(widget: QtWidgets.QWidget) -> bool:
    """True where the widget draws its own ground, so the tokens it drew with are its business.

    A row that fills with `sidebar_accent` behind `sidebar_accent_foreground` is a pair the theme
    names; read against the page's own ink it would look like a fault and is not one.
    """
    return type(widget).paintEvent is not QtWidgets.QWidget.paintEvent


def surfaces() -> list[QtWidgets.QWidget]:
    """Every plain container on screen: a widget Qt fills, not one this package paints."""
    out: list[QtWidgets.QWidget] = []
    seen: set[int] = set()
    for root in roots():
        for widget in [root, *root.findChildren(QtWidgets.QWidget)]:
            if id(widget) in seen or not _is_visible(widget):
                continue
            seen.add(id(widget))
            if isinstance(widget, (ThemedMixin, *_kinds())) or _paints_itself(widget):
                continue
            out.append(widget)
    return out


#: How much of a crop the ground has to cover before it is read as the widget's ground rather than
#: as part of a picture or a row of chips drawn over it.
GROUND_SHARE = 0.8

#: How far a pixel may stand from the most common colour and still be that ground. A translucent
#: window composites its surface a shade either way, so a flat fill is several neighbouring
#: colours and never one.
SAME = 1.15


def surface_faults(threshold: float = READABLE) -> list[dict]:
    """Every plain container filled with a ground the theme's own ink could not be read on.

    `QScrollArea.setWidget` turns the scrolled widget's auto-fill on and Qt fills it from the
    application's palette, which is a light grey whatever the theme says. Nothing on that ground
    is drawn wrong, the chips over it wear the theme's white, and none of it can be read.
    """
    pictures = composite()
    out: list[dict] = []
    for widget in surfaces():
        image = pictures.get(id(widget.window()))
        if image is None or image.isNull():
            continue
        seen = _seen_rect(widget)
        if seen.isEmpty() or seen.height() < widget.height() * SEEN_SHARE:
            continue
        pixels = _crop(image, seen)
        if len(pixels) < MIN_CROP * MIN_CROP:
            continue
        counts = Counter(pixels)
        packed = counts.most_common(1)[0][0]
        flat = _color(packed)
        covered = sum(
            count
            for other, count in counts.items()
            if contrast_ratio(_color(other), flat) < SAME
        )
        if covered < len(pixels) * GROUND_SHARE:
            continue
        theme = theme_of(widget)
        token = _surface(widget)
        ink = theme.color("foreground" if token == "background" else token + "_foreground")
        ground = _color(packed)
        ratio = contrast_ratio(ground, ink)
        if ratio < threshold:
            out.append(
                {
                    "widget": _name(widget),
                    "under": _owner(widget),
                    "text": "",
                    "ground": ground.name(),
                    "ink": ink.name(),
                    "ratio": round(ratio, 2),
                    "why": "the ground this stands on could not carry the theme's own ink",
                }
            )
    return out


def scan(threshold: float = READABLE) -> dict:
    """The three passes, as one report."""
    return {
        "palette": palette_faults(),
        "pixels": pixel_faults(threshold),
        "surfaces": surface_faults(threshold),
    }


def faults(threshold: float = READABLE) -> list[str]:
    """Both passes as one list of lines, empty while every run of text on screen reads."""
    report = scan(threshold)
    out = []
    for one in report["palette"] + report["pixels"] + report["surfaces"]:
        out.append(
            f"{one['under']} / {one['widget']}: ink {one['ink']} on {one['ground']} "
            f"at {one['ratio']}:1 -- {one['why']}"
        )
    return out


def check_ink(walk: Any, said: str = "ink: every run of text on screen reads against its ground") -> bool:
    """Record on a walk whether anything on screen is ink the reader cannot see.

    Both `Walk` classes under `walk/` take `check(what, ok, expected, actual)`, so one call ends
    any of them. The walk owns the state, so the call goes where the page is at its busiest, the
    list open on a query or the editor in a popover, and in the theme the defect shows in.
    """
    lines = faults()
    return walk.check(said, not lines, [], lines)
