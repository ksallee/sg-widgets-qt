"""Measure one picker or query page the way the browser is measured upstream.

The upstream half is `tools/drives/upstream/measure/<page>.js`, which walks the react pane and
the portalled popup and answers a rect and the painted styles for every `data-slot`. This is the
same walk over the Qt tree: every widget with an object name, the chips and badges that carry
none, the rows a delegate paints and the sub-rects inside a row, at rest and open, in light and
in dark, so `tools/measure_diff.py` can read the two side by side.

    QA_MEASURE_OPEN=picker .venv/bin/python tools/qa.py --page entity-picker \\
        --drive tools/drives/measure/_pickers.py > out.json
    python tools/measure_split.py tools/drives/measure entity-picker < out.json

A row is painted, not laid out, so its sub-rects are read by wrapping the delegate's own paint
helpers for one forced repaint and keeping the rectangles they were handed. Nothing in the
package changes: the wrappers are put back before the measurement returns.
"""
from __future__ import annotations

import os

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from sg_widgets_qt.primitives.list_view import ListSurface
from sg_widgets_qt.primitives.row_delegate import RowDelegate

#: What `open_it` does on a page, keyed by `QA_MEASURE_OPEN`.
OPEN_KINDS = ("picker", "trigger", "still", "tree", "editor")

#: A widget with no object name is still worth a line when its class is one the upstream DOM
#: gives a slot to — a chip, a badge, a skeleton — so the inline insets can be read.
NAMELESS = ("Chip", "Badge", "Skeleton", "Avatar", "Thumbnail", "StateLine", "Pill")


def _kind() -> str:
    wanted = os.environ.get("QA_MEASURE_OPEN", "picker").strip().lower()
    return wanted if wanted in OPEN_KINDS else "picker"


# --- reading a widget -------------------------------------------------------------------


def _hex(color: QtGui.QColor) -> str:
    return f"#{color.red():02x}{color.green():02x}{color.blue():02x}{color.alpha():02x}"


def _sample(shot: QtGui.QImage, x: int, y: int) -> str:
    if shot.isNull() or not (0 <= x < shot.width() and 0 <= y < shot.height()):
        return ""
    return _hex(QtGui.QColor(shot.pixel(x, y)))


def _font(widget: QtWidgets.QWidget) -> tuple[int, int]:
    font = widget.font()
    size = font.pixelSize()
    if size <= 0:
        size = int(round(font.pointSizeF() * 96.0 / 72.0))
    return size, int(font.weight())


def _text_of(widget: QtWidgets.QWidget) -> str:
    for name in ("text", "placeholder", "label"):
        found = getattr(widget, name, None)
        if callable(found):
            try:
                value = found()
            except TypeError:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()[:48]
        elif isinstance(found, str) and found.strip():
            return found.strip()[:48]
    return ""


