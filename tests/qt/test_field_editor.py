"""One field displayed or edited: the dispatch, the commit, the states and the popover."""
from __future__ import annotations

import time

import pytest
from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QLineEdit, QWidget

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_core.schema import FieldSchema
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.field_editor import FieldEditor

from .editors import type_into
from .test_picker_contract import spin


def context_for():
    client = MockClient(seed=1, latency_ms=0, now=MOCK_NOW)
    return create_sg_context(client, SgContextOptions()), client


def schema(name: str, label: str, data_type: str, **extra) -> FieldSchema:
    return FieldSchema(
        name=name,
        display_name=label,
        entity_type="Version",
        data_type=data_type,
        editable=True,
        mandatory=False,
        unique=False,
        **extra,
    )


#: One field per data type the dispatch knows, with a value in the shape the API sends.
CASES = [
    ("text", schema("sg_department", "Department", "text"), "lighting", "TextEditor"),
    ("number", schema("frame_count", "Frame Count", "number"), 1001, "NumberEditor"),
    ("float", schema("ratio", "Movie Aspect Ratio", "float"), "1.75", "NumberEditor"),
    ("percent", schema("sg___complete", "Complete", "percent"), 50, "NumberEditor"),
    ("currency", schema("sg_bid", "Bid", "currency"), 12500, "NumberEditor"),
    ("duration", schema("sg_bid___total", "Bid Total", "duration"), 480, "NumberEditor"),
    ("timecode", schema("sg_timecode", "Timecode", "timecode"), 3600000, "NumberEditor"),
    ("checkbox", schema("flagged", "Flagged", "checkbox"), True, "CheckboxEditor"),
    ("date", schema("sg_turnover_date", "Turnover Date", "date"), "2026-09-02", "DateEditor"),
    (
        "date_time",
        schema("client_approved_at", "Client Approved At", "date_time"),
        "2026-03-04T13:06:07Z",
        "DateTimeEditor",
    ),
    (
        "url",
        schema("sg_uploaded_movie", "Uploaded Movie", "url"),
        {"url": "https://example.com/plate.mov", "name": "plate.mov", "link_type": "web"},
        "UrlEditor",
    ),
    ("color", schema("color", "Gantt Bar Color", "color"), "pipeline_step", "ColorEditor"),
    (
        "list",
        schema("sg_version_type", "Version Type", "list", valid_values=["Type A", "Type B"]),
        "Type A",
        "ListPicker",
    ),
    ("status_list", schema("sg_status_list", "Status", "status_list"), "ip", "StatusPicker"),
    (
        "entity",
        schema("entity", "Link", "entity", valid_types=["Shot"]),
        {"type": "Shot", "id": 1234, "name": "sh010"},
        "EntityPicker",
    ),
    (
        "multi_entity",
        schema("sg_shots", "Shots", "multi_entity", valid_types=["Shot"]),
        [{"type": "Shot", "id": 1234, "name": "sh010"}],
        "EntityMultiPicker",
    ),
]


def build(qtbot, **props):
    context, client = context_for()
    props.setdefault("context", context)
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(520, 200)
    editor = FieldEditor(parent=root, **props)
    editor.setGeometry(10, 10, 500, 60)
    root.show()
    qtbot.waitExposed(root)
    editor.test_root = root
    editor.test_client = client
    editor.test_context = context
    return editor


