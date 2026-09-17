"""One person, chosen by server-side search.

The port of `apps/site/src/demos/user-picker/Demo.tsx`: one person or script, a search matched on
the name, the address or the login, people only, inactive people included, a bare reference
resolved on the way in, the three heights and the three states.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import placeholder_name

from ...widgets.user_picker import UserPicker
from ..context import DemoContext
from ._pickers import column, field, poll_ready, section

__all__ = ["build"]

#: A person the fixtures always carry, for the examples that come with a value.
PRESET = EntityRef(type="HumanUser", id=20, name="Ada Lovelace")

#: A bare reference: type and id, no name. Resolved on the way in by one id-in read.
BARE = EntityRef(type="HumanUser", id=22)

SIZES = (("sm", "Small"), ("md", "Medium, the default"), ("lg", "Large"))


class UserPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("user-picker-demo")
        self._context = context
        self._pickers: list = []
        #: False until every value handed in has a name.
        self.demo_ready = True

        body = column(self)
        body.addWidget(
            section(
                "One person or script",
                field("One person or script, clearable", self._picker(), parent=self),
                case="single",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Matched on the name, the address or the login",
                field(
                    "Matched on the name, the address or the login",
                    self._picker(placeholder="Try ada, ada.lo or @example.studio…"),
                    parent=self,
                ),
                case="by-address",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "People only",
                field(
                    "People only, no script users",
                    self._picker(include_api_users=False),
                    parent=self,
                ),
                case="people-only",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Inactive people included",
                field("Inactive people included", self._picker(include_inactive=True), parent=self),
                case="inactive",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Bare reference, resolved on the way in",
                field(
                    "Type and id in, name resolved on the way in",
                    self._picker(value=BARE),
                    parent=self,
                ),
                case="hydrate",
                parent=self,
            )
        )

        states = [
            field(caption, self._picker(value=PRESET, size=size, follow=False), parent=self)
            for size, caption in SIZES
        ]
        states.extend(
            field(flag.capitalize(), self._picker(value=PRESET, **{flag: True}), parent=self)
            for flag in ("disabled", "readonly", "invalid")
        )
        body.addWidget(
            section(
                "Sizes, then disabled, read-only, invalid", *states, case="states", parent=self
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _picker(self, follow: bool = True, **props: Any) -> UserPicker:
        picker = UserPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def _pending(self) -> bool:
        """True while a value handed in still reads as `Type id`."""
        for picker in self.findChildren(UserPicker):
            value = picker.value
            if value is None:
                continue
            labels = picker.control.labels
            if not labels or labels[0] == placeholder_name(value):
                return True
        return False

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The three heights are their own example."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return UserPickerDemo(context, parent)
