"""A `url` field, as a web link.

Ported from `packages/react/src/registry/sg/components/url-editor.tsx`.

    editor = UrlEditor(value=UrlValue(url="https://example.com/plate.mov", name="plate.mov"))
    editor.committed.connect(write)

The only accepted write is an object holding `url`: a bare string is a 400, the url itself is
validated, and a raw space is the one character measured to fail. With no name the field reads back
the whole url as its name. Uploads mint an Attachment through a separate flow and are out of scope
here (field_types/url).
"""
from __future__ import annotations

from typing import Any, Callable

from qtpy import QtWidgets

from sg_widgets_core.edit import UrlWriteValue, parse_url_input
from sg_widgets_core.render import UrlValue
from sg_widgets_core.schema import FieldSchema

from ..primitives.input import Input
from .value_editor import VALUE_EDITOR_GAP, EditorNote, ValueEditor, ValueSession, fade_disabled

__all__ = ["LOCAL_NOTE", "UrlEditor"]

#: What the control says instead of showing an empty box on a value it will not edit.
LOCAL_NOTE = "This value is a local path. Only web links are edited here."


def _half(value: Any, key: str) -> str:
    """One field of a stored url value, whether it arrived as a map or as a `UrlValue`."""
    if value is None:
        return ""
    found = value.get(key) if isinstance(value, dict) else getattr(value, key, None)
    return "" if found is None else str(found)


class UrlEditor(ValueEditor):
    """A `url` field: the address, then its name."""

    def __init__(
        self,
        value: UrlValue | dict | None = None,
        field: FieldSchema | None = None,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "https://example.com/plate.mov",
        name_placeholder: str = "Name",
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[UrlWriteValue | None], None] | None = None,
        on_error_change: Callable[[str | None], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__("url-editor", size=size, error_message=error_message, parent=parent)
        self._stored = value
        self._name_placeholder = name_placeholder

        self.use_session(
            ValueSession(
                value,
                # The stored object carries more than a link; the two edited halves are all
                # this reads.
                format=lambda stored: {
                    "url": _half(stored, "url"),
                    "name": _half(stored, "name"),
                },
                parse=lambda draft: parse_url_input(
                    str(draft.get("url", "")), str(draft.get("name", ""))
                ),
                # A committed link is a fresh object, so every commit is a write.
                same=lambda _next, _current: False,
                error=error,
                invalid=invalid,
                parent=self,
            )
        )
        self._build()

        self.set_placeholder(placeholder)
        self.set_field(field)
        self.set_invalid(invalid)
        self.set_readonly(readonly)
        self.set_disabled(disabled)
        self.connect_callbacks(on_value_change, on_error_change)
        self._refresh()

    # --- the parts -----------------------------------------------------------------------

    def _build(self) -> None:
        column = QtWidgets.QWidget(self)
        column.setObjectName("url-editor-fields")
        stack = QtWidgets.QVBoxLayout(column)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(VALUE_EDITOR_GAP)

        self._url = Input(placeholder=self.placeholder, size=self.size, parent=column)
        self._url.setObjectName("url-editor-url")
        self._session.bind(self._url, "url")
        stack.addWidget(self._url)

        self._name = Input(placeholder=self._name_placeholder, size=self.size, parent=column)
        self._name.setObjectName("url-editor-name")
        self._session.bind(self._name, "name")
        stack.addWidget(self._name)
        self.add_control(column)

        self._note = EditorNote("", parent=self)
        self._note.setObjectName("url-editor-note")
        self.add_control(self._note)

        self._session.committed.connect(self._on_committed)

    def _on_committed(self, value: object) -> None:
        self._stored = value
        self._refresh()

    # --- props ---------------------------------------------------------------------------

    @property
    def value(self) -> Any:
        """The stored object. Only the web-link shape is edited here (field_types/url)."""
        return self._stored

    def set_value(self, value: UrlValue | dict | None) -> None:
        self._stored = value
        self._session.set_value(value)
        self._refresh()

    @property
    def local_only(self) -> bool:
        """True on a value carrying paths and no address, which this control will not edit."""
        return _half(self._stored, "link_type") == "local"

    @property
    def name_placeholder(self) -> str:
        """The placeholder of the second input."""
        return self._name_placeholder

    def set_name_placeholder(self, value: str) -> None:
        self._name_placeholder = value
        self._name.setPlaceholderText(value)

    @property
    def url_input(self) -> Input:
        """The address."""
        return self._url

    @property
    def name_input(self) -> Input:
        """The name beside the address."""
        return self._name

    def _refresh(self) -> None:
        # A local value carries paths and no url at all, so the control says so rather than
        # showing an empty box (field_types/url).
        local = self.local_only
        self._note.set_text(LOCAL_NOTE if local else "")
        self._url.setEnabled(self.isEnabled() and not local)
        self._name.setEnabled(self.isEnabled() and not local)

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        self._url.set_size(size)
        self._name.set_size(size)

    def _apply_placeholder(self, placeholder: str) -> None:
        self._url.setPlaceholderText(placeholder)
        super()._apply_placeholder(placeholder)

    def _apply_state(self) -> None:
        url = getattr(self, "_url", None)
        if url is None:
            return
        for control in (self._url, self._name):
            control.setReadOnly(self.readonly)
            control.set_invalid(self.reads_invalid)
            fade_disabled(control)
        name = self.field_name()
        if name:
            self._url.setAccessibleName(name)
        self._name.setAccessibleName("Link name")
        self._refresh()