def _record(widget: QtWidgets.QWidget, root: QtWidgets.QWidget, where: str, shot) -> dict:
    top_left = widget.mapTo(root, QtCore.QPoint(0, 0))
    size, weight = _font(widget)
    box = widget.rect()
    # An icon control's widget is its hit box, which takes no room and is not what is drawn.
    # The upstream walk sees the painted box, so this one answers that.
    side = getattr(widget, "box_side", None)
    if callable(side):
        painted = QtCore.QRect(0, 0, side(), side())
        painted.moveCenter(box.center())
        top_left += painted.topLeft()
        box = QtCore.QRect(0, 0, painted.width(), painted.height())
    return {
        "slot": widget.objectName(),
        "cls": type(widget).__name__,
        "where": where,
        "x": top_left.x(),
        "y": top_left.y(),
        "w": box.width(),
        "h": box.height(),
        "text": _text_of(widget),
        "font-size": size,
        "font-weight": weight,
        "paint-corner": _sample(shot, top_left.x() + 1, top_left.y() + 1),
        "paint-mid": _sample(shot, top_left.x() + box.width() // 2, top_left.y() + box.height() // 2),
        "paint-right": _sample(shot, top_left.x() + box.width() - 2, top_left.y() + 2),
    }


def _walk(root: QtWidgets.QWidget, where: str) -> list[dict]:
    shot = root.grab().toImage()
    found = [_record(root, root, where, shot)]
    for widget in root.findChildren(QtWidgets.QWidget):
        if not widget.isVisible():
            continue
        if widget.objectName():
            found.append(_record(widget, root, where, shot))
            continue
        cls = type(widget).__name__
        if any(one in cls for one in NAMELESS):
            one = _record(widget, root, where, shot)
            one["slot"] = "~" + cls.lstrip("_")
            found.append(one)
    return found


# --- the rows a delegate paints ---------------------------------------------------------


class _Capture:
    """The rectangles a `RowDelegate` is handed for one forced repaint."""

    PARTS = (("lead", "_paint_lead"), ("text", "_paint_text"),
             ("checkbox", "_paint_checkbox"), ("tick", "_paint_tick"))

    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self._patched: list[tuple[str, object]] = []

    def _keep(self, row: int, part: str, rect: QtCore.QRect) -> None:
        self.rows.setdefault(row, {})[part] = [rect.x(), rect.y(), rect.width(), rect.height()]

    def install(self) -> None:
        keep = self._keep
        for part, name in self.PARTS:
            original = getattr(RowDelegate, name)
            self._patched.append((name, original))

            def wrapper(self_, painter, rect, index, *rest, _o=original, _p=part):
                if isinstance(index, QtCore.QModelIndex) and index.isValid():
                    keep(index.row(), _p, rect)
                return _o(self_, painter, rect, index, *rest)

            setattr(RowDelegate, name, wrapper)

    def remove(self) -> None:
        for name, original in self._patched:
            setattr(RowDelegate, name, original)
        self._patched = []


def _rows(surface: ListSurface, root: QtWidgets.QWidget, where: str) -> list[dict]:
    model = surface.model()
    if model is None:
        return []
    capture = _Capture()
    capture.install()
    try:
        surface.viewport().repaint()
    finally:
        capture.remove()
    delegate = surface.row_delegate()
    slot = surface.objectName() or "list"
    base = surface.viewport().mapTo(root, QtCore.QPoint(0, 0))
    out: list[dict] = []
    for row in range(min(model.rowCount(), 24)):
        index = model.index(row, 0)
        rect = surface.visualRect(index)
        if rect.height() <= 0:
            continue
        kind = "more" if surface.is_load_more(row) else "option"
        option = QtWidgets.QStyleOptionViewItem()
        option.rect = rect
        option.widget = surface
        hint = delegate.sizeHint(option, index)
        out.append({
            "slot": f"{slot}-{kind}", "cls": "row", "where": where, "row": row,
            "x": rect.x() + base.x(), "y": rect.y() + base.y(),
            "w": rect.width(), "h": rect.height(), "hint-h": hint.height(),
            "text": str(index.data(Qt.ItemDataRole.DisplayRole) or "")[:48],
        })
        for part, box in sorted(capture.rows.get(row, {}).items()):
            out.append({
                "slot": f"picker-row-{part}", "cls": "row-part", "where": where, "row": row,
                "x": box[0] + base.x(), "y": box[1] + base.y(), "w": box[2], "h": box[3],
                "text": "",
            })
    return out


def _views(root: QtWidgets.QWidget, where: str) -> list[dict]:
    """The header and the first cells of every table-shaped view under `root`."""
    out: list[dict] = []
    for view in root.findChildren(QtWidgets.QTableView):
        if not view.isVisible():
            continue
        base = view.viewport().mapTo(root, QtCore.QPoint(0, 0))
        head = view.horizontalHeader()
        slot = view.objectName() or "table"
        if head is not None and head.isVisible():
            corner = head.mapTo(root, QtCore.QPoint(0, 0))
            out.append({
                "slot": f"{slot}-header", "cls": "header", "where": where,
                "x": corner.x(), "y": corner.y(), "w": head.width(), "h": head.height(),
                "text": "",
            })
        model = view.model()
        if model is None:
            continue
        for row in range(min(model.rowCount(), 6)):
            for column in range(min(model.columnCount(), 8)):
                rect = view.visualRect(model.index(row, column))
                if rect.width() <= 0 or rect.height() <= 0:
                    continue
                out.append({
                    "slot": f"{slot}-cell", "cls": "cell", "where": where,
                    "row": row, "column": column,
                    "x": rect.x() + base.x(), "y": rect.y() + base.y(),
                    "w": rect.width(), "h": rect.height(),
                    "text": str(model.index(row, column).data() or "")[:24],
                })
    return out


# --- one measurement --------------------------------------------------------------------


def _tokens(page: QtWidgets.QWidget) -> dict:
    from sg_widgets_qt.theme import theme_of

    theme = theme_of(page)
    names = (
        "background", "foreground", "muted", "muted_foreground", "accent", "accent_foreground",
        "popover", "popover_foreground", "border", "input", "ring", "destructive",
        "secondary", "secondary_foreground",
    )
    found = {name: _hex(theme.color(name)) for name in names}
    found["radius"] = theme.radius_px("lg")
    found["radius-sm"] = theme.radius_px("sm")
    found["radius-md"] = theme.radius_px("md")
    return found


def _popups(window: QtWidgets.QWidget) -> list[QtWidgets.QWidget]:
    return [
        other
        for other in QtWidgets.QApplication.topLevelWidgets()
        if other is not window and other.isVisible() and other.width() > 0 and other.height() > 0
    ]


def measure(page: QtWidgets.QWidget, case: str) -> dict:
    window = page.window()
    elements: list[dict] = []
    for root, where in [(page, "pane"), *[(one, "popup") for one in _popups(window)]]:
        elements.extend(_walk(root, where))
        for surface in root.findChildren(ListSurface):
            if surface.isVisible():
                elements.extend(_rows(surface, root, where))
        elements.extend(_views(root, where))
    return {"case": case, "tokens": _tokens(page), "elements": elements}


# --- opening the page's surface ----------------------------------------------------------


def _live_controls(find) -> list:
    from sg_widgets_qt.widgets.picker_control import PickerControl

    return [
        control
        for control in find(PickerControl, all=True)
        if control.isVisible() and not control.disabled and not control.readonly
    ]


def _press(widget: QtWidgets.QWidget) -> None:
    from qtpy.QtTest import QTest

    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)


