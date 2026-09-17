"""status-badge: take the crosses, read the labels, and prove an unknown code still reads.

    .venv/bin/python tools/qa.py --page status-badge --drive tools/drives/walk/status-badge.py

The badge is display, so what the page invites is the cross inside the pill, and reading what each
example claims: a name from the site, the code instead of the name, a label from the schema where
the site knows no status, and a code the site never heard of.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import (  # noqa: E402
    Walk,
    case_widget,
    click,
    click_chip_cross,
    key,
    popups,
    scroll_to,
    set_view,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.widgets.status_badge import StatusBadge  # noqa: E402


def badges_in(page, case: str) -> list:
    holder = case_widget(page, case)
    return list(holder.findChildren(StatusBadge)) if holder is not None else []


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    wait(500)
    demo = find("status-badge-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no status-badge demo"}

    # --- the site answered its statuses ------------------------------------------------------
    site = badges_in(page, "site")
    walk.check("site: the read answered this site's statuses", len(site) > 0, "> 0", len(site))
    walk.check(
        "site: every badge names its status",
        all(badge.status_text for badge in site),
        "a name on each",
        [badge.code for badge in site if not badge.status_text],
    )

    # --- the crosses -------------------------------------------------------------------------
    removable = [badge for badge in badges_in(page, "removable") if badge.removable]
    walk.check("removable: the example opens on badges that carry a cross", len(removable) >= 3, ">= 3", len(removable))
    scroll_to(page, removable[0], wait)
    named = removable[0].code
    walk.check("removable: the first badge carries a cross", click_chip_cross(removable[0]), True, False)
    wait(400)
    left = [badge for badge in badges_in(page, "removable") if badge.removable]
    walk.check(
        "removable: the cross takes that badge",
        named not in [badge.code for badge in left],
        f"no {named}",
        [badge.code for badge in left],
    )

    # The cross is a button, so the keyboard takes one with Enter, the way a button answers.
    pill = [badge for badge in left if badge.variant != "icon"]
    if pill:
        pill[0].setFocus(QtCore.Qt.FocusReason.TabFocusReason)
        held = pill[0].code
        key(pill[0], QtCore.Qt.Key.Key_Return)
        wait(400)
        walk.check(
            "removable: Enter on a focused badge takes it",
            held not in [badge.code for badge in badges_in(page, "removable")],
            f"no {held}",
            [badge.code for badge in badges_in(page, "removable")],
        )

    while True:
        pills = [
            badge
            for badge in badges_in(page, "removable")
            if badge.removable and badge.variant != "icon"
        ]
        if not pills:
            break
        click_chip_cross(pills[0])
        wait(300)
    back = find("put-them-back")
    walk.check("removable: the demo offers to put them back", back is not None, True, back)
    if back is not None:
        click(back)
        wait(400)
        walk.check(
            "removable: pressing it puts them all back",
            len([badge for badge in badges_in(page, "removable") if badge.removable]) >= 3,
            ">= 3",
            len([badge for badge in badges_in(page, "removable") if badge.removable]),
        )

    # --- the name, and the code instead --------------------------------------------------------
    labelled = badges_in(page, "label")
    walk.same("labels: the example holds two badges", 2, len(labelled))
    named_one, coded = labelled
    walk.check(
        "labels: the first reads the status's name",
        named_one.status_text and named_one.status_text != named_one.code,
        "a name, not the code",
        named_one.status_text,
    )
    walk.same("labels: the second reads the code instead", coded.code, coded.status_text)
    walk.same("labels: the name it hides is the tooltip", named_one.status_text, coded.other_text)

    # --- a code the site never heard of ----------------------------------------------------------
    unknown = badges_in(page, "unknown")
    walk.same("unknown: the example holds two badges", 2, len(unknown))
    from_schema, never_seen = unknown
    walk.check(
        "unknown: a code the schema names still reads",
        bool(from_schema.status_text),
        "a label",
        from_schema.status_text,
    )
    walk.same(
        "unknown: a code nobody knows falls back to the code itself",
        never_seen.code,
        never_seen.status_text,
    )

    # --- the bare glyphs, on the muted ground and on the status's own colour ----------------------
    for ground in ("muted", "color"):
        tile = find("glyph-" + ground)
        walk.check(f"glyph: the {ground} tile is drawn", tile is not None, True, tile)

    # --- the shipped statuses and icons, which need no site -----------------------------------------
    native = badges_in(page, "native")
    walk.check("shipped: the bundled statuses are drawn", len(native) > 0, "> 0", len(native))
    stock = badges_in(page, "stock")
    walk.check("shipped: the bundled icons are drawn", len(stock) > 0, "> 0", len(stock))

    # --- the view controls ---------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("status-badge-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    wait(700)
    rebuilt = [badge for badge in badges_in(page, "removable") if badge.removable]
    walk.check("header: the crosses came back with it", len(rebuilt) >= 3, ">= 3", len(rebuilt))
    if rebuilt:
        scroll_to(page, rebuilt[0], wait)
        held = rebuilt[0].code
        click_chip_cross(rebuilt[0])
        wait(400)
        walk.check(
            "header: a rebuilt cross still takes its badge",
            held not in [badge.code for badge in badges_in(page, "removable")],
            f"no {held}",
            [badge.code for badge in badges_in(page, "removable")],
        )
    sized = badges_in(page, "site")
    walk.check(
        "header: the site badges keep the size they named",
        all(badge.size == "sm" for badge in sized),
        "sm",
        sorted({badge.size for badge in sized}),
    )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the site's statuses read, a cross takes its own badge from the mouse and the"
        " keyboard and the demo puts them back, the name and the code both read, an unknown code"
        " still draws, and the page follows the view controls"
    )
