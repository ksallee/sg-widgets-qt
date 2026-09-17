"""field-value: every data type drawn as a value, and the same values through the delegate.

    .venv/bin/python tools/qa.py --page field-value --drive tools/drives/walk/field-value.py

A value is display, so the walk reads what the table claims: one row a data type, the status drawn
as its badge, a link drawn as a chip, a picture as a thumbnail, and the empty and sentinel cases
saying so rather than drawing nothing. The density is the one step a value takes, so it is moved
and the rows are measured again; the delegate face below is measured beside the widgets above.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, popups, set_view, wait_for  # noqa: E402

from sg_widgets_qt.images import image_loader  # noqa: E402
from sg_widgets_qt.widgets.entity_chip import EntityChip  # noqa: E402
from sg_widgets_qt.widgets.status_badge import StatusBadge  # noqa: E402
from sg_widgets_qt.widgets.thumbnail import Thumbnail  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("field-value-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no field-value demo"}
    wait_for(lambda: demo.demo_ready(), wait, 25000)
    wait_for(lambda: image_loader().pending == 0, wait, 20000)
    wait(300)

    values = list(demo._values)  # noqa: SLF001
    walk.check("the table draws a value a data type", len(values) >= 15, ">= 15", len(values))
    kinds = sorted({one.data_type for one in values})
    walk.check("more than a dozen data types are on show", len(kinds) >= 12, ">= 12", kinds)
    walk.check(
        "every value is given room",
        all(one.height() > 0 for one in values),
        "room for each",
        [one.data_type for one in values if one.height() <= 0],
    )

    # --- the types that draw a widget of their own ---------------------------------------------
    badges = demo.findChildren(StatusBadge)
    walk.check("a status draws its badge", badges, "a badge", len(badges))
    walk.check(
        "the badge names the status",
        all(one.status_text for one in badges),
        "a name on each",
        [one.code for one in badges if not one.status_text],
    )
    chips = demo.findChildren(EntityChip)
    walk.check("a link draws its chip", chips, "a chip", len(chips))
    walk.check(
        "every chip names the row it points at",
        all(one.label for one in chips),
        "a name on each",
        [one.label for one in chips if not one.label],
    )
    pictures = demo.findChildren(Thumbnail)
    walk.check("a picture draws its thumbnail", pictures, "a thumbnail", len(pictures))
    walk.check(
        "no thumbnail is left loading",
        not any(one.loading for one in pictures),
        "nothing loading",
        [one.alt for one in pictures if one.loading],
    )

    # --- the empty and sentinel cases -------------------------------------------------------------
    empty = [one for one in values if one.value in (None, "", [])]
    walk.check("the table carries the empty cases", empty, "an empty value", len(empty))
    walk.check(
        "an empty value still takes a line rather than collapsing",
        all(one.height() > 0 for one in empty),
        "room for each",
        [(one.data_type, one.height()) for one in empty if one.height() <= 0],
    )

    # --- the delegate face draws the same rows ------------------------------------------------------
    delegate = find("field-value-delegate")
    walk.check("the delegate face stands under the table", delegate is not None, True, delegate)
    if delegate is not None:
        walk.check("the delegate face is given room", delegate.height() > 0, "> 0", delegate.height())
        walk.check(
            "the delegate draws a row a data type",
            len(delegate._rows) == len(values),  # noqa: SLF001
            len(values),
            len(delegate._rows),  # noqa: SLF001
        )

    # --- the density is the one step a value takes -----------------------------------------------------
    tall = [one.height() for one in values]
    deep = delegate.height() if delegate is not None else 0
    missed = set_view(page, wait, density="compact")
    walk.same("header: the density moved", [], missed)
    again = find("field-value-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready(), wait, 25000)
        wait_for(lambda: image_loader().pending == 0, wait, 20000)
        wait(400)
        compact = list(again._values)  # noqa: SLF001
        walk.check(
            "header: every value wears the compact density",
            all(one.density == "compact" for one in compact),
            "compact",
            sorted({one.density for one in compact}),
        )
        shorter = sum(one.height() for one in compact)
        walk.check(
            "header: compact draws the rows a step smaller",
            shorter < sum(tall),
            f"< {sum(tall)}",
            shorter,
        )
        face = find("field-value-delegate")
        if face is not None and deep:
            walk.check(
                "header: the delegate face follows the density too",
                face.height() < deep,
                f"< {deep}",
                face.height(),
            )

    missed = set_view(page, wait, theme="dark", size="lg")
    walk.same("header: the theme and the size moved", [], missed)
    once_more = find("field-value-demo")
    walk.check("header: the demo survived again", once_more is not None, True, once_more)
    if once_more is not None:
        wait_for(lambda: once_more.demo_ready(), wait, 25000)
        wait(300)
        walk.check(
            "header: the values came back with their widgets",
            once_more.findChildren(StatusBadge) and once_more.findChildren(EntityChip),
            "a badge and a chip",
            (len(once_more.findChildren(StatusBadge)), len(once_more.findChildren(EntityChip))),
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS a value is drawn for every data type, a status draws its badge, a link its chip and"
        " a picture its thumbnail, the empty cases still take a line, the delegate face draws the"
        " same rows, and the density moves both of them a step"
    )
