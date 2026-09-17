"""The states of the field-picker, column-picker and field-editor wave, one function each.

Every `tools/drives/<widget>-<state>.py` is a short file over one function here, and the ones
upstream can be driven into have a twin under `tools/drives/upstream/<widget>-<state>.js`. A
shot of each pair is what the QA pass reads.

`:hover` and keyboard focus are widget state here rather than CSS, so this file reaches them
where an upstream body cannot; `tools/drives/upstream/README.md` says so.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, QPoint, Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication

__all__ = [
    "column_picker_dragging",
    "drag_move",
    "column_picker_moved",
    "column_picker_stacked",
    "field_editor_committed",
    "field_editor_editing",
    "field_editor_failed",
    "field_editor_popover",
    "field_picker_deep",
    "field_picker_error",
    "field_picker_focus",
    "field_picker_hover",
    "field_picker_loading",
    "field_picker_no_match",
    "field_picker_open",
    "field_picker_query",
]

#: A query the Version schema answers rows for, and one it answers nothing for.
QUERY = "date"
NO_MATCH = "zzzqqq"

#: The link the deep state descends through, and the type it lands on.
DEEP_FIELD = "entity"

#: How long a state waits for the schema behind it.
SETTLE_MS = 12000


def drag_move(widget, point) -> None:
    """A move with the button still down, delivered the same way on Qt 5 and Qt 6.

    `QTest.mouseMove` synthesises a move the platform may or may not carry the button on, so
    the event is built with `LeftButton` held and sent straight to the widget.
    """
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QMouseEvent

    where = QPointF(float(point.x()), float(point.y()))
    QApplication.sendEvent(
        widget,
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            where,
            where,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def press(widget, key: int, modifier=Qt.KeyboardModifier.NoModifier) -> None:
    """One key, delivered to the widget itself, so a headless run needs no focus."""
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, key, modifier))


def until(read, wait, ms: int = SETTLE_MS) -> bool:
    """Turn the loop until `read` answers something truthy, or give up."""
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        wait(40)
        if read():
            return True
    return False


def mock_of(client):
    """The mock under the cache and the counter, which is what arms a failure."""
    seen = client
    for _ in range(6):
        if hasattr(seen, "fail_next"):
            return seen
        seen = getattr(seen, "_client", None)
        if seen is None:
            return None
    return None


def picker_of(find, name: str):
    """One field picker of the page, by the object name its demo gave it."""
    found = find(name)
    if found is None:
        raise LookupError(f"no {name} on this page")
    return found


def rows_of(picker) -> int:
    return picker.control.list_surface().row_count()


def opened(picker, wait, ms: int = SETTLE_MS) -> bool:
    """Open a picker's list and wait until it has rows to show."""
    picker.control.set_open(True)
    return until(lambda: rows_of(picker) > 0, wait, ms)


def state(picker) -> dict:
    """What a field picker's list is showing, which is what the pair of shots is read against."""
    surface = picker.control.list_surface()
    return {
        "rows": surface.row_count(),
        "crumb": picker.breadcrumb.text() if picker.breadcrumb.isVisible() else "",
        "query": picker.control.query,
        "placeholder": picker.control.search_placeholder,
        "highlighted": surface.highlighted(),
    }


# --- field-picker ----------------------------------------------------------------------------


def field_picker_open(page, wait, find, prefs=None) -> dict:
    """The list of Version's fields, at the root."""
    picker = picker_of(find, "field-picker-free")
    if not opened(picker, wait):
        return {"verdict": "FAIL the field list never answered"}
    wait(200)
    return {"verdict": "PASS open", "seen": state(picker)}


def field_picker_deep(page, wait, find, prefs=None) -> dict:
    """One level down: the breadcrumb over the fields of the type the link landed on."""
    picker = picker_of(find, "field-picker-free")
    if not opened(picker, wait):
        return {"verdict": "FAIL the field list never answered"}
    link = next(
        (row for row in picker.options if row.name == DEEP_FIELD and row.traversable), None
    )
    if link is None:
        return {"verdict": f"FAIL Version has no traversable {DEEP_FIELD} field"}
    picker.levels.descend_into(link)
    if not until(lambda: picker.levels.deep, wait):
        return {"verdict": "FAIL the descend never landed"}
    # A link declaring several target types asks which first; the state wanted is the hop.
    choosing = picker.levels.choosing
    if choosing is not None:
        targets = picker.levels.targets()
        if not targets:
            return {"verdict": "FAIL the link offered no target type"}
        picker.levels.descend(choosing, targets[0])
    if not until(lambda: len(picker.hops) > 0 and rows_of(picker) > 0, wait):
        return {"verdict": "FAIL the hop never landed"}
    wait(200)
    return {"verdict": "PASS deep", "seen": state(picker), "hops": len(picker.hops)}


