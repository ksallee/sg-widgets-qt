"""The showcase and its driver: the window, the sidebar, a page, a stage and `tools/qa.py`."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from qtpy import QtWidgets

from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.showcase.page import WidgetPage, docs_dir
from sg_widgets_qt.showcase.prefs import Prefs
from sg_widgets_qt.showcase.window import ShowcaseWindow, read_index

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "tools" / "qa.py"

#: The driver starts a window and settles a read, so it is given room.
QA_TIMEOUT_S = 60


@pytest.fixture
def window(qapp):
    """A window on its own prefs, so a test never writes the developer's view."""
    made = ShowcaseWindow(prefs=Prefs(persist=False), context=demo_context())
    made.resize(1200, 900)
    made.show()
    qapp.processEvents()
    yield made
    made.close()


def _run_qa(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(QA), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=QA_TIMEOUT_S,
    )


def test_the_window_builds(window):
    assert window.isVisible()
    assert window.current
    assert window.page is not None


def test_the_sidebar_lists_every_page_of_the_index(window):
    index = read_index()
    listed = set(window.page_names())
    for section in ("start", "core"):
        for name in index.get(section, []):
            if (docs_dir() / section / f"{name}.md").is_file():
                assert f"{section}/{name}" in listed
    for group in index.get("widgets", []):
        for name in group["items"]:
            if (docs_dir() / "widgets" / f"{name}.md").is_file():
                assert f"widgets/{name}" in listed


def test_the_sidebar_search_filters_the_rows(window):
    window.sidebar.search.set_text("status")
    shown = [row for row in window.sidebar.rows if row.isVisible()]
    assert shown
    assert all(
        "status" in row.data_name.lower() or "status" in row.label().lower() for row in shown
    )
    window.sidebar.search.set_text("")
    assert all(row.isVisible() for row in window.sidebar.rows)


def test_opening_hello_builds_a_stage(window, qapp):
    page = window.open_page("hello")
    qapp.processEvents()
    assert isinstance(page, WidgetPage)
    assert [stage.data_name for stage in page.stages] == ["hello"]
    stage = page.stages[0]
    assert stage.error == ""
    assert stage.widget is not None
    assert stage.findChild(QtWidgets.QWidget, "load-entity-types") is not None


def test_a_widget_page_draws_its_props_table(window, qapp):
    page = window.open_page("status-badge")
    qapp.processEvents()
    assert page.tables
    assert page.tables[0].row_count > 0


def test_the_theme_switch_repaints_the_stage(window, qapp):
    page = window.open_page("hello")
    qapp.processEvents()
    stage = page.stages[0]
    light = stage.grab().toImage()
    window.prefs.set("theme", "dark")
    qapp.processEvents()
    dark = stage.grab().toImage()
    assert light.pixel(4, 4) != dark.pixel(4, 4)


def test_qa_writes_a_shot(tmp_path):
    target = tmp_path / "shots" / "hello.png"
    done = _run_qa("--page", "hello", "--shot", str(target))
    assert done.returncode == 0, done.stderr
    assert target.is_file()
    assert json.loads(done.stdout)["shot"] == str(target)


def test_a_drive_that_passes_exits_zero(tmp_path):
    drive = tmp_path / "pass.py"
    drive.write_text(
        "def drive(page, wait, find, prefs):\n"
        "    wait(10)\n"
        "    return {'verdict': 'PASS', 'stages': len(page.stages)}\n",
        encoding="utf-8",
    )
    done = _run_qa("--page", "hello", "--drive", str(drive))
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["result"]["stages"] == 1


def test_a_drive_that_fails_exits_one(tmp_path):
    drive = tmp_path / "fail.py"
    drive.write_text(
        "def drive(page, wait, find, prefs):\n    return {'verdict': 'FAIL nothing here'}\n",
        encoding="utf-8",
    )
    done = _run_qa("--page", "hello", "--drive", str(drive))
    assert done.returncode == 1
    assert json.loads(done.stdout)["result"]["verdict"].startswith("FAIL")


