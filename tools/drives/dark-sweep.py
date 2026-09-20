#!/usr/bin/env python
"""Walk every showcase page in dark and name every ground and ink that still reads light.

    .venv/bin/python tools/qa.py --dark --drive tools/drives/dark-sweep.py

`ink-sweep.py` beside this file reads one page hard: every popup on it opened, every editor
turned into a field, every box typed into. This reads every page instead, once each, and asks the
one question of the dark sweep: is anything on screen a value that belongs to a light page.

The grounds are point-sampled: what a reader looks at rather than what a widget says it drew.
The page's own ground, the stage of every demo on it, the widget inside each stage and the
children that widget places, and every floating surface standing over them with what it carries,
each at nine points of itself. Two readings are faults.

A sample is light where no token of the theme carries that value: the application's grey or a
white a host style filled, standing where `background`, `card` or `popover` should be. A token
the theme does carry is never a fault, because a dark palette's `primary` is a near white by
design and the button wearing it is right.

A sample inside a surface standing on `popover` is the page's own `background`. That is the
light theme's reading kept: there the two tokens are the same white and the mistake shows
nowhere, and in dark the panel reads as a hole cut in the surface around it.

A ground is a colour the widget wears at more than one of its points, and a point another widget
covers is passed over. A glyph, a row of chips, a status colour and a thumbnail are all a
different colour at each point, and none of them is the ground of the widget under it.

The inks, and the grounds Qt fills rather than a widget paints, come from `_ink.py`: the ink in a
field's own palette read against the surface under it, the widgets that hold text and show none
of it, and the plain containers filled with a ground the theme's ink could not be read on.

A page is walked a screenful at a time, so a demo below the fold is read where it stands. The
surfaces a walk cannot reach -- a popover, a dialog, a menu, a tooltip, the command palette --
are opened one of each kind, on the page that has one, and sampled with it on show.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ink import faults  # noqa: E402
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sg_widgets_qt.theme import (  # noqa: E402
    TOKENS,
    contrast_ratio,
    generate_qss,
    theme_of,
    to_color,
)

#: How far the page is stepped when it is read from top to bottom.
STEP = 700

#: How long a page is given to build and settle its first read before it is sampled.
READY_MS = 6000

#: How long an opened surface is given to place itself and read its rows.
SETTLE_MS = 700

#: The relative luminance at or above which a ground reads as a light page's. Halfway up the
#: scale is a mid grey; every surface token of every dark palette sits far below it, and the
#: greys a host style fills -- `#f0f0f0`, `#ffffff`, `#efefef` -- sit far above.
LIGHT = 0.45

#: How near a sample has to be to a token before it counts as that token rather than as a stray
#: fill. A translucent surface composites a shade either way, so this is a contrast ratio and
#: never an equality.
SAME = 1.08

#: Where a widget is sampled: the middle, the four points a quarter in from each corner, and one
#: near each edge, which on a popover is the padding its own surface shows through.
POINTS = (
    (0.5, 0.5),
    (0.25, 0.25),
    (0.75, 0.25),
    (0.25, 0.75),
    (0.75, 0.75),
    (0.5, 0.08),
    (0.5, 0.92),
    (0.08, 0.5),
    (0.92, 0.5),
)

#: How many widgets of one floating surface are sampled. A popup holds a list, and a list holds
#: a row per answer; the surface, its panel and its first controls are what a reader sees.
INSIDE = 60

#: How many of a widget's points have to agree on a colour before it is that widget's ground.
AGREE = 2


def _luminance(color: QtGui.QColor) -> float:
    """The WCAG relative luminance of a colour, 0 for black and 1 for white."""
    out = 0.0
    for channel, weight in ((color.red(), 0.2126), (color.green(), 0.7152), (color.blue(), 0.0722)):
        value = channel / 255.0
        out += weight * (value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return out


def _token_colors(theme: object) -> list[QtGui.QColor]:
    """Every value the theme carries, so a ground that is one of them is never a fault."""
    return [to_color(getattr(theme, token)) for token in TOKENS]


def _is_token(color: QtGui.QColor, palette: list[QtGui.QColor]) -> bool:
    return any(contrast_ratio(color, other) < SAME for other in palette)


def _name(widget: QtWidgets.QWidget) -> str:
    own = widget.objectName()
    return f"{type(widget).__name__}({own})" if own else type(widget).__name__


def _sampled(page: QtWidgets.QWidget) -> list[QtWidgets.QWidget]:
    """What a page is point-sampled at: its own ground, each stage, and the demo in each stage."""
    out: list[QtWidgets.QWidget] = [page]
    inner = page.scroll.widget()
    if inner is not None:
        out.append(inner)
    for stage in getattr(page, "stages", []):
        out.append(stage)
        out.extend(
            child for child in stage.findChildren(QtWidgets.QWidget)
            if child.objectName() == "demo-body"
        )
        demo = getattr(stage, "widget", None)
        if isinstance(demo, QtWidgets.QWidget):
            out.append(demo)
            out.extend(
                child for child in demo.findChildren(QtWidgets.QWidget)
                if child.parentWidget() is demo
            )
    return out


def _fault(
    widget: QtWidgets.QWidget,
    at: tuple[float, float],
    color: QtGui.QColor,
    palette: list[QtGui.QColor],
    page_ground: QtGui.QColor,
    surface: str,
) -> dict | None:
    """What is wrong with one sample, or nothing.

    Two things are wrong with a ground in dark. It is light, which is a grey a host style or the
    application's own palette filled where a token should have. Or it is the page's own
    `background` standing on a surface the theme calls `popover`, which is the light theme's
    reading kept: there `background` and `popover` are the same white and the mistake shows
    nowhere, and in dark the panel reads as a hole cut in the surface around it.
    """
    if _luminance(color) >= LIGHT and not _is_token(color, palette):
        return {
            "widget": _name(widget),
            "at": [round(at[0], 2), round(at[1], 2)],
            "ground": color.name(),
            "luminance": round(_luminance(color), 3),
            "why": "a light ground on a dark page, and no token of the theme carries it",
        }
    if surface == "popover" and contrast_ratio(color, page_ground) < SAME:
        return {
            "widget": _name(widget),
            "at": [round(at[0], 2), round(at[1], 2)],
            "ground": color.name(),
            "luminance": round(_luminance(color), 3),
            "why": "the page's own `background` painted on a surface standing on `popover`",
        }
    return None


def _sample(
    window: QtWidgets.QWidget,
    widgets: list[QtWidgets.QWidget],
    palette: list[QtGui.QColor],
    page_ground: QtGui.QColor,
    surface: str = "background",
) -> list[dict]:
    """Point-sample those widgets out of one window's own picture.

    A popover is a top-level of its own and paints its own surface, so what is under a widget
    inside one is read from that window rather than from the page behind it.

    A point another widget covers is passed over: what is painted there is that widget's
    business, and a thumbnail, an avatar or a status badge is a colour the site sends rather
    than a token. Each of those widgets is sampled in its own turn, where nothing covers it.
    """
    shot = window.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    out: list[dict] = []
    seen: set[int] = set()
    for widget in widgets:
        if id(widget) in seen:
            continue
        seen.add(id(widget))
        if not widget.isVisible() or widget.width() < 8 or widget.height() < 8:
            continue
        region = widget.visibleRegion().boundingRect()
        if region.width() < 8 or region.height() < 8:
            continue
        origin = widget.mapTo(window, region.topLeft())
        taken: list[tuple[tuple[float, float], QtGui.QColor]] = []
        for across, down in POINTS:
            local = QtCore.QPoint(
                region.x() + int(region.width() * across), region.y() + int(region.height() * down)
            )
            if widget.childAt(local) is not None:
                continue
            point = QtCore.QPoint(
                origin.x() + int(region.width() * across), origin.y() + int(region.height() * down)
            )
            if not shot.rect().contains(point):
                continue
            packed = shot.pixel(point)
            if (packed >> 24) & 0xFF < 200:  # The room a translucent window keeps for its shadow.
                continue
            taken.append(
                ((across, down), QtGui.QColor((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF))
            )
        counts = Counter(color.rgb() for _at, color in taken)
        for at, color in taken:
            # A ground is a colour the widget wears at more than one of its points. A glyph, a
            # row of chips and a picture are a different colour at each, and reading one of
            # those as the widget's ground is how a sweep of a page full of thumbnails and
            # status colour fills itself with faults that are not there.
            if counts[color.rgb()] < AGREE:
                continue
            found = _fault(widget, at, color, palette, page_ground, surface)
            if found is not None:
                found["points"] = counts[color.rgb()]
                out.append(found)
                break
    return out


def _surface_of(window: QtWidgets.QWidget, theme: object) -> str:
    """Which token a floating window's own stylesheet says it stands on."""
    return "popover" if window.styleSheet() == generate_qss(theme, "popover") else "background"


