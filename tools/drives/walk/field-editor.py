"""field-editor: press a value to edit it, commit with Enter, cancel with Escape.

    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/walk/field-editor.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click,
    key,
    orphans,
    scroll_to,
    type_into,
    wear,
)
from qtpy import QtCore, QtWidgets  # noqa: E402


def editor(find, key_name: str):
    return find(f"field-editor-{key_name}")


def line(find, key_name: str):
    return find(f"field-editor-{key_name}-value")


def caret_of(one):
    """The text field a person types into, inside whatever control the editor mounted.

    A text field in a popover is a textarea, which is where there is room for one, and a
    control may hold a line edit of its own out of sight; the visible one is the one a person
    has under the caret.
    """
    control = one.control
    if control is None:
        return None
    for kind in (QtWidgets.QPlainTextEdit, QtWidgets.QLineEdit):
        for found in control.findChildren(kind):
            if found.isVisibleTo(control):
                return found
    return None


def start_editing(page, one, wait) -> bool:
    """A press on the value, which is what a reader does to edit it.

    An editor in a popover opens a window of its own, and a text field only commits what it
    holds once the caret leaves it; the window is asked for the activation a real press would
    have given it, so the caret is where a person's would be.
    """
    scroll_to(page, one, wait)
    click(one.display)
    wait(250)
    caret = caret_of(one)
    if caret is not None:
        window = caret.window()
        window.raise_()
        window.activateWindow()
        QtWidgets.QApplication.setActiveWindow(window)
        caret.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        wait(120)
    return one.mode == "edit"


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- a press on the value opens its editor ---------------------------------------------
    text = editor(find, "text")
    text_line = line(find, "text")
    walk.check("text: a press on the value opens the editor", start_editing(page, text, wait), True, text.mode)
    caret = caret_of(text)
    walk.check("text: the editor takes the caret", caret is not None, "a field", caret)
    if caret is not None:
        type_into(caret, "compositing", wait)
        key(caret, QtCore.Qt.Key.Key_Return)
        wait(400)
        walk.same("text: Enter commits what was typed", "compositing", text.value)
        walk.same("text: Enter leaves the editor", "display", text.mode)
        walk.same("text: the readout under the row follows", '"compositing"', text_line.text())
        walk.check("text: the value is on show again", text.display.isVisible(), True, False)

    # --- Escape cancels ----------------------------------------------------------------------
    held = text.value
    walk.check("text: the value opens again", start_editing(page, text, wait), True, text.mode)
    caret = caret_of(text)
    if caret is not None:
        type_into(caret, "never", wait)
        key(caret, QtCore.Qt.Key.Key_Escape)
        wait(400)
        walk.same("text: Escape leaves the editor", "display", text.mode)
        walk.same("text: Escape puts the value back", held, text.value)
        walk.same("text: the readout is untouched", f'"{held}"', text_line.text())

    # --- Enter on the value opens it too -------------------------------------------------------
    scroll_to(page, text, wait)
    text.display.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(text.display, QtCore.Qt.Key.Key_Return)
    wait(300)
    walk.same("text: Enter on the value opens the editor", "edit", text.mode)
    key(caret_of(text) or text.display, QtCore.Qt.Key.Key_Escape)
    wait(250)

    # --- a duration reads what a person writes ---------------------------------------------------
    duration = editor(find, "duration")
    duration_line = line(find, "duration")
    walk.check("duration: a press opens the editor", start_editing(page, duration, wait), True, duration.mode)
    caret = caret_of(duration)
    if caret is not None:
        type_into(caret, "1h 30m", wait)
        key(caret, QtCore.Qt.Key.Key_Return)
        wait(400)
        walk.same("duration: 1h 30m is stored as 90 minutes", 90, duration.value)
        walk.same("duration: the readout says 90", "90", duration_line.text())
        walk.check(
            "duration: the value reads back as hours and minutes",
            "1" in duration.display.text(),
            "1h 30m",
            duration.display.text(),
        )

    # --- a number steps and commits -----------------------------------------------------------------
    number = editor(find, "number")
    number_line = line(find, "number")
    held = number.value
    walk.check("number: a press opens the editor", start_editing(page, number, wait), True, number.mode)
    caret = caret_of(number)
    if caret is not None:
        type_into(caret, "2002", wait)
        key(caret, QtCore.Qt.Key.Key_Return)
        wait(400)
        walk.same("number: Enter commits the number", 2002, number.value)
        walk.same("number: the readout follows", "2002", number_line.text())

    # --- a checkbox toggles ---------------------------------------------------------------------------
    checkbox = editor(find, "checkbox")
    held = checkbox.value
    walk.check("checkbox: a press opens the editor", start_editing(page, checkbox, wait), True, checkbox.mode)
    control = checkbox.control
    switch = control.findChild(QtWidgets.QWidget, "checkbox-editor-switch") if control else None
    walk.check("checkbox: the editor draws a switch", switch is not None, "a switch", switch)
    if switch is not None:
        click(switch)
        wait(350)
        walk.check("checkbox: the press toggles the value", checkbox.value != held, f"not {held}", checkbox.value)
    key(checkbox.display, QtCore.Qt.Key.Key_Escape)
    wait(200)

    # --- a list picks from its own set --------------------------------------------------------------------
    listed = editor(find, "list")
    listed_line = line(find, "list")
    held = listed.value
    walk.check("list: a press opens the editor", start_editing(page, listed, wait), True, listed.mode)
    control = listed.control
    if control is not None and hasattr(control, "control"):
        picker = control
        surface = picker.control.list_surface() if hasattr(picker, "control") else None
        if not picker.control.is_open:
            click(picker.control)
            wait(250)
        if surface is not None and surface.row_count() > 1:
            surface.set_highlight(1)
            key(picker.control, QtCore.Qt.Key.Key_Return)
            wait(400)
            walk.check("list: the pick commits a new value", listed.value != held, f"not {held}", listed.value)
            walk.check("list: the readout follows", listed_line.text() == f'"{listed.value}"', f'"{listed.value}"', listed_line.text())
    if listed.mode == "edit":
        key(listed.display, QtCore.Qt.Key.Key_Escape)
        wait(200)

    # --- the toggle opens every inline row at once ------------------------------------------------------------
    toggle = find("demo-toggle")
    walk.check("toggle: the demo offers it", toggle is not None, True, toggle)
    if toggle is not None:
        scroll_to(page, toggle, wait)
        click(toggle)
        wait(700)
        inline = [one for one in page.findChildren(type(text)) if one.editor_placement != "popover"]
        editing = [one for one in inline if one.mode == "edit"]
        walk.check(
            "toggle: every inline row is in its editor",
            len(editing) == len(inline) and bool(inline),
            len(inline),
            len(editing),
        )
        click(toggle)
        wait(700)
        shown = [one for one in inline if one.mode == "display"]
        walk.same("toggle: pressing it again shows the values", len(inline), len(shown))

    # --- in a popover --------------------------------------------------------------------------------------------
    popover_text = editor(find, "popover-text")
    popover_line = line(find, "popover-text")
    held = popover_text.value
    walk.check("popover: a press opens the editor", start_editing(page, popover_text, wait), True, popover_text.mode)
    walk.check("popover: it opens in a popover of its own", popover_text.popover is not None, "a popover", None)
    walk.check("popover: the value stays where it is", popover_text.display.isVisible(), True, False)
    cancel = popover_text.popover.findChild(QtWidgets.QWidget, "field-editor-cancel") if popover_text.popover else None
    save = popover_text.popover.findChild(QtWidgets.QWidget, "field-editor-save") if popover_text.popover else None
    walk.check("popover: it carries Cancel and Save", cancel is not None and save is not None, "both", (cancel, save))
    caret = caret_of(popover_text)
    if caret is not None and cancel is not None:
        type_into(caret, "Cancelled.", wait)
        click(cancel)
        wait(400)
        walk.same("popover: Cancel leaves the editor", "display", popover_text.mode)
        walk.same("popover: Cancel puts the value back", held, popover_text.value)
        walk.check("popover: no popup is left standing", not orphans(), [], orphans())

    walk.check("popover: the value opens again", start_editing(page, popover_text, wait), True, popover_text.mode)
    caret = caret_of(popover_text)
    save = popover_text.popover.findChild(QtWidgets.QWidget, "field-editor-save") if popover_text.popover else None
    if caret is not None and save is not None:
        type_into(caret, "Plate re-delivered.", wait)
        wait(150)
        walk.check("popover: the caret is in the field", caret.hasFocus(), True, caret.hasFocus())
        click(save)
        wait(400)
        walk.same("popover: Save commits what was typed", "Plate re-delivered.", popover_text.value)
        walk.same("popover: Save leaves the editor", "display", popover_text.mode)
        walk.same("popover: the readout follows", '"Plate re-delivered."', popover_line.text())
        walk.check("popover: nothing is left standing", not orphans(), [], orphans())

    # A status in a popover, which is the other case the caption names.
    popover_status = editor(find, "popover-status")
    walk.check("popover status: a press opens the editor", start_editing(page, popover_status, wait), True, popover_status.mode)
    walk.check("popover status: it opens in a popover", popover_status.popover is not None, "a popover", None)
    cancel = popover_status.popover.findChild(QtWidgets.QWidget, "field-editor-cancel") if popover_status.popover else None
    if cancel is not None:
        click(cancel)
        wait(400)
        walk.same("popover status: Cancel leaves the editor", "display", popover_status.mode)
    walk.check("popover status: nothing is left standing", not orphans(), [], orphans())

    # --- the header ---------------------------------------------------------------------------------------------------
    wear(prefs, wait, theme="dark")
    walk.same("header: the page wears dark", "dark", prefs.theme)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = editor(find, "text")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the editor wears the size step", "lg", rebuilt.size)
        walk.check("header: the rebuilt editor still opens", start_editing(page, rebuilt, wait), True, rebuilt.mode)
        key(caret_of(rebuilt) or rebuilt.display, QtCore.Qt.Key.Key_Escape)
        wait(250)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