def written(qtbot, editor, ms: int = 1200) -> None:
    """Spin until the write in flight has landed."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if not editor.writing:
            break
        qtbot.wait(5)
    spin(qtbot, 30)


@pytest.mark.parametrize(("key", "field", "value", "expected"), CASES, ids=[c[0] for c in CASES])
def test_the_data_type_picks_the_editor(qtbot, key, field, value, expected):
    editor = build(qtbot, value=value, field=field, editable=True, mode="edit")
    spin(qtbot, 60)
    assert editor.mode == "edit", key
    assert type(editor.control).__name__ == expected
    assert editor.control.objectName() == f"field-editor-{editor.kind}"


def test_a_type_with_no_editor_stays_on_the_display_half(qtbot):
    for data_type in ("calculated", "summary", "pivot_column", "image"):
        editor = build(
            qtbot,
            value=3,
            field=schema("computed", "Computed", data_type),
            editable=True,
            mode="edit",
        )
        assert editor.kind == "none"
        assert not editor.has_editor
        assert editor.mode == "display"
        assert editor.control is None


def test_a_picker_without_its_schema_stays_on_the_display_half(qtbot):
    # A link field with no valid types has nothing to search, so the editor is not drawn.
    editor = build(
        qtbot,
        value=None,
        field=schema("entity", "Link", "entity"),
        editable=True,
        mode="edit",
    )
    assert not editor.has_editor
    assert editor.mode == "display"


def test_it_commits_through_the_client_and_emits(qtbot):
    context, client = context_for()
    row = client.rows_of("Version")[0]
    field = context.schema.fields("Version")["description"]
    from sg_widgets_core.filter import EntityRef

    editor = build(
        qtbot,
        context=context,
        value=row.get("description"),
        field=field,
        entity=EntityRef(type="Version", id=int(row["id"])),
        editable=True,
        mode="edit",
    )
    seen: list = []
    editor.value_changed.connect(seen.append)
    caret = editor.control.findChild(QLineEdit)
    type_into(caret, "turnover by qa")
    QTest.keyClick(caret, Qt.Key.Key_Return)
    written(qtbot, editor)
    assert seen == ["turnover by qa"]
    # The write answers the whole record but never resolves a dotted path, so the row is read
    # again on the field that was written (024_read_after_write).
    answer = client.search(
        "Version",
        SearchOptions(
            filters={"logical_operator": "and", "conditions": [["id", "is", int(row["id"])]]},
            fields=["description"],
        ),
    )
    assert answer.data[0].values["description"] == "turnover by qa"
    assert editor.error is None


def test_a_failed_write_shows_the_error(qtbot):
    context, client = context_for()
    row = client.rows_of("Version")[0]
    field = context.schema.fields("Version")["description"]
    from sg_widgets_core.filter import EntityRef

    editor = build(
        qtbot,
        context=context,
        value=row.get("description"),
        field=field,
        entity=EntityRef(type="Version", id=int(row["id"])),
        editable=True,
        mode="edit",
    )
    failures: list = []
    editor.error_changed.connect(failures.append)
    client.fail_next()
    caret = editor.control.findChild(QLineEdit)
    type_into(caret, "a write that fails")
    QTest.keyClick(caret, Qt.Key.Key_Return)
    written(qtbot, editor)
    assert editor.error, "the failed write said something"
    assert any(one for one in failures if one)
    line = editor.findChild(QWidget, "field-editor-error")
    assert line is not None and line.isVisibleTo(editor)


def test_without_an_entity_it_only_emits(qtbot):
    editor = build(
        qtbot,
        value="lighting",
        field=schema("sg_department", "Department", "text"),
        editable=True,
        mode="edit",
    )
    seen: list = []
    editor.value_changed.connect(seen.append)
    caret = editor.control.findChild(QLineEdit)
    type_into(caret, "comp")
    QTest.keyClick(caret, Qt.Key.Key_Return)
    spin(qtbot, 60)
    assert seen == ["comp"]
    assert editor.mode == "display"
    assert not editor.writing


def test_enter_opens_the_editor_and_escape_cancels(qtbot):
    editor = build(
        qtbot,
        value="lighting",
        field=schema("sg_department", "Department", "text"),
        editable=True,
    )
    modes: list = []
    editor.mode_changed.connect(modes.append)
    editor.display.setFocus()
    QTest.keyClick(editor.display, Qt.Key.Key_Return)
    spin(qtbot, 30)
    assert editor.mode == "edit" and modes == ["edit"]
    caret = editor.control.findChild(QLineEdit)
    type_into(caret, "comp")
    QTest.keyClick(caret, Qt.Key.Key_Escape)
    spin(qtbot, 30)
    assert editor.mode == "display"
    assert editor.value == "lighting", "a cancel restores the value the session opened on"


def test_a_popover_carries_the_label_and_its_buttons(qtbot):
    editor = build(
        qtbot,
        value="lighting",
        field=schema("sg_department", "Department", "text"),
        editable=True,
        editor_placement="popover",
        mode="edit",
    )
    spin(qtbot, 60)
    assert editor.placement == "popover"
    assert editor.popover is not None
    popup = editor.popover.findChild(QWidget, "field-editor-popover")
    assert popup is not None
    label = popup.findChild(QWidget, "field-editor-label")
    assert label is not None and label.text() == "Department"
    assert popup.findChild(QWidget, "field-editor-cancel") is not None
    assert popup.findChild(QWidget, "field-editor-save") is not None
    # A text field in a popover is a textarea, which is where there is room for one.
    assert editor.multiline is True


def test_a_read_only_field_never_opens(qtbot):
    field = schema("sg_department", "Department", "text")
    field.editable = False
    editor = build(qtbot, value="lighting", field=field, editable=True)
    assert editor.readonly
    editor.display.setFocus()
    QTest.keyClick(editor.display, Qt.Key.Key_Return)
    spin(qtbot, 30)
    assert editor.mode == "display"
    assert editor.control is None


def test_the_display_half_draws_the_value_by_its_data_type(qtbot):
    status = build(qtbot, value="ip", field=schema("sg_status_list", "Status", "status_list"))
    assert status.display.text() == "ip"
    from sg_widgets_qt.widgets.status_badge import StatusBadge

    assert status.display.findChild(StatusBadge) is not None

    link = build(
        qtbot,
        value={"type": "Shot", "id": 1234, "name": "sh010"},
        field=schema("entity", "Link", "entity", valid_types=["Shot"]),
    )
    from sg_widgets_qt.widgets.entity_chip import EntityChip

    assert link.display.findChild(EntityChip) is not None

    unset = build(qtbot, value=None, field=schema("sg_department", "Department", "text"))
    assert unset.display.text() == ""


def test_the_display_half_is_the_shared_field_value(qtbot):
    """Upstream mounts `FieldValue` here, so a url is a link and a checkbox its own mark."""
    from sg_widgets_qt.widgets.field_value import FieldValue

    cases = {
        "url": (
            schema("sg_uploaded_movie", "Uploaded Movie", "url"),
            {"url": "https://example.com/plate.mov", "name": "plate.mov", "link_type": "web"},
        ),
        "checkbox": (schema("flagged", "Flagged", "checkbox"), True),
        "color": (schema("color", "Gantt Bar Color", "color"), "255,0,0"),
    }
    for data_type, (field, value) in cases.items():
        editor = build(qtbot, value=value, field=field, editable=True)
        shown = editor.display.findChild(FieldValue)
        assert shown is not None, f"{data_type} draws no FieldValue"
        assert shown.data_type == data_type
    link = build(qtbot, value=cases["url"][1], field=cases["url"][0], editable=True)
    assert link.display.findChild(FieldValue).url == "https://example.com/plate.mov"


def test_an_editable_value_leaves_the_press_to_the_half_it_sits_in(qtbot):
    """A url opens itself on a press; on an editable half the press opens the editor."""
    from sg_widgets_qt.widgets.field_value import FieldValue

    field = schema("sg_uploaded_movie", "Uploaded Movie", "url")
    value = {"url": "https://example.com/plate.mov", "name": "plate.mov", "link_type": "web"}
    editable = build(qtbot, value=value, field=field, editable=True)
    shown = editable.display.findChild(FieldValue)
    assert shown.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert shown.focusPolicy() == Qt.FocusPolicy.NoFocus
    plain = build(qtbot, value=value, field=field, editable=False)
    other = plain.display.findChild(FieldValue)
    assert not other.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_the_popover_takes_the_caret_and_its_buttons_ride_the_ladder(qtbot):
    from sg_widgets_qt.primitives.button import Button
    from sg_widgets_qt.widgets.field_editor import POPOVER_BUTTON

    for step in ("sm", "md", "lg"):
        editor = build(
            qtbot,
            value="Plate delivered.",
            field=schema("description", "Description", "text"),
            editable=True,
            editor_placement="popover",
            size=step,
        )
        editor.set_mode("edit")
        spin(qtbot, 60)
        assert editor.popover is not None
        refused = Qt.WindowType.WindowDoesNotAcceptFocus
        assert not (editor.popover.windowFlags() & refused), "the caret cannot land inside"
        popup = editor.popover.content()
        buttons = popup.findChildren(Button)
        assert [one.text for one in buttons[-2:]] == ["Cancel", "Save"]
        assert {one.size for one in buttons[-2:]} == {POPOVER_BUTTON[step]}
        assert popup.findChild(QWidget, "field-editor-label") is not None
        editor.set_mode("display")
        spin(qtbot, 20)


def test_a_failed_write_says_so_in_destructive_under_the_control(qtbot):
    from sg_widgets_qt.widgets.field_error import FIELD_ERROR_SLOT, FieldError

    editor = build(
        qtbot,
        value="lighting",
        field=schema("sg_department", "Department", "text"),
        editable=True,
    )
    line = editor.findChild(FieldError, FIELD_ERROR_SLOT)
    assert line is not None, "the line under the control is not the shared FieldError"
    assert line.message is None
    assert not line.isVisible()
    editor.set_error("Permission denied.")
    spin(qtbot, 20)
    assert line.message == "Permission denied."
    editor.set_error(None)
    spin(qtbot, 20)
    assert line.message is None


def test_the_caller_s_own_renderer_draws_the_line_under_the_control(qtbot):
    from sg_widgets_qt.widgets.field_error import FIELD_ERROR_SLOT, FieldError

    made: list = []

    def render(message: str):
        widget = QWidget()
        widget.setObjectName("caller-error")
        made.append(message)
        return widget

    editor = build(
        qtbot,
        value="lighting",
        field=schema("sg_department", "Department", "text"),
        editable=True,
        error="Refused.",
        error_message=render,
    )
    line = editor.findChild(FieldError, FIELD_ERROR_SLOT)
    spin(qtbot, 20)
    assert made == ["Refused."]
    assert line.findChild(QWidget, "caller-error") is not None


def test_an_invalid_parse_keeps_the_edit_half_open_and_emits_nothing(qtbot):
    """`field-editor-invalid-float.js`: invalid input never emits and the editor stays."""
    editor = build(
        qtbot,
        value="1.777778",
        field=schema("ratio", "Movie Aspect Ratio", "float"),
        editable=True,
        mode="edit",
    )
    heard: list = []
    editor.value_changed.connect(heard.append)
    caret = editor.control.findChild(QLineEdit)
    type_into(caret, "not a number")
    spin(qtbot, 20)
    QTest.keyClick(caret, Qt.Key.Key_Return)
    spin(qtbot, 60)
    assert heard == []
    assert editor.value == "1.777778"
    assert editor.mode == "edit"
    assert editor.control is not None
    assert editor.control.message


def test_the_list_editor_takes_the_caller_s_message_like_every_other(qtbot):
    editor = build(
        qtbot,
        value="Type A",
        field=schema("sg_version_type", "Version Type", "list", valid_values=["Type A", "Type B"]),
        editable=True,
        mode="edit",
        error="Refused.",
    )
    spin(qtbot, 40)
    assert editor.control is not None
    assert editor.control.error == "Refused."


@pytest.mark.parametrize(
    ("data_type", "value"),
    [
        ("entity", {"type": "HumanUser", "id": 3, "name": "Ada Lovelace"}),
        ("multi_entity", [{"type": "HumanUser", "id": 3, "name": "Ada Lovelace"}]),
    ],
)
def test_cancel_on_a_link_popover_closes_it_and_keeps_the_hash(qtbot, data_type, value):
    """The restore hands the picker the value in its own shape, not the API's hash.

    Cancel on the Artist cell of a table left the popover standing: the picker's setter took
    the `{type, id, name}` hash and fell over before the close could run.
    """
    editor = build(
        qtbot,
        value=value,
        field=schema("user", "Artist", data_type, valid_types=["HumanUser"]),
        editable=True,
        editor_placement="popover",
        mode="edit",
    )
    modes: list = []
    editor.mode_changed.connect(modes.append)
    cancel = None
    for top in QApplication.topLevelWidgets():
        cancel = top.findChild(QWidget, "field-editor-cancel") or cancel
    assert cancel is not None, "the popover carries a Cancel button"
    QTest.mouseClick(cancel, Qt.MouseButton.LeftButton)
    spin(qtbot, 60)
    assert editor.mode == "display" and modes == ["display"]
    assert editor.value == value, "a cancel restores the value the session opened on"


def test_every_editor_the_dispatch_names_is_there():
    """The pickers are written: the editor reaches them by name, with nothing to fall back to."""
    from sg_widgets_qt.widgets import field_editor

    assert field_editor.ListPicker is not None
    assert field_editor.StatusPicker is not None
    assert not hasattr(field_editor, "_import")