def field_picker_query(page, wait, find, prefs=None) -> dict:
    """A query in the search box, with the matched runs in the rows."""
    picker = picker_of(find, "field-picker-free")
    if not opened(picker, wait):
        return {"verdict": "FAIL the field list never answered"}
    picker.control.set_query(QUERY)
    wait(300)
    return {"verdict": "PASS query", "seen": state(picker)}


def field_picker_no_match(page, wait, find, prefs=None) -> dict:
    """A query nothing answers, which is the empty line."""
    picker = picker_of(find, "field-picker-free")
    if not opened(picker, wait):
        return {"verdict": "FAIL the field list never answered"}
    picker.control.set_query(NO_MATCH)
    if not until(lambda: rows_of(picker) == 0, wait, 4000):
        return {"verdict": "FAIL the list still holds rows"}
    wait(200)
    return {"verdict": "PASS no match", "seen": state(picker)}


def field_picker_loading(page, wait, find, prefs=None) -> dict:
    """The skeletons a schema read stands behind, caught before the answer lands."""
    picker = picker_of(find, "field-picker-free")
    picker.set_entity_type("Asset")
    picker.control.set_open(True)
    wait(30)
    return {
        "verdict": "PASS loading" if picker.levels.loading else "FAIL the read landed too soon",
        "loading": picker.levels.loading,
    }


def field_picker_error(page, wait, find, prefs=None) -> dict:
    """Upstream has no hook for this state; the mock here is armed to fail the next read."""
    picker = picker_of(find, "field-picker-free")
    mock = mock_of(getattr(picker.levels.context, "client", None))
    if mock is None:
        return {"verdict": "FAIL the demo client cannot be armed to fail"}
    mock.fail_next()
    picker.set_entity_type("Asset")
    picker.control.set_open(True)
    landed = until(lambda: picker.levels.failure is not None, wait, 8000)
    mock.fail_next(None)
    wait(200)
    return {
        "verdict": "PASS error" if landed else "FAIL the armed read did not fail",
        "message": picker.levels.failure or "",
    }