def test_a_drive_reaches_the_demo_and_the_view(tmp_path):
    drive = tmp_path / "read.py"
    drive.write_text(
        "def drive(page, wait, find, prefs):\n"
        "    prefs.set('theme', 'dark')\n"
        "    wait(20)\n"
        "    button = find('load-entity-types')\n"
        "    output = find('demo-output')\n"
        "    return {\n"
        "        'verdict': 'PASS' if button is not None and output is not None else 'FAIL',\n"
        "        'theme': prefs.theme,\n"
        "    }\n",
        encoding="utf-8",
    )
    done = _run_qa("--page", "hello", "--drive", str(drive))
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["result"]["theme"] == "dark"


def test_a_demo_radio_settles_on_the_one_pressed(qapp):
    """A press on one of a demo's radio toggles picks it, and does not loop.

    Each toggle reports when it goes down *and* when it comes up, so a handler that reads
    every report as a pick sets the others down, is reported for each of them, and never
    returns. The showcase died on a press of Load more.
    """
    from sg_widgets_qt.showcase.demos.entity_table import _radio

    holder = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(holder)
    picked: list = []
    made = _radio(holder, layout, (("a", "A"), ("b", "B"), ("c", "C")), "mode", picked.append)
    assert picked == ["a"]
    assert [key for key, toggle in made.items() if toggle.checked] == ["a"]

    made["b"].set_checked(True)
    assert picked == ["a", "b"]
    assert [key for key, toggle in made.items() if toggle.checked] == ["b"]

    # The one already down stays down when it is pressed again.
    made["b"].set_checked(False)
    assert [key for key, toggle in made.items() if toggle.checked] == ["b"]
    holder.deleteLater()


def test_a_demo_toggle_is_bordered_before_it_is_pressed(qapp):
    """A demo's toggles read as controls at rest.

    Upstream's `toggle` class carries `border border-border bg-background` and only adds the
    `accent` ground under `aria-pressed`, so a toggle nobody has pressed still looks pressable.
    """
    from sg_widgets_qt.showcase import chrome

    made = chrome.toggle("Compact", size="sm")
    assert made.variant == "outline"
    assert made.checked is False
    made.deleteLater()


def test_the_header_holds_a_project_picker_bound_to_the_source(qtbot):
    """The header's project control is the real picker over the mock's projects, and a pick scopes the demos."""
    from sg_widgets_core.filter import EntityRef
    from sg_widgets_qt.showcase.context import demo_context
    from sg_widgets_qt.showcase.prefs import Prefs
    from sg_widgets_qt.showcase.window import ShowcaseWindow
    from sg_widgets_qt.widgets.project_picker import ProjectPicker

    window = ShowcaseWindow(prefs=Prefs(persist=False), context=demo_context())
    qtbot.addWidget(window)
    picker = window.header.project
    assert isinstance(picker, ProjectPicker)
    assert picker.value == EntityRef("Project", window.context.project_id)
    assert picker.isEnabled()
    window.header.project_picked.emit(71, "Second show")
    assert window.context.project_id == 71
    assert window.context.project_name == "Second show"


def test_prose_headings_take_the_foreground_in_dark(qtbot):
    """A heading in the docs prose is painted in `foreground`, not the document's black default."""
    from sg_widgets_qt.showcase import markdown
    from sg_widgets_qt.theme import theme_for

    dark = theme_for("default", dark=True)
    css = markdown.stylesheet(dark)
    for tag in ("h1", "h2", "h3", "li", "td"):
        rule = css[css.index(tag + " {") : css.index("}", css.index(tag + " {"))]
        assert dark.foreground in rule, tag


