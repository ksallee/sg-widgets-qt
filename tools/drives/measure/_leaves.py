"""What the Foundations and Display parity drives share: the Qt half of the measurement.

The twin of `tools/drives/upstream/measure/_leaves.js`, which reads the same numbers off the
upstream DOM. A drive is exec'd by `tools/qa.py`, so it puts this directory on `sys.path`
itself before importing this module:

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _leaves import measure_page, measure_popups

A Qt widget has no computed style, so the colours come off a grab: `paint` holds the pixel at
the centre and one step in from each edge, which is what the upstream `getComputedStyle`
colours composite to. Padding is the widget's own `contentsMargins` and its layout's, and the
gap is that layout's spacing, which is where a Qt surface keeps what CSS calls padding and gap.
"""
from __future__ import annotations

from qtpy import QtCore, QtWidgets

__all__ = ["measure_page", "measure_popups", "widget_record", "colour_at"]


def _hex(colour) -> str:
    return f"#{colour.red():02x}{colour.green():02x}{colour.blue():02x}"


def colour_at(image, x: int, y: int) -> str:
    """The painted colour of one point of a grab, as #rrggbb."""
    ratio = image.devicePixelRatio() or 1.0
    px = int(round(x * ratio))
    py = int(round(y * ratio))
    if px < 0 or py < 0 or px >= image.width() or py >= image.height():
        return ""
    return _hex(image.pixelColor(px, py))


def _font_of(widget) -> dict:
    font = QtWidgets.QWidget.font(widget)
    size = font.pixelSize()
    if size <= 0:
        size = int(round(font.pointSizeF() * QtWidgets.QWidget.logicalDpiY(widget) / 72.0))
    return {"px": size, "weight": int(font.weight()), "family": font.family()}


def _probes(width: int, height: int) -> dict:
    """Where a colour is read: the centre, and one step in from each edge."""
    return {
        "centre": (width // 2, height // 2),
        "top": (width // 2, 1),
        "left": (1, height // 2),
        "right": (max(0, width - 2), height // 2),
        "bottom": (width // 2, max(0, height - 2)),
        "inset": (min(max(0, width - 1), 4), min(max(0, height - 1), 4)),
    }


#: Our widgets carry props named `size`, `text` and `state`, which shadow `QWidget`'s own
#: methods, so every geometry call here goes through the unbound `QWidget` method.
W = QtWidgets.QWidget


def widget_record(widget, origin, image) -> dict:
    """One widget, measured the way the DOM walk measures an element."""
    at = QtCore.QPoint(0, 0) if widget is origin else W.mapTo(widget, origin, QtCore.QPoint(0, 0))
    size = W.size(widget)
    own = W.contentsMargins(widget)
    layout = W.layout(widget)
    record = {
        "slot": W.objectName(widget) or None,
        "cls": type(widget).__name__,
        "box": {"x": at.x(), "y": at.y(), "w": size.width(), "h": size.height()},
        "pad": [own.top(), own.right(), own.bottom(), own.left()],
        "font": _font_of(widget),
        "enabled": W.isEnabled(widget),
        "hint": [W.sizeHint(widget).width(), W.sizeHint(widget).height()],
        "text": "",
    }
    if layout is not None:
        inset = layout.contentsMargins()
        record["layout"] = {
            "cls": type(layout).__name__,
            "gap": layout.spacing(),
            "pad": [inset.top(), inset.right(), inset.bottom(), inset.left()],
        }
    else:
        record["layout"] = None
    for name in ("text", "placeholderText"):
        found = getattr(widget, name, None)
        if callable(found):
            try:
                value = found()
            except TypeError:
                continue
            if isinstance(value, str) and value:
                record["text"] = value[:80]
                break
    if image is not None:
        record["paint"] = {
            where: colour_at(image, at.x() + px, at.y() + py)
            for where, (px, py) in _probes(size.width(), size.height()).items()
        }
    # The props a leaf names itself by, which is how a record is matched to its upstream twin.
    for prop in ("size", "radius", "aspect", "variant", "state", "pad", "density", "step", "tone"):
        got = getattr(widget, prop, None)
        if isinstance(got, (str, bool, int, float)):
            record[prop] = got
    return record


def _wanted(widget) -> bool:
    """A widget worth a record: one of ours, one that is named, or one that carries text."""
    if type(widget).__module__.startswith("sg_widgets_qt"):
        return True
    if W.objectName(widget):
        return True
    return isinstance(widget, (QtWidgets.QLabel, QtWidgets.QAbstractButton, QtWidgets.QLineEdit))


def measure_page(page, image=None) -> dict:
    """Every visible widget under `page`, measured against the page's own top left."""
    if image is None:
        image = W.grab(page).toImage()
    rows = [
        widget_record(widget, page, image)
        for widget in [page, *page.findChildren(QtWidgets.QWidget)]
        if W.isVisible(widget) and W.width(widget) > 0 and W.height(widget) > 0 and _wanted(widget)
    ]
    verdict = f"PASS measured {len(rows)} widgets"
    return {"verdict": verdict, "count": len(rows), "elements": rows}


def measure_popups() -> list:
    """Every popup standing over the window, measured against its own top left.

    A popover here is a top-level window of its own, the way `tools/qa.py`'s `grab_with_popups`
    finds it, so the upstream portalled content has a twin to be read against.
    """
    out = []
    for other in QtWidgets.QApplication.topLevelWidgets():
        if not W.isVisible(other) or W.width(other) <= 0 or W.height(other) <= 0:
            continue
        if W.objectName(other) == "showcase":
            continue
        image = W.grab(other).toImage()
        out.append(
            {
                "top": W.objectName(other) or type(other).__name__,
                "box": [W.width(other), W.height(other)],
                "elements": [
                    widget_record(widget, other, image)
                    for widget in [other, *other.findChildren(QtWidgets.QWidget)]
                    if W.isVisible(widget)
                    and W.width(widget) > 0
                    and W.height(widget) > 0
                    and _wanted(widget)
                ],
            }
        )
    return out
