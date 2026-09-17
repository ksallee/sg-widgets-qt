"""What the ten picker tests share: a mock context, a themed window, and a settle loop."""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_core.schema import FieldSchema
from sg_widgets_qt.theme import apply_theme, theme_for

#: The two projects the fixtures carry, and the type whose statuses differ between them.
PROJECT = 70
OTHER_PROJECT = 71


class Counting:
    """A client that counts the calls that reached it, by method name."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.reads: dict = {}

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._client, name)
        if not callable(value):
            return value

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.reads[name] = self.reads.get(name, 0) + 1
            return value(*args, **kwargs)

        return counted


def context_for(latency_ms: int = 0):
    """A context over the mock, and the counting client under it."""
    client = Counting(MockClient(seed=1, latency_ms=latency_ms, now=MOCK_NOW))
    return create_sg_context(client, SgContextOptions()), client


def window(qtbot, width: int = 520, height: int = 160) -> QWidget:
    """A themed top-level wide enough for a chip row."""
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(width, height)
    return root


def mount(qtbot, picker: QWidget, root: QWidget) -> QWidget:
    """Place a picker on the window and show it, holding the window on the picker."""
    picker.setGeometry(10, 10, root.width() - 20, 40)
    root.show()
    qtbot.waitExposed(root)
    picker.test_root = root
    return picker


def spin(qtbot, ms: int = 50) -> None:
    """Turn the event loop for a while, so a queued answer lands."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)


def settled(qtbot, picker: Any, ms: int = 900) -> None:
    """Spin until the picker's list has rows, or the time is up."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)
        if picker.control.items:
            return
    QApplication.processEvents()


def list_field(
    name: str = "sg_shot_type",
    mandatory: bool = False,
    valid_values: list | None = None,
    display_values: dict | None = None,
    hidden_values: list | None = None,
) -> FieldSchema:
    """A `list` field schema, the way the demos and the tests hand one in."""
    return FieldSchema(
        name=name,
        display_name="Shot Type",
        entity_type="Shot",
        data_type="list",
        editable=True,
        mandatory=mandatory,
        unique=False,
        valid_values=valid_values
        if valid_values is not None
        else ["VFX", "2D", "Full CG", "Trailer", "Marketing", "Look Dev"],
        display_values=display_values
        if display_values is not None
        else {"2D": "Two D", "Look Dev": "Lookdev"},
        hidden_values=hidden_values if hidden_values is not None else ["Marketing", "Trailer"],
    )
