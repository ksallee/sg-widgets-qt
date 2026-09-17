"""field-editor: one editor per data type, the commit path, and the schema's own refusals.

The port of `~/dev/sg-widgets/tools/drives/field-editors.js`, which runs on the entity table
upstream because the table is what writes there. The port's own FieldEditor writes when it is
given an `entity`, so the whole path is read here, on this page.

    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-dispatch.py
    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-dispatch.py --qt5

Six readings:

    dispatch   every data type the mock's schema names mounts the editor core's map says
    none       a type with no editor stays on the display half whatever the mode says
    commit     with an `entity`, the value is written through the client and the row read back
               on the field that was written (024_read_after_write)
    emit       without one, the editor only emits and the caller writes
    failed     a refused write puts what the site said under the control
    hidden     a status field read with a project offers none of the codes it hides (009)
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtCore import Qt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import mock_of, press, until  # noqa: E402

#: The type whose schema the dispatch reading walks, and the project the hidden codes belong to.
ROOT = "Version"
PROJECT = 70
STATUS_FIELD = "sg_status_list"

#: What core's own map says each editor is, by the widget class the port mounts.
EXPECTED: dict[str, str] = {
    "text": "TextEditor",
    "entity_type": "TextEditor",
    "uuid": "TextEditor",
    "number": "NumberEditor",
    "float": "NumberEditor",
    "percent": "NumberEditor",
    "currency": "NumberEditor",
    "duration": "NumberEditor",
    "timecode": "NumberEditor",
    "footage": "NumberEditor",
    "checkbox": "CheckboxEditor",
    "date": "DateEditor",
    "date_time": "DateTimeEditor",
    "list": "ListPicker",
    "url": "UrlEditor",
    "color": "ColorEditor",
    "status_list": "StatusPicker",
    "entity": "EntityPicker",
    "multi_entity": "EntityMultiPicker",
}

#: The types the REST API cannot write, which have no editor at all (field_types/calculated).
NO_EDITOR = ("image", "calculated", "summary", "pivot_column")


def schema_of(context, entity_type: str) -> dict:
    """The type's fields at site scope, straight off the context's own schema service."""
    service = getattr(context, "schema", None)
    return {} if service is None else service.fields(entity_type)


def scoped_status(context, entity_type: str, name: str, project_id: int):
    """The status field with the project's hidden codes on it (009_status_lists)."""
    service = getattr(context, "schema", None)
    if service is None:
        return None
    found = service.fields(entity_type).get(name)
    if found is None:
        return None
    import copy

    scoped = copy.copy(found)
    scoped.hidden_values = service.hidden_values(entity_type, name, project_id)
    return scoped


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    from sg_widgets_core.schema import FieldSchema
    from sg_widgets_qt.widgets.field_editor import FieldEditor

    failures: list[str] = []
    seen: dict = {}

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    wait(300)
    sample = find("field-editor-text")
    if sample is None:
        return {"verdict": "FAIL no field editor on this page"}
    context = sample.context

    # 1. Every data type the mock's schema names mounts the editor core's map says. The types
    #    are taken from the schema rather than from a list here, so the mock's own vocabulary
    #    is what the reading walks.
    fields = schema_of(context, ROOT)
    types = sorted({field.data_type for field in fields.values()})
    mounted: dict[str, str] = {}
    for data_type in types:
        field = FieldSchema(
            name="probe",
            display_name="Probe",
            entity_type=ROOT,
            data_type=data_type,
            editable=True,
            mandatory=False,
            unique=False,
            valid_values=["a", "b"] if data_type == "list" else None,
            valid_types=["Shot"] if data_type in ("entity", "multi_entity") else None,
        )
        one = FieldEditor(
            value=None, field=field, editable=True, mode="edit", context=context, parent=page
        )
        wait(20)
        mounted[data_type] = type(one.control).__name__ if one.control is not None else ""
        one.setParent(None)
        one.deleteLater()
    wrong = {
        data_type: mounted[data_type]
        for data_type in types
        if data_type in EXPECTED and mounted[data_type] != EXPECTED[data_type]
    }
    seen["dispatch"] = {"types": len(types), "mounted": mounted, "wrong": wrong}
    if wrong:
        note("dispatch", f"{wrong}")

    # 2. A type with no editor stays on the display half whatever the mode says.
    staying = {}
    for data_type in NO_EDITOR:
        field = FieldSchema(
            name="probe",
            display_name="Probe",
            entity_type=ROOT,
            data_type=data_type,
            editable=True,
            mandatory=False,
            unique=False,
        )
        one = FieldEditor(
            value=None, field=field, editable=True, mode="edit", context=context, parent=page
        )
        wait(20)
        staying[data_type] = one.mode
        if one.mode != "display" or one.control is not None:
            note("none", f"{data_type} left the display half")
        one.setParent(None)
        one.deleteLater()
    seen["none"] = staying

    # 3. With an `entity`, the commit is written and the row read back on the field written.
    client = getattr(context, "client", None)
    ref = _a_row(context, ROOT)
    if ref is None:
        return {"verdict": f"FAIL the mock answered no {ROOT} to write to"}
    editor = find("field-editor-text")
    heard: list = []
    editor.value_changed.connect(heard.append)
    editor.set_entity(ref)
    editor.set_mode("edit")
    wait(150)
    caret = _caret(editor)
    if caret is None:
        return {"verdict": "FAIL the text editor never mounted"}
    caret.setText("roto")
    press(caret, Qt.Key.Key_Return)
    until(lambda: not editor.writing and heard, wait, 8000)
    wait(200)
    stored = _read_back(client, ref, editor.field.name)
    seen["commit"] = {"emitted": list(heard), "stored": stored, "error": editor.error or ""}
    if editor.error:
        note("commit", f"the write said {editor.error}")
    if stored != "roto":
        note("commit", f"the row reads {stored!r} after the write")
    if heard[-1:] != [stored]:
        note("commit", f"the editor emitted {heard[-1:]} rather than the row it read back")

    # 4. Without an entity, the editor only emits and the caller writes.
    editor.set_entity(None)
    heard.clear()
    editor.set_mode("edit")
    wait(150)
    caret = _caret(editor)
    caret.setText("matte")
    press(caret, Qt.Key.Key_Return)
    wait(300)
    after = _read_back(client, ref, editor.field.name)
    seen["emit"] = {"emitted": list(heard), "stored": after}
    if heard != ["matte"]:
        note("emit", f"the editor emitted {heard}")
    if after != "roto":
        note("emit", f"the row moved to {after!r} with no entity given")

    # 5. A refused write puts what the site said under the control.
    mock = mock_of(client)
    if mock is None:
        note("failed", "the demo client cannot be armed to fail")
    else:
        editor.set_entity(ref)
        editor.set_mode("edit")
        wait(150)
        mock.fail_next()
        caret = _caret(editor)
        caret.setText("refused")
        press(caret, Qt.Key.Key_Return)
        landed = until(lambda: bool(editor.error), wait, 8000)
        mock.fail_next(None)
        wait(200)
        line = page.findChild(type(editor), "field-editor-text")
        shown = ""
        for child in (line or editor).findChildren(object, "field-editor-error"):
            shown = getattr(child, "message", "") or shown
        seen["failed"] = {"error": editor.error or "", "line": shown}
        if not landed:
            note("failed", "the armed write did not fail")
        if shown != editor.error:
            note("failed", f"the line under the control reads {shown!r}")
        editor.set_mode("display")
        editor.set_error(None)
        editor.set_entity(None)

    # 6. A status field read with a project offers none of the codes the project hides (009).
    status = scoped_status(context, ROOT, STATUS_FIELD, PROJECT)
    if status is None:
        note("hidden", f"the schema has no {ROOT}.{STATUS_FIELD}")
    else:
        one = FieldEditor(
            value="ip",
            field=status,
            editable=True,
            mode="edit",
            context=context,
            project_id=PROJECT,
            parent=page,
        )
        until(lambda: one.control is not None and bool(one.control.options), wait, 8000)
        offered = [row.code for row in (one.control.options if one.control else [])]
        hidden = list(status.hidden_values or [])
        leaked = [code for code in hidden if code in offered]
        seen["hidden"] = {"hides": len(hidden), "offers": len(offered), "leaked": leaked}
        if not hidden:
            note("hidden", f"project {PROJECT} hides nothing on {STATUS_FIELD}")
        if leaked:
            note("hidden", f"the picker still offers {', '.join(leaked)}")
        one.setParent(None)
        one.deleteLater()

    return {
        "verdict": (
            "PASS every data type mounts its own editor, a commit writes through the client and"
            " re-reads the row, an editor with no entity only emits, a refused write says so, and"
            " a project's hidden status codes are off the list"
            if not failures
            else "FAIL " + "; ".join(failures[:6])
        ),
        "failures": failures,
        "seen": seen,
    }


def _caret(editor):
    """The field a typed editor takes its draft from: `input` where it has one, else `control`."""
    control = editor.control
    if control is None:
        return None
    found = getattr(control, "input", None)
    return found if found is not None else getattr(control, "control", None)


def _a_row(context, entity_type: str):
    from sg_widgets_core.client import SearchOptions
    from sg_widgets_core.filter import EntityRef

    client = getattr(context, "client", None)
    if client is None:
        return None
    answer = client.search(
        entity_type, SearchOptions(fields=["code"], page={"size": 1, "number": 1})
    )
    rows = answer.data
    return EntityRef(type=entity_type, id=rows[0].id) if rows else None


def _read_back(client, ref, name: str):
    """The field as the site now holds it, which is what the commit is measured against."""
    from sg_widgets_core.client import SearchOptions

    answer = client.search(
        ref.type,
        SearchOptions(
            filters={"logical_operator": "and", "conditions": [["id", "is", ref.id]]},
            fields=[name],
            page={"size": 1, "number": 1},
        ),
    )
    rows = answer.data
    return rows[0].values.get(name) if rows else None