def test_the_entity_table_demo_sorts_on_the_columns_it_shows(qtbot):
    """`options` is the visible columns, flat, and it follows them.

    Upstream hands the picker `columns.map((column) => column.path)`, so a toolbar sorts on
    what its table shows. Ours used to hand it every column the demo can show, which offered
    fields no reader could see. It goes through `options` now, so the linked column the table
    shows is on the list without the reader having to walk a link to it.
    """
    import time

    from sg_widgets_core.collection import CollectionColumn
    from sg_widgets_qt.showcase.demos.entity_table import (
        PATHS,
        SHOWN,
        EntityTableDemo,
        table_context,
    )

    demo = EntityTableDemo(table_context(demo_context()))
    qtbot.addWidget(demo)
    picker = demo._sort
    assert picker is not None
    assert picker.options == list(SHOWN)
    # The flat list takes the place of the nested one, which is left alone.
    assert picker.paths is None

    end = time.time() + 5.0
    while time.time() < end and not demo.table.columns:
        QtWidgets.QApplication.processEvents()
        qtbot.wait(5)
    resolved = [column.path for column in demo.table.columns]
    assert resolved == list(SHOWN)
    assert picker.options == resolved
    # A column through a link is shown and therefore offered.
    assert "entity.Shot.sg_turnover_date" in resolved
    # The two the demo can show but does not are not on offer.
    assert [path for path in PATHS if path not in resolved]
    assert not [path for path in picker.options if path not in resolved]

    # A column dropped from the table takes its path off the list with it.
    kept = [column for column in demo.table.columns if column.path != "description"]
    demo.table.columns_changed.emit(kept)
    QtWidgets.QApplication.processEvents()
    assert picker.options == [column.path for column in kept]
    assert isinstance(kept[0], CollectionColumn)


def field_editor_demo(qtbot):
    """The field-editor demo on a themed window, the way the showcase stands it up."""
    from sg_widgets_qt.showcase.demos.field_editor import FieldEditorDemo
    from sg_widgets_qt.theme import apply_theme, theme_for

    root = QtWidgets.QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(900, 700)
    column = QtWidgets.QVBoxLayout(root)
    demo = FieldEditorDemo(demo_context(), root)
    column.addWidget(demo)
    root.show()
    qtbot.waitExposed(root)
    # The window is held on the demo, so neither goes while the test still drives it.
    demo.test_root = root
    return demo


def test_the_field_editor_toggle_shows_the_values_again(qtbot):
    """The second press on "Edit every field" puts every row back on its value.

    The press moves the focus off the row that holds it, and an editor commits and closes on
    a blur, so a toggle that reads its state back off the rows finds one of them closed and
    opens them all again. The button holds what it last asked for instead.
    """
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest

    demo = field_editor_demo(qtbot)
    toggle = demo.toggle

    def press() -> None:
        QTest.mouseClick(
            toggle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, toggle.rect().center()
        )
        for _ in range(40):
            QtWidgets.QApplication.processEvents()
        qtbot.wait(120)

    press()
    assert [one.mode for one in demo._inline] == ["edit"] * len(demo._inline)
    press()
    assert [one.mode for one in demo._inline] == ["display"] * len(demo._inline)
    press()
    assert [one.mode for one in demo._inline] == ["edit"] * len(demo._inline)


