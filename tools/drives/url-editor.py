"""The url editor, driven on the url-editor page.

The only accepted write is an object holding `url`: a bare string is a 400, the url itself is
validated and a raw space is the one character measured to fail, and with no name the field reads
back the whole url as its name (field_types/url). A local value is not edited here.

    .venv/bin/python tools/qa.py --page url-editor --drive tools/drives/url-editor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore  # noqa: E402


def _shape(value: object) -> dict:
    """The payload as a plain map, whichever way the editor spelled it."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if v is not None}
    return {k: v for k, v in vars(value).items() if v is not None}


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
    from sg_widgets_qt.widgets.url_editor import LOCAL_NOTE

    failures: list[str] = []
    seen: dict = {}

    editors = find("url-editor", all=True)
    if len(editors) < 3:
        return {"verdict": f"FAIL the page holds {len(editors)} url editors, wanted 3"}
    web, unset, local = editors[:3]

    committed: list = []
    web.committed.connect(committed.append)

    # Typing and Enter commit, and the payload carries the address and the name.
    type_text(web.url_input, "https://example.com/comp.mov")
    type_text(web.name_input, "comp.mov")
    press_enter(web.name_input)
    wait(60)
    seen["committed"] = _shape(committed[-1] if committed else None)
    if seen["committed"].get("url") != "https://example.com/comp.mov":
        failures.append(f"Enter committed {seen['committed']}")
    if seen["committed"].get("name") != "comp.mov":
        failures.append("the name did not reach the payload")

    # With no name the field reads back the whole url as its name.
    type_text(web.name_input, "")
    press_enter(web.url_input)
    wait(60)
    seen["nameless"] = _shape(committed[-1] if committed else None)
    if seen["nameless"].get("name") not in (None, seen["nameless"].get("url")):
        failures.append(f"a nameless link committed {seen['nameless']}")

    # A raw space is the one character measured to fail (field_types/url).
    type_text(web.url_input, "https://example.com/a b.mov")
    # The caret moving here is itself a blur, which commits; the refusal is what Enter does next.
    before = len(committed)
    press_enter(web.url_input)
    wait(60)
    seen["refused"] = web.message
    if not web.message:
        failures.append("a url with a space showed no error line")
    if web.reads_invalid is not True:
        failures.append("a refused url left the control reading valid")
    if len(committed) != before:
        failures.append("a refused url reached the value")

    # Escape restores the stored value and drops the message.
    escape(web.url_input)
    wait(60)
    seen["restored"] = (web.url_input.text(), web.message)
    if web.message is not None:
        failures.append("Escape left the error line standing")

    # Both halves empty stores null.
    type_text(web.url_input, "")
    type_text(web.name_input, "")
    press_enter(web.url_input)
    wait(60)
    seen["cleared"] = committed[-1:]
    if committed[-1:] != [None]:
        failures.append(f"both empty committed {committed[-1:]}, wanted [None]")

    # A blur commits too.
    type_text(web.url_input, "https://example.com/plate.mov")
    web.url_input.clearFocus()
    wait(60)
    seen["blurred"] = _shape(committed[-1] if committed else None).get("url")
    if seen["blurred"] != "https://example.com/plate.mov":
        failures.append(f"leaving the control committed {seen['blurred']!r}")

    # The unset case starts empty and shows its placeholders.
    seen["unset"] = (unset.value, unset.url_input.text(), unset.name_input.text())
    if unset.value is not None or unset.url_input.text() or unset.name_input.text():
        failures.append(f"the unset case reads {seen['unset']}")

    # A local value carries paths and no address: the control says so and edits nothing.
    seen["local"] = (local.local_only, local._note.text, local.url_input.isEnabled())
    if local.local_only is not True:
        failures.append("the local case does not read local")
    if local._note.text != LOCAL_NOTE:
        failures.append(f"the local note reads {local._note.text!r}")
    if local.url_input.isEnabled() or local.name_input.isEnabled():
        failures.append("the local case left its inputs live")

    # Readonly drops the writing and keeps full contrast; disabled is inert.
    unset.set_readonly(True)
    wait(40)
    if not (unset.url_input.isReadOnly() and unset.name_input.isReadOnly()):
        failures.append("readonly left an input writable")
    if unset.isEnabled() is not True:
        failures.append("readonly disabled the control, which drops its contrast")
    unset.set_readonly(False)
    unset.set_disabled(True)
    wait(40)
    was = unset.value
    key(unset.url_input, QtCore.Qt.Key.Key_Return)
    if unset.value != was:
        failures.append("a disabled editor still committed")
    unset.set_disabled(False)

    # The size ladder, measured on both inputs.
    ladder = {}
    for step, height in CONTROL_HEIGHT.items():
        web.set_size(step)
        wait(20)
        ladder[step] = (web.url_input.sizeHint().height(), web.name_input.sizeHint().height())
        if ladder[step] != (height, height):
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    web.set_size("md")
    seen["ladder"] = ladder

    return {
        "verdict": (
            "PASS Enter commits {url, name}, a space is refused with a line and no commit, "
            "Escape restores, a blur commits, a local value is not edited, ladder 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
