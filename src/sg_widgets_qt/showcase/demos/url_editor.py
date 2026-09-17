"""The url-editor demo: a web link, an unset field, and a local path it will not edit.

The port of `apps/site/src/demos/url-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.render import UrlValue
from sg_widgets_core.schema import FieldSchema

from ...widgets.url_editor import UrlEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]

LOCAL = UrlValue(
    link_type="local",
    name="plate.exr",
    local_path_mac="/Volumes/shows/sh010/plate.exr",
)

WEB = UrlValue(
    url="https://example.com/plate.mov",
    name="plate.mov",
    link_type="web",
)

FIELD = FieldSchema(
    name="sg_uploaded_movie",
    display_name="Uploaded Movie",
    entity_type="Version",
    data_type="url",
    editable=True,
    mandatory=False,
    unique=False,
)


class UrlEditorDemo(QtWidgets.QWidget):
    """Three url editors: a web link, an unset field, and a local path."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("url-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.cases = [
            _editors.Case("web link", UrlEditor(value=WEB, field=FIELD)),
            _editors.Case("unset", UrlEditor(value=None)),
            _editors.Case("local path", UrlEditor(value=LOCAL)),
        ]
        for case in self.cases:
            _editors.bind(case, case.editor.value)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(_editors.rows(self, self.cases))

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for case in self.cases:
            case.editor.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return UrlEditorDemo(context, parent)