def field_picker_hover(page, wait, find, prefs=None) -> dict:
    """The closed control under the pointer: `muted` at 30% laid over the surface.

    Rule 5's wash is `bg-background hover:bg-muted/30`, a composite rather than a blend, so the
    pixel the box paints is read back and measured against it.
    """
    from sg_widgets_qt.theme import theme_of, with_alpha
    from sg_widgets_qt.widgets.picker_control import over

    picker = picker_of(find, "field-picker-preset")
    control = picker.control
    control.set_hovered(True)
    wait(400)
    theme = theme_of(control)
    wash = with_alpha(theme.muted, 0.3)
    want = over(theme.color("background"), wash)
    shot = control.grab().toImage()
    seen = shot.pixelColor(shot.width() // 2, 4)
    close = all(abs(a - b) <= 2 for a, b in zip(_rgb(seen), _rgb(want)))
    return {
        "verdict": "PASS hover" if control.hovered and close else "FAIL the wash is not muted/30",
        "hovered": control.hovered,
        "seen": _rgb(seen),
        "wanted": _rgb(want),
    }


def _rgb(colour) -> list:
    return [colour.red(), colour.green(), colour.blue()]


def field_picker_focus(page, wait, find, prefs=None) -> dict:
    """The closed control with the keyboard on it, which is the painted ring."""
    picker = picker_of(find, "field-picker-preset")
    picker.control.setFocus(Qt.FocusReason.TabFocusReason)
    wait(300)
    return {
        "verdict": "PASS focus" if picker.control.keyboard_focus else "FAIL no keyboard focus",
        "focused": picker.control.keyboard_focus,
    }


# --- column-picker ---------------------------------------------------------------------------


def _chosen_of(find, name: str = "column-picker-columns"):
    picker = find(name)
    if picker is None:
        raise LookupError(f"no {name} on this page")
    return picker, picker.chosen_list


def _row_point(chosen, row: int, x: int = 12) -> QPoint:
    rect = chosen.visualRect(chosen.model().index(row, 0))
    return QPoint(rect.left() + x, rect.center().y())


def column_picker_dragging(page, wait, find, prefs=None) -> dict:
    """The third row carried by its grip, held over the first, before the release."""
    picker, chosen = _chosen_of(find)
    wait(400)
    if chosen.model().rowCount() < 3:
        return {"verdict": "FAIL the chosen list has fewer than three rows"}
    start = _row_point(chosen, 2)
    QTest.mousePress(chosen.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    drag_move(chosen.viewport(), QPoint(start.x(), start.y() - 8))
    drag_move(chosen.viewport(), _row_point(chosen, 0))
    wait(200)
    return {
        "verdict": "PASS dragging" if chosen.carrying else "FAIL nothing is being carried",
        "carrying": chosen.carrying or "",
        "order": chosen.paths,
    }


def column_picker_moved(page, wait, find, prefs=None) -> dict:
    """A row picked up with Space and moved one place with the keyboard."""
    picker, chosen = _chosen_of(find)
    wait(400)
    if chosen.model().rowCount() < 2:
        return {"verdict": "FAIL the chosen list has fewer than two rows"}
    chosen.setFocus(Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(0)
    press(chosen, Qt.Key.Key_Space)
    press(chosen, Qt.Key.Key_Down)
    wait(200)
    return {
        "verdict": "PASS moved",
        "order": chosen.paths,
        "value": picker.value,
        "announced": picker.announcement,
    }


def column_picker_stacked(page, wait, find, prefs=None) -> dict:
    """The dual layout under 512px, where the two panes stack."""
    picker = find("column-picker-dual")
    if picker is None:
        return {"verdict": "FAIL no dual column picker on this page"}
    picker.setFixedWidth(420)
    wait(400)
    return {"verdict": "PASS stacked", "width": picker.width()}


# --- field-editor ----------------------------------------------------------------------------


def _editor_of(find, key: str):
    found = find(f"field-editor-{key}")
    if found is None:
        raise LookupError(f"no field-editor-{key} on this page")
    return found


def field_editor_editing(page, wait, find, prefs=None) -> dict:
    """Every inline row on the edit half, which is what the demo's own toggle does."""
    toggle = find("demo-toggle")
    if toggle is None:
        return {"verdict": "FAIL no toggle on this page"}
    toggle.clicked.emit()
    wait(400)
    from sg_widgets_qt.widgets.field_editor import FieldEditor

    editors = find(FieldEditor, all=True)
    editing = [one.objectName() for one in editors if one.mode == "edit"]
    return {"verdict": "PASS editing", "editing": len(editing), "rows": len(editors)}


def field_editor_popover(page, wait, find, prefs=None) -> dict:
    """The text field editing in a popover: the label, the textarea, Cancel and Save."""
    editor = _editor_of(find, "popover-text")
    editor.set_mode("edit")
    if not until(lambda: editor.popover is not None, wait, 4000):
        return {"verdict": "FAIL the popover never opened"}
    wait(300)
    from sg_widgets_qt.primitives.button import Button

    popup = editor.popover.content()
    buttons = [one.text for one in popup.findChildren(Button)]
    label = popup.findChild(object, "field-editor-label")
    return {
        "verdict": "PASS popover" if buttons[-2:] == ["Cancel", "Save"] else "FAIL " + str(buttons),
        "width": popup.width(),
        "label": bool(label),
        "buttons": buttons,
        "steps": [one.size for one in popup.findChildren(Button)],
    }


def field_editor_committed(page, wait, find, prefs=None) -> dict:
    """A commit written through the client, with the row read back on the field written."""

    editor = _editor_of(find, "text")
    ref = _a_version(editor.context)
    if ref is None:
        return {"verdict": "FAIL the mock answered no Version to write to"}
    editor.set_entity(ref)
    editor.set_mode("edit")
    wait(200)
    control = editor.control
    if control is None:
        return {"verdict": "FAIL the text editor never mounted"}
    caret = control.control
    caret.setText("comp")
    press(caret, Qt.Key.Key_Return)
    if not until(lambda: not editor.writing, wait, 8000):
        return {"verdict": "FAIL the write never finished"}
    wait(300)
    clean = not editor.error
    return {
        "verdict": "PASS committed" if clean else f"FAIL the write said {editor.error}",
        "wrote_to": [ref.type, ref.id],
        "value": editor.value,
        "error": editor.error or "",
    }


def _a_version(context):
    """A row of the mock to write to, so the commit path is walked end to end."""
    from sg_widgets_core.client import SearchOptions
    from sg_widgets_core.filter import EntityRef

    client = getattr(context, "client", None)
    if client is None:
        return None
    answer = client.search(
        "Version", SearchOptions(fields=["code"], page={"size": 1, "number": 1})
    )
    rows = answer.data
    return EntityRef(type="Version", id=rows[0].id) if rows else None


def field_editor_failed(page, wait, find, prefs=None) -> dict:
    """A refused write: the line under the control says what the site said."""
    from sg_widgets_core.filter import EntityRef

    editor = _editor_of(find, "text")
    mock = mock_of(getattr(editor.context, "client", None))
    if mock is None:
        return {"verdict": "FAIL the demo client cannot be armed to fail"}
    editor.set_entity(_a_version(editor.context) or EntityRef(type="Version", id=1))
    editor.set_mode("edit")
    wait(200)
    control = editor.control
    if control is None:
        return {"verdict": "FAIL the text editor never mounted"}
    mock.fail_next()
    caret = control.control
    caret.setText("refused")
    press(caret, Qt.Key.Key_Return)
    landed = until(lambda: bool(editor.error), wait, 8000)
    mock.fail_next(None)
    wait(300)
    return {
        "verdict": "PASS failed" if landed else "FAIL the armed write did not fail",
        "message": editor.error or "",
    }
