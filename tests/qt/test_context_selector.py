"""The context: its trigger, its assigned tasks, its recents and the tree in the third section."""
from __future__ import annotations

import threading

import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QWidget

from sg_widgets_core.filter import EntityRef
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.context_selector import (
    ContextSelector,
    MyTask,
    WorkContext,
    context_from_path,
)
from sg_widgets_qt.workers import default_pool

SETTLE_MS = 8000
ADA = EntityRef(type="HumanUser", id=20, name="Ada Lovelace")
PROJECT = EntityRef(type="Project", id=70, name="Blue Moon Rising")
SHOT = EntityRef(type="Shot", id=862, name="sh010_0010")
TASK = EntityRef(type="Task", id=5700, name="Comp")
HELD = WorkContext(project=PROJECT, entity=SHOT, task=TASK)


class Counting:
    """The mock client with the Task search counted, and one that can be held or fail."""

    def __init__(self, client) -> None:
        self._client = client
        self.searches: list[str] = []
        self.fail = False
        self.gate = threading.Event()
        self.gate.set()

    def __getattr__(self, name):
        return getattr(self._client, name)

    def search(self, entity_type, options=None):
        self.searches.append(entity_type)
        if entity_type == "Task":
            self.gate.wait(5.0)
            if self.fail:
                raise RuntimeError("the task list is not answering")
        return self._client.search(entity_type, options)


@pytest.fixture(autouse=True)
def drain_the_pool():
    """Let every read answer before the next test, so a job never outlives its widget."""
    yield
    default_pool().wait(5000)


@pytest.fixture
def host(qtbot):
    widget = QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(520, 480)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def context():
    built = demo_context(latency_ms=0)
    built.context.client = Counting(built.context.client)
    return built


def make(host, qtbot, context, **props) -> ContextSelector:
    props.setdefault("work_context", HELD)
    props.setdefault("current_user", ADA)
    selector = ContextSelector(host, context=context.context, **props)
    qtbot.addWidget(selector)
    selector.show()
    return selector


def settle(qtbot, selector: ContextSelector) -> None:
    qtbot.waitUntil(lambda: not selector.tasks_control().loading, timeout=SETTLE_MS)


def test_the_trigger_carries_the_three_parts_as_chips(host, qtbot, context):
    selector = make(host, qtbot, context)
    assert [ref.type for ref in selector.trigger().refs] == ["Project", "Shot", "Task"]
    assert selector.label == "Comp"
    selector.set_work_context(WorkContext())
    assert selector.trigger().refs == []
    assert selector.label == "No context"


def test_the_assigned_tasks_are_read_and_grouped_by_project(host, qtbot, context):
    selector = make(host, qtbot, context)
    settle(qtbot, selector)
    assert "Task" in context.context.client.searches
    model = selector.tasks_control().model
    kinds = [model.data(model.index(i, 0), Roles.KIND) for i in range(model.rowCount())]
    assert kinds[0] == "heading"
    assert any(isinstance(model.row_at(i), MyTask) for i in range(model.rowCount()))


def test_nothing_is_read_without_a_current_user(host, qtbot, context):
    selector = make(host, qtbot, context, current_user=None)
    qtbot.wait(120)
    assert "Task" not in context.context.client.searches
    selector.set_current_user(ADA)
    settle(qtbot, selector)
    assert "Task" in context.context.client.searches


def test_a_stale_answer_is_dropped_when_the_person_changes_first(host, qtbot, context):
    counted = context.context.client
    counted.gate.clear()
    selector = make(host, qtbot, context)
    qtbot.waitUntil(lambda: counted.searches.count("Task") == 1, timeout=SETTLE_MS)
    selector.set_current_user(EntityRef(type="HumanUser", id=21, name="Anna van der Meer"))
    counted.gate.set()
    settle(qtbot, selector)
    qtbot.wait(80)
    assert counted.searches.count("Task") == 2
    assert selector.tasks_control().view in ("rows", "empty")


def test_the_empty_line_shows_when_the_person_has_no_task(host, qtbot, context):
    selector = make(
        host,
        qtbot,
        context,
        current_user=EntityRef(type="HumanUser", id=999, name="Nobody"),
        empty_label="No rows",
    )
    selector.set_open(True)
    settle(qtbot, selector)
    assert selector.tasks_control().view == "empty"
    line = selector.tasks_control().findChild(QWidget, "context-tasks-empty")
    assert not line.isHidden()
    assert line.label == "No rows"


def test_the_error_line_shows_what_the_failed_read_said(host, qtbot, context):
    context.context.client.fail = True
    selector = make(host, qtbot, context)
    with qtbot.waitSignal(selector.tasks_control().error, timeout=SETTLE_MS) as caught:
        pass
    assert "not answering" in caught.args[0]
    assert selector.tasks_control().view == "error"


def test_up_and_down_and_enter_pick_a_task_and_set_all_three_parts(host, qtbot, context):
    selector = make(host, qtbot, context, work_context=WorkContext())
    settle(qtbot, selector)
    taken: list[WorkContext] = []
    selector.work_context_changed.connect(taken.append)
    control = selector.tasks_control()
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Up))
    control.handle_key(_key(Qt.Key.Key_Return))
    assert taken
    assert taken[0].task is not None
    assert taken[0].project is not None


def test_a_pick_leads_the_recents_and_closes_the_popover(host, qtbot, context):
    selector = make(host, qtbot, context, recents=[])
    selector.set_open(True)
    assert selector.open
    with qtbot.waitSignal(selector.recents_changed, timeout=SETTLE_MS) as caught:
        selector.apply(HELD)
    assert caught.args[0][0] is HELD
    assert not selector.open


def test_escape_closes_the_popover(host, qtbot, context):
    selector = make(host, qtbot, context)
    selector.set_open(True)
    assert selector.popover().handle_key(_key(Qt.Key.Key_Escape))
    assert not selector.open


def test_the_tree_is_scoped_to_the_project_on_show(host, qtbot, context):
    selector = make(host, qtbot, context)
    assert selector.tree().root_path == "/Project/70"
    selector.set_work_context(WorkContext())
    assert selector.tree().root_path == "/"


def test_a_path_becomes_the_three_parts_it_implies():
    path = [PROJECT, EntityRef(type="Sequence", id=3, name="sh010"), SHOT, TASK]
    held = context_from_path(TASK, path)
    assert held.project is PROJECT
    assert held.entity is SHOT
    assert held.task is TASK
    # A row that is not a Task is the entity itself, and a Project is only a project.
    assert context_from_path(SHOT, path).entity is SHOT
    assert context_from_path(PROJECT, path).entity is None


def _key(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier)