def ground_faults(page: QtWidgets.QWidget) -> list[dict]:
    """Every ground on screen that reads wrong where the theme the page wears is dark.

    The page's own ground, the stage of every demo on it and the widget each stage holds, and
    every floating surface standing over them with what it carries, each at nine points.
    """
    theme = theme_of(page)
    if not getattr(theme, "dark", False):
        return []
    palette = _token_colors(theme)
    ground = to_color(theme.background)
    out = _sample(page.window(), _sampled(page), palette, ground)
    for other in QtWidgets.QApplication.topLevelWidgets():
        # A tooltip and a menu carry no theme of their own to read, so they are sampled against
        # the page's: a light ground under one is the defect whatever it thinks it is wearing.
        if not other.isVisible() or isinstance(other, QtWidgets.QMainWindow):
            continue
        inside = [one for one in other.findChildren(QtWidgets.QWidget) if one.isVisible()]
        out.extend(
            _sample(other, [other, *inside[:INSIDE]], palette, ground, _surface_of(other, theme))
        )
    return out


def _lines(page: QtWidgets.QWidget) -> list[str]:
    """Both readings of one screenful: the point-sampled grounds and `_ink.py`'s three passes."""
    out = [
        f"{one['widget']} at {one['at']}: ground {one['ground']} "
        f"(luminance {one['luminance']}) -- {one['why']}"
        for one in ground_faults(page)
    ]
    out.extend(faults())
    return out


