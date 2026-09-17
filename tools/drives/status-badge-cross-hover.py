"""The state matrix: the cross of a badge and of a chip under the pointer.

    .venv/bin/python tools/qa.py --page status-badge \
      --drive tools/drives/status-badge-cross-hover.py --shot /tmp/status-badge-cross-hover.png

This state has no upstream twin that a drive can reach: `hover:bg-current/8` is a CSS state, and a
dispatched event sets none, so upstream's own hover is read off `REMOVE_CONTROL` rather than off a
shot. What the shot shows here is the wash a hovered cross draws: the badge's own foreground at
8%, never the destructive tint (rule 5), and the glyph at full opacity rather than 70%.
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.widgets.status_badge import StatusBadge


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    badges = [b for b in find(StatusBadge, all=True) if b.removable and b.variant == "both"]
    if not badges:
        return {"verdict": "FAIL the page drew no removable badge"}
    badge = badges[0]
    where = badge._cross_box().center()
    QtWidgets.QApplication.sendEvent(
        badge,
        QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove,
            QtCore.QPointF(where),
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
        ),
    )
    wait(250)
    return {
        "verdict": (
            "PASS the cross is washed with the badge's own foreground"
            if badge._cross_hovered
            else "FAIL the cross did not take the hover"
        ),
        "seen": {"wash": round(badge._cross_hover.value, 2)},
    }
