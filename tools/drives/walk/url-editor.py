"""url-editor: edit the address, edit its name, and leave the local path alone.

    .venv/bin/python tools/qa.py --page url-editor --drive tools/drives/walk/url-editor.py

The three rows are a web link, an unset field and a local path. The walk types into both halves of
the link and commits each way, reads the one refusal the field measures, fills the unset row and
empties it again, and proves the local row says why it is inert rather than showing an empty box.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, blur, key, popups, press_enter, retype, set_view  # noqa: E402
from qtpy import QtCore  # noqa: E402

LOCAL_NOTE = "This value is a local path. Only web links are edited here."


def half(editor, key_name: str) -> object:
    """One half of the stored link, whichever shape it arrived in."""
    value = editor.value
    if value is None:
        return None
    return value.get(key_name) if isinstance(value, dict) else getattr(value, key_name, None)


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("url-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no url-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- the web link: both halves, both ways of committing ---------------------------------
    web = cases["web link"]
    editor = web.editor
    walk.same("web: the demo opens on the stored address", "https://example.com/plate.mov", editor.url_input.text())
    walk.same("web: the name beside it shows", "plate.mov", editor.name_input.text())

    retype(editor.url_input, "https://example.com/final.mov")
    press_enter(editor.url_input)
    wait(200)
    walk.same("web: Enter commits the address", "https://example.com/final.mov", half(editor, "url"))

    retype(editor.name_input, "Final cut")
    blur(editor.name_input)
    wait(250)
    walk.same("web: leaving the name commits it", "Final cut", half(editor, "name"))
    walk.check(
        "web: the readout carries both halves",
        "Final cut" in web.readout.text and "final.mov" in web.readout.text,
        "both halves",
        web.readout.text,
    )

    # The one character the field is measured to refuse.
    retype(editor.url_input, "https://example.com/a file.mov")
    press_enter(editor.url_input)
    wait(200)
    walk.same("web: a raw space is refused", "https://example.com/final.mov", half(editor, "url"))
    walk.same("web: the line names the reason", "No spaces in a link. Percent-encode them.", editor.message)
    walk.check("web: the line is on show", editor.error_line.isVisible(), True, False)

    key(editor.url_input, QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.same("web: Escape clears the refusal", None, editor.message)
    walk.same("web: Escape puts the stored address back", "https://example.com/final.mov", editor.url_input.text())

    # A name with no link behind it is refused too.
    retype(editor.url_input, "")
    press_enter(editor.url_input)
    wait(200)
    walk.same("web: a name with no link is refused", "A name needs a link.", editor.message)
    key(editor.url_input, QtCore.Qt.Key.Key_Escape)
    wait(200)

    # --- the unset row: filled, then emptied again --------------------------------------------
    unset = cases["unset"]
    empty = unset.editor
    walk.same("unset: the demo opens on nothing", None, empty.value)
    retype(empty.url_input, "https://example.com/new.mov")
    press_enter(empty.url_input)
    wait(200)
    walk.same("unset: a typed address commits", "https://example.com/new.mov", half(empty, "url"))
    walk.same("unset: the readout follows", '{"url":"https://example.com/new.mov"}', unset.readout.text)
    retype(empty.url_input, "")
    press_enter(empty.url_input)
    wait(200)
    walk.same("unset: emptying the field stores nothing", None, empty.value)
    walk.same("unset: the readout reads null", "null", unset.readout.text)

    # --- the local path: named, not edited -------------------------------------------------------
    local = cases["local path"]
    path = local.editor
    walk.check("local: the row knows it is a path", path.local_only, True, path.local_only)
    walk.same("local: the line says why it is inert", LOCAL_NOTE, path._note.text)  # noqa: SLF001
    walk.check("local: the line is on show", path._note.isVisible(), True, False)  # noqa: SLF001
    walk.check(
        "local: the address is inert",
        not path.url_input.isEnabled(),
        False,
        path.url_input.isEnabled(),
    )
    held = local.readout.text
    retype(path.url_input, "https://example.com/hijack.mov")
    press_enter(path.url_input)
    wait(200)
    walk.same("local: the keyboard does not reach the value", held, local.readout.text)

    # --- the view controls ------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("url-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}["web link"]
        walk.same("header: the editors wear the size step", "lg", rebuilt.editor.size)
        retype(rebuilt.editor.url_input, "https://example.com/after.mov")
        press_enter(rebuilt.editor.url_input)
        wait(200)
        walk.same(
            "header: the rebuilt editor still commits",
            "https://example.com/after.mov",
            half(rebuilt.editor, "url"),
        )
    set_view(page, wait, theme="light", size="md", density="default", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS both halves of a link commit on Enter and on leaving, the space and the nameless"
        " link are named under the control, an emptied field stores nothing, and the local path"
        " says why it is inert"
    )
