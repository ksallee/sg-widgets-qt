"""The collection demo's row height, its head and its footer, against the upstream DOM walk."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qtpy import QtWidgets  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    wait(800)
    view = None
    for widget in page.findChildren(QtWidgets.QAbstractItemView):
        if widget.model() is not None and widget.model().rowCount() > 0:
            view = widget
            break
    out: dict = {"verdict": "PASS"}
    if view is not None:
        model = view.model()
        rects = []
        for index in range(min(4, model.rowCount())):
            item = model.index(index, 0)
            box = view.visualRect(item)
            rects.append([box.x(), box.y(), box.width(), box.height()])
        out["rows"] = rects
        out["row_count"] = model.rowCount()
        out["viewport"] = [view.viewport().width(), view.viewport().height()]
    footer = find("review-queue-footer")
    if footer is not None:
        out["footer"] = {
            "height": footer.height(),
            "hint": footer.sizeHint().height(),
            "min": footer.minimumSizeHint().height(),
            "children": [
                [type(child).__name__, child.height(), child.sizeHint().height()]
                for child in footer.findChildren(QtWidgets.QWidget)
            ],
        }
    head = find("review-queue-head")
    if head is not None:
        margins = head.contentsMargins()
        layout = head.layout()
        inset = layout.contentsMargins() if layout is not None else margins
        out["head"] = {
            "height": head.height(),
            "hint": head.sizeHint().height(),
            "pad": [inset.top(), inset.right(), inset.bottom(), inset.left()],
        }
    return out
