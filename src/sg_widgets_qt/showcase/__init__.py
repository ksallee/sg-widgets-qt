"""The showcase: the sidebar, the pages, the demo stages and the toolbar they wear.

`python -m sg_widgets_qt.showcase` opens it. `tools/qa.py` opens the same window offscreen and
drives it.
"""
from __future__ import annotations

__all__ = ["DemoContext", "DemoStage", "Prefs", "ShowcaseWindow", "WidgetPage"]


def __getattr__(name: str) -> object:
    # Imported lazily so `python -m sg_widgets_qt.showcase --help` costs no QWidget.
    if name == "Prefs":
        from .prefs import Prefs

        return Prefs
    if name == "DemoContext":
        from .context import DemoContext

        return DemoContext
    if name == "ShowcaseWindow":
        from .window import ShowcaseWindow

        return ShowcaseWindow
    if name == "WidgetPage":
        from .page import WidgetPage

        return WidgetPage
    if name == "DemoStage":
        from .stage import DemoStage

        return DemoStage
    raise AttributeError(name)
