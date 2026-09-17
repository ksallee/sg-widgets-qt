"""The state matrix: the remove control of a status badge holding keyboard focus.

    .venv/bin/python tools/qa.py --page status-badge \
      --drive tools/drives/status-badge-cross-focus.py --shot /tmp/status-badge-cross-focus.png

The twin of `tools/drives/upstream/status-badge-cross-focus.js`. Upstream the ring is
`focus-visible:ring-2 focus-visible:ring-offset-2` of `REMOVE_CONTROL`, which a browser only
paints when it decides the focus came from a key; here rule 5 says the same thing outright, so
the badge is given focus by a key reason and the ring is painted around the cross's own box.
"""
from __future__ import annotations

from qtpy import QtCore

from sg_widgets_qt.widgets.status_badge import StatusBadge


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    badges = [b for b in find(StatusBadge, all=True) if b.removable and b.variant == "both"]
    if not badges:
        return {"verdict": "FAIL the page drew no removable badge"}
    badge = badges[0]
    rest = badge.grab().toImage()
    badge.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    wait(250)
    focused = badge.grab().toImage()
    ringed = focused != rest
    return {
        "verdict": (
            "PASS the cross takes the focus ring on a keyboard focus"
            if badge.keyboard_focus and ringed
            else "FAIL the cross drew no ring on a keyboard focus"
        ),
        "seen": {
            "keyboard_focus": badge.keyboard_focus,
            "repainted": ringed,
            "cross": list(badge._cross_box().getRect()),
        },
    }
