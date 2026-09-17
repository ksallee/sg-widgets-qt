"""One module per demo, found by the stage through `importlib`.

A demo is `<item name in snake_case>.py` and defines one function:

    def build(context: DemoContext, parent: QWidget) -> QWidget

`context` is what the toolbar's source select built: `context.client` reads, `context.project_id`
is the project to scope to, `context.schema` and `context.statuses` are the shared services, and
`context.reads` counts the calls a drive asserts on. A read runs on a worker
(`sg_widgets_qt.workers`), never on the GUI thread.

Every widget a demo builds sets its object name to its slot name, which is how a drive finds it.
"""
from __future__ import annotations

__all__: list[str] = []
