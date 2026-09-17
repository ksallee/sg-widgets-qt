"""index: the overview, whose one button reads the site.

    .venv/bin/python tools/qa.py --page index --drive tools/drives/walk/index.py

The hello demo is the harness end to end: the buttons are the primitives, and `Load entity types`
puts a read on a worker and prints what the site answered under them. The walk presses it, watches
the line say it is loading and then name the types, presses it again while it is still out to prove
a second press is ignored, and presses each of the other variants.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, popups, set_view, wait_for  # noqa: E402

VARIANTS = ("secondary", "outline", "ghost", "destructive")


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("hello")
    if demo is None:
        return {"verdict": "FAIL the overview drew no hello demo"}
    button = find("load-entity-types")
    line = find("demo-output")
    walk.check("the overview carries the read button", button is not None, True, button)
    walk.check("the line under it stands on the page", line is not None, True, line)
    walk.same("the line says nothing has been read", "Nothing loaded yet.", line.text())

    # --- the read -----------------------------------------------------------------------------
    click(button)
    wait(20)
    walk.check(
        "pressing it puts the read out and says so",
        line.text() == "Loading…" or not demo.demo_ready,
        "Loading…",
        line.text(),
    )
    walk.check(
        "the button is inert while the read is out",
        not button.isEnabled() or demo.demo_ready,
        False,
        button.isEnabled(),
    )
    wait_for(lambda: demo.demo_ready, wait, 20000)
    wait(200)
    answered = line.text()
    walk.check(
        "the line names what the site answered",
        answered not in ("", "Loading…", "Nothing loaded yet."),
        "the types",
        answered[:80],
    )
    walk.check("the types read as a list", "·" in answered, "a list", answered[:80])
    walk.check("the button takes presses again", button.isEnabled(), True, button.isEnabled())

    # --- a second read answers the same thing ---------------------------------------------------
    click(button)
    wait_for(lambda: demo.demo_ready, wait, 20000)
    wait(200)
    walk.same("reading again answers the same types", answered, line.text())

    # --- the other variants -----------------------------------------------------------------------
    for name in VARIANTS:
        made = find("button-" + name)
        walk.check(f"the {name} button stands on the page", made is not None, True, made)
        if made is not None:
            click(made)
            wait(120)
            walk.check(f"the {name} button takes a press", made.isEnabled(), True, made.isEnabled())

    # --- the view controls --------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    walk.same("header: the page wears dark", "dark", prefs.theme)
    again = find("hello")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    rebuilt = find("load-entity-types")
    if rebuilt is not None:
        click(rebuilt)
        wait_for(lambda: again.demo_ready, wait, 20000)
        wait(200)
        walk.same("header: the rebuilt button still reads the site", answered, find("demo-output").text())
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the read button puts a read on a worker, goes inert while it is out, and names the"
        " types the site answered under it; every other variant takes a press; and the demo still"
        " reads after the view controls have rebuilt it"
    )
