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