def open_it(page, wait, find) -> str:
    kind = _kind()
    if kind == "still":
        wait(200)
        return "still"
    if kind == "picker":
        found = _live_controls(find)
        if not found:
            return "no control"
        found[0].set_open(True)
        for _ in range(120):
            wait(50)
            if found[0].list_surface().row_count() > 0:
                break
        wait(700)
        return "picker"
    if kind == "tree":
        tree = find(QtWidgets.QTreeView)
        if tree is not None:
            tree.expandToDepth(1)
            wait(600)
        return "tree"
    if kind == "editor":
        for stage in page.stages:
            widget = stage.widget
            starter = getattr(widget, "begin_edit", None) or getattr(widget, "start_editing", None)
            if callable(starter):
                starter()
                wait(500)
                return "editor"
        return "no editor"
    wanted = ("-trigger", "-launch", "sort-trigger", "filter-pill")
    for widget in page.findChildren(QtWidgets.QWidget):
        name = widget.objectName()
        if widget.isVisible() and name and any(one in name for one in wanted):
            _press(widget)
            wait(700)
            return name
    return "no trigger"


def close_it(page, wait, find) -> None:
    from sg_widgets_qt.widgets.picker_control import PickerControl

    for control in find(PickerControl, all=True):
        if control.is_open:
            control.set_open(False)
    for other in _popups(page.window()):
        other.close()
    wait(250)


def drive(page, wait, find, prefs) -> dict:
    out: dict = {}
    for theme in ("light", "dark"):
        prefs.set("theme", theme)
        wait(500)
        out[f"rest-{theme}"] = measure(page, "rest")
        opened = open_it(page, wait, find)
        wait(400)
        out[f"open-{theme}"] = measure(page, "open")
        out[f"open-{theme}"]["opened"] = opened
        close_it(page, wait, find)
    return {"verdict": "PASS measured", "states": out}