def test_cancelling_a_popover_edit_leaves_no_window_behind(qtbot):
    """A value on its way off the display half is hidden before it is let go.

    A widget reparented to None is a top-level window of its own, and one Qt never saw
    explicitly hidden stands as a stray window over the page until the deferred delete runs.
    The value is rebuilt on every cancel, so this was a window per cancelled edit.
    """
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest

    demo = field_editor_demo(qtbot)
    editor = demo.findChild(QtWidgets.QWidget, "field-editor-popover-text")
    assert editor is not None
    QTest.mouseClick(
        editor.display,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        editor.display.rect().center(),
    )
    qtbot.wait(150)
    assert editor.mode == "edit" and editor.popover is not None
    # Typed into, the way a reader edits: the draft reaches the value, and the value the
    # display half draws is built again under the popover.
    caret = editor.control.findChild(QtWidgets.QPlainTextEdit) or editor.control.findChild(
        QtWidgets.QLineEdit
    )
    assert caret is not None
    caret.setFocus(Qt.FocusReason.OtherFocusReason)
    QTest.keyClicks(caret, " Cancelled.")
    qtbot.wait(120)
    cancel = editor.popover.findChild(QtWidgets.QWidget, "field-editor-cancel")
    assert cancel is not None
    QTest.mouseClick(
        cancel, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, cancel.rect().center()
    )
    # Paints and posted events only: a nested event loop would run the deferred delete and
    # take the stray away before it could be seen, which is not what the showcase does.
    for _ in range(40):
        QtWidgets.QApplication.processEvents()
    assert editor.mode == "display"
    strays = [
        one.objectName()
        for one in QtWidgets.QApplication.topLevelWidgets()
        if one.isVisible() and one.objectName() == "field-editor-value"
    ]
    assert not strays, f"a value was left standing as a window of its own: {strays}"


def test_a_demo_rebuilt_with_its_palette_open_takes_the_dialog_with_it(qtbot, qapp):
    """The toolbar rebuilds the demo under an open palette; the dialog goes with it.

    A command dialog hangs off the host window and holds the search box inside it, so neither
    is a child of the widget that built them. A demo rebuilt by a size or a density step used
    to leave the dialog standing over the application with nothing behind it.
    """
    import time

    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest

    from sg_widgets_qt.showcase.stage import DemoStage

    prefs = Prefs(persist=False)
    root = QtWidgets.QWidget()
    qtbot.addWidget(root)
    root.resize(900, 600)
    column = QtWidgets.QVBoxLayout(root)
    stage = DemoStage("global-search", "Global search", demo_context(), prefs, root)
    column.addWidget(stage)
    root.show()
    qtbot.waitExposed(root)
    end = time.time() + 5.0
    while time.time() < end and not stage.ready:
        qapp.processEvents()
        qtbot.wait(10)

    palette = stage.findChild(QtWidgets.QWidget, "global-search-palette")
    assert palette is not None
    trigger = palette.trigger()
    assert trigger is not None
    QTest.mouseClick(
        trigger, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, trigger.rect().center()
    )
    qtbot.wait(200)
    assert palette.open
    assert [
        one for one in QtWidgets.QApplication.topLevelWidgets()
        if one.isVisible() and one.objectName() == "dialog-content"
    ], "the palette never opened its dialog"

    # The size step is one of the keys a stage rebuilds on.
    prefs.set("size", "lg")
    qtbot.wait(400)
    for _ in range(10):
        qapp.processEvents()
        qtbot.wait(40)
    strays = [
        one.objectName()
        for one in QtWidgets.QApplication.topLevelWidgets()
        if one.isVisible() and one.objectName() == "dialog-content"
    ]
    assert not strays, f"the rebuilt demo left its dialog standing: {strays}"


def test_the_density_control_is_offered_only_where_the_demo_takes_one(qtbot):
    """A stage whose demo has no `set_density` hides the control rather than drawing a no-op."""
    from sg_widgets_qt.showcase.stage import DemoStage

    bare = DemoStage("hello", prefs=Prefs(persist=False), context=demo_context())
    qtbot.addWidget(bare)
    assert bare.widget is not None
    assert bare.toolbar.controls["density"].isHidden()

    dense = DemoStage("search-control", prefs=Prefs(persist=False), context=demo_context())
    qtbot.addWidget(dense)
    assert dense.widget is not None
    assert not dense.toolbar.controls["density"].isHidden()


def test_the_hello_demo_shows_the_leaf_gallery(window, qapp):
    """The gallery of leaf primitives stands under the buttons, reached by a plain import."""
    page = window.open_page("hello")
    qapp.processEvents()
    assert page.stages[0].findChild(QtWidgets.QWidget, "leaf-gallery") is not None
