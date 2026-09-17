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
    for tag in ("h1", "h2", "h3"):
        rule = css[css.index(tag + " {") : css.index("}", css.index(tag + " {"))]
        assert dark.foreground in rule, tag
