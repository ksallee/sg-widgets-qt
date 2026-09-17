"""The first picker control on the page, open, measured against the upstream DOM walk."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _leaves import measure_page, measure_popups  # noqa: E402
from qtpy import QtWidgets  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    control = find("department-picker-control")
    if control is None:
        return {"verdict": "FAIL the page drew no picker control"}
    setter = getattr(control, "set_open", None)
    if callable(setter):
        setter(True)
    wait(600)
    out = measure_page(page)
    out["popups"] = measure_popups()
    rows = []
    for popup in QtWidgets.QApplication.topLevelWidgets():
        if not popup.isVisible() or popup.objectName() == "showcase":
            continue
        for view in popup.findChildren(QtWidgets.QAbstractItemView):
            model = view.model()
            if model is None or model.rowCount() == 0:
                continue
            for index in range(min(4, model.rowCount())):
                box = view.visualRect(model.index(index, 0))
                rows.append([box.x(), box.y(), box.width(), box.height()])
    out["rows"] = rows
    return out