def _wait_ready(page: QtWidgets.QWidget, wait) -> bool:
    """Spin until every stage on the page has settled its first read, or the budget is out."""
    spent = 0
    while not page.ready and spent < READY_MS:
        wait(100)
        spent += 100
    wait(150)
    return bool(page.ready)


def _walk(page: QtWidgets.QWidget, wait) -> dict[str, str]:
    """A page read a screenful at a time, as the line and the state each fault was seen in."""
    seen: dict[str, str] = {}
    bar = page.scroll.verticalScrollBar()
    offset = 0
    while True:
        bar.setValue(offset)
        wait(200)
        for line in _lines(page):
            seen.setdefault(line, f"at {offset}")
        if offset >= bar.maximum():
            break
        offset = min(bar.maximum(), offset + STEP)
    bar.setValue(0)
    wait(100)
    return seen


# --- the surfaces a walk cannot reach ----------------------------------------------------------


def _first(page: QtWidgets.QWidget, wanted: str) -> QtWidgets.QWidget | None:
    """The first visible widget on the page whose class is named `wanted`."""
    for widget in page.findChildren(QtWidgets.QWidget):
        if not widget.isVisible():
            continue
        if any(base.__name__ == wanted for base in type(widget).__mro__):
            return widget
    return None


def _openable(page: QtWidgets.QWidget) -> QtWidgets.QWidget | None:
    """The outermost widget on the page that opens a surface of its own."""
    found = [
        widget
        for widget in page.findChildren(QtWidgets.QWidget)
        if widget.isVisible() and callable(getattr(type(widget), "set_open", None))
    ]
    for widget in found:
        if not any(other is not widget and other.isAncestorOf(widget) for other in found):
            return widget
    return None


def _scroll_to(page: QtWidgets.QWidget, widget: QtWidgets.QWidget, wait) -> None:
    inner = page.scroll.widget()
    try:
        top = widget.mapTo(inner, widget.rect().topLeft()).y()
    except RuntimeError:
        return
    page.scroll.verticalScrollBar().setValue(max(0, top - 120))
    wait(200)


def _floating() -> list[str]:
    """Every top-level window on show that is not the showcase, by class and name."""
    return [
        _name(one)
        for one in QtWidgets.QApplication.topLevelWidgets()
        if one.isVisible() and not isinstance(one, QtWidgets.QMainWindow)
    ]


