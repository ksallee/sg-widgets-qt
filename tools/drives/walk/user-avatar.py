"""user-avatar: the site's people, the initials behind them, and the accounts that are not people.

    .venv/bin/python tools/qa.py --page user-avatar --drive tools/drives/walk/user-avatar.py

An avatar is read, not pressed, so the walk reads what each example claims: a picture the site
named, the initials a person with none falls back to, the tint that keeps two people apart, the
inactive reading, a picture that will never load, and the script accounts. Every avatar names the
person it stands for, because an unnamed one is a picture nobody can read.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, case_widget, popups, set_view, wait_for  # noqa: E402

from sg_widgets_qt.images import image_loader  # noqa: E402
from sg_widgets_qt.widgets.user_avatar import UserAvatar  # noqa: E402


def avatars(root) -> list:
    return list(root.findChildren(UserAvatar)) if root is not None else []


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("user-avatar-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no user-avatar demo"}
    wait_for(lambda: demo.demo_ready(), wait, 25000)
    wait_for(lambda: image_loader().pending == 0, wait, 20000)
    wait(300)

    every = avatars(demo)
    walk.check("the page draws avatars", len(every) >= 8, ">= 8", len(every))
    # One avatar on the page has no name at all, which the docs call a muted circle; every other
    # one names the person it stands for and carries that name where a pointer can read it.
    named = [one for one in every if one.name]
    nameless = [one for one in every if not one.name]
    walk.same("one avatar is the demo's nameless case", 1, len(nameless))
    walk.check(
        "every named avatar carries its name as its tooltip",
        all(one.toolTip() for one in named),
        "a tooltip on each",
        [one.name for one in named if not one.toolTip()],
    )
    walk.check(
        "the nameless one is still a circle of its own",
        nameless[0].width() > 0 and nameless[0].pixmap is None,
        "a drawn circle",
        (nameless[0].width(), nameless[0].initials),
    )
    walk.check(
        "no avatar is left loading",
        not any(one.loading for one in every),
        "nothing loading",
        [one.name for one in every if one.loading],
    )

    # --- the ladder ------------------------------------------------------------------------------
    steps = sorted({one.size for one in every})
    walk.check("more than one step is on show", len(steps) >= 3, ">= 3", steps)
    widths = {step: max(one.width() for one in every if one.size == step) for step in steps}
    walk.check("each step is wider than the one under it", len(set(widths.values())) >= 3, ">= 3 widths", widths)

    # --- a picture the site named, and the initials behind one that has none --------------------------
    with_picture = [one for one in every if one.pixmap is not None]
    walk.check("a picture the site named landed", with_picture, "a picture", len(with_picture))
    without = [one for one in every if one.pixmap is None and not one.api_user and one.name]
    walk.check("a person with no picture falls back to initials", without, "an avatar", len(without))
    walk.check(
        "the initials are the person's own",
        all(1 <= len(one.initials) <= 2 for one in without),
        "one or two letters",
        [(one.name, one.initials) for one in without][:6],
    )

    # --- the tint keeps two people apart ------------------------------------------------------------------
    hues = {one.name: one.hue for one in without}
    walk.check("the tint is taken from the name", len(set(hues.values())) > 1, "> 1 hue", hues)

    # --- inactive, and a picture that will never load --------------------------------------------------------
    inactive = [one for one in every if one.inactive]
    walk.check("an inactive person is marked", inactive, "an avatar", [one.name for one in inactive])
    broken = [one for one in every if one.image and one.pixmap is None and one.name]
    walk.check(
        "a picture that will not load falls back rather than staying blank",
        broken and all(one.initials for one in broken),
        "initials",
        [(one.name, one.initials) for one in broken],
    )

    # --- the script accounts ----------------------------------------------------------------------------------
    api = avatars(case_widget(page, "api"))
    walk.check("the API example draws its avatars", len(api) >= 4, ">= 4", len(api))
    walk.check(
        "every one of them says it is not a person",
        all(one.api_user for one in api),
        "an API mark on each",
        [one.name for one in api if not one.api_user],
    )
    walk.check(
        "one of them is inactive as well",
        any(one.inactive for one in api),
        "an inactive one",
        [one.inactive for one in api],
    )

    # --- the view controls ------------------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("user-avatar-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready(), wait, 25000)
        wait_for(lambda: image_loader().pending == 0, wait, 20000)
        wait(300)
        rebuilt = avatars(again)
        walk.check("header: the avatars came back", len(rebuilt) >= 8, ">= 8", len(rebuilt))
        walk.check(
            "header: the pictures came back with them",
            any(one.pixmap is not None for one in rebuilt),
            "a picture",
            sum(1 for one in rebuilt if one.pixmap is not None),
        )
        walk.check(
            "header: the avatars wear the size step",
            any(one.size == "lg" for one in rebuilt),
            "lg",
            sorted({one.size for one in rebuilt}),
        )
        walk.check(
            "header: the API example keeps the steps it named",
            {one.size for one in avatars(case_widget(page, "api"))} >= {"sm", "md"},
            "sm and md",
            sorted({one.size for one in avatars(case_widget(page, "api"))}),
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the site's pictures landed, a person with none falls back to their own initials on"
        " a tint taken from the name, the inactive and the script accounts read as such, every"
        " avatar names its person, and they come back through a rebuild"
    )