def _open_surface(page, wait, kind: str) -> tuple[list[str], dict]:
    """Open one surface of that kind on the page, read it, and close it again.

    The report keeps what stood on screen while it was read, because a surface that never
    opened is a check that never ran rather than a check that passed.
    """
    if kind == "tooltip":
        holder = None
        for widget in page.findChildren(QtWidgets.QWidget):
            if widget.isVisible() and widget.toolTip():
                holder = widget
                break
        if holder is None:
            return [], {"opened": False, "why": "nothing on the page carries a tooltip"}
        _scroll_to(page, holder, wait)
        where = holder.mapToGlobal(holder.rect().center())
        QtWidgets.QToolTip.showText(where, holder.toolTip(), holder)
        wait(SETTLE_MS)
        standing = _floating()
        lines = _lines(page)
        QtWidgets.QToolTip.hideText()
        wait(200)
        return lines, {"opened": bool(standing), "on": _name(holder), "windows": standing}

    if kind == "menu":
        # The menu surface is `dropdown_menu.py`'s, and a `Select` is what every page carries
        # one of: the stage toolbar sets the view through them.
        select = _first(page, "Select")
        if select is None:
            return [], {"opened": False, "why": "no select on the page to open a menu from"}
        _scroll_to(page, select, wait)
        select.open()
        wait(SETTLE_MS)
        standing = _floating()
        lines = _lines(page)
        select.close()
        wait(250)
        return lines, {"opened": bool(standing), "on": _name(select), "windows": standing}

    if kind == "editor":
        # A field editor set to edit opens a popover holding a label, a field and two buttons,
        # which is the one surface on any page where a box a reader types into stands on
        # `popover` rather than on the page.
        editor = None
        for widget in page.findChildren(QtWidgets.QWidget):
            if (
                widget.isVisible()
                and "popover" in widget.objectName()
                and callable(getattr(type(widget), "set_mode", None))
            ):
                editor = widget
                break
        if editor is None:
            return [], {"opened": False, "why": "no editor on the page opens in a popover"}
        _scroll_to(page, editor, wait)
        editor.set_mode("edit")
        wait(SETTLE_MS)
        standing = _floating()
        lines = _lines(page)
        editor.set_mode("display")
        wait(250)
        return lines, {"opened": bool(standing), "on": _name(editor), "windows": standing}

    widget = _openable(page)
    if widget is None:
        return [], {"opened": False, "why": "nothing on the page opens a surface"}
    _scroll_to(page, widget, wait)
    try:
        widget.set_open(True)
        wait(SETTLE_MS)
        if not getattr(widget, "open", False):
            return [], {"opened": False, "why": f"{_name(widget)} refused to open"}
        standing = _floating()
        lines = _lines(page)
        widget.set_open(False)
    except (RuntimeError, TypeError) as error:
        return [], {"opened": False, "why": f"{type(error).__name__}: {error}"}
    wait(250)
    return lines, {"opened": bool(standing), "on": _name(widget), "windows": standing}


#: One page per kind of surface a walk cannot reach, and what it is called in the report.
DEMAND = (
    ("popover", "widgets/entity-picker"),
    ("dialog", "widgets/filter-dialog"),
    ("menu", "widgets/entity-table"),
    ("palette", "widgets/global-search"),
    ("tooltip", "widgets/status-badge"),
    ("editor", "widgets/field-editor"),
)


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    window = page.window()
    window.raise_()
    window.activateWindow()
    QtWidgets.QApplication.setActiveWindow(window)
    wait(200)

    pages: dict[str, dict] = {}
    for name in window.page_names():
        try:
            current = window.open_page(name)
            ready = _wait_ready(current, wait)
            seen = _walk(current, wait)
        except (RuntimeError, TypeError, ValueError) as error:
            pages[name] = {"error": f"{type(error).__name__}: {error}"}
            continue
        pages[name] = {
            "ready": ready,
            "stages": len(current.stages),
            "faults": [f"{line}   [{state}]" for line, state in sorted(seen.items())],
        }

    for kind, name in DEMAND:
        try:
            current = window.open_page(name)
            _wait_ready(current, wait)
            lines, how = _open_surface(current, wait, kind)
        except (RuntimeError, TypeError, ValueError) as error:
            pages[f"{name} [{kind}]"] = {"error": f"{type(error).__name__}: {error}"}
            continue
        pages[f"{name} [{kind}]"] = dict(how, faults=sorted(set(lines)))

    # A page with nothing to say is left out; a surface that had to be opened is kept either
    # way, because `opened: false` is a check that never ran rather than a check that passed.
    shown = {
        name: seen
        for name, seen in pages.items()
        if seen.get("faults") or seen.get("error") or "opened" in seen
    }
    count = sum(len(seen.get("faults") or []) for seen in pages.values())
    broken = sum(1 for seen in pages.values() if seen.get("faults") or seen.get("error"))
    if broken:
        return {
            "verdict": f"FAIL {count} grounds and inks read light across {broken} pages",
            "pages": shown,
            "walked": len(pages),
        }
    return {
        "verdict": f"PASS every ground and ink on {len(pages)} pages reads as dark",
        "pages": shown,
        "walked": len(pages),
    }
