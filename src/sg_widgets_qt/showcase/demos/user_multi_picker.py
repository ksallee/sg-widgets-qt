"""Several people, chosen by server-side search.

The port of `apps/site/src/demos/user-multi-picker/Demo.tsx`: several people at once, a token
field with chips already in it, people only with the inactive included, bare references resolved
on the way in, the three summary modes wide and narrow, a capped chip row, the three heights and
the three states.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import placeholder_name

from ...widgets.user_multi_picker import UserMultiPicker
from ..context import DemoContext
from ._pickers import boxed, column, field, poll_ready, section

__all__ = ["build"]

PRESET = [
    EntityRef(type="HumanUser", id=20, name="Ada Lovelace"),
    EntityRef(type="HumanUser", id=22, name="Cleo Dias"),
]

#: Five, so `ellipsis` has something to count and `max` something to cut.
FIVE = [
    *PRESET,
    EntityRef(type="HumanUser", id=23, name="Dmitri Ivanov"),
    EntityRef(type="HumanUser", id=25, name="Farid Nasser"),
    EntityRef(type="HumanUser", id=26, name="Grace Ono"),
]

#: A token field with chips already in it, for the keyboard.
TOKENS = FIVE[:3]

#: Bare references: type and id, no name.
BARE = [EntityRef(type="HumanUser", id=22), EntityRef(type="HumanUser", id=25)]

SUMMARIES = ("chips", "ellipsis", "count")
SIZES = ("sm", "md", "lg")

#: The three inert states, with the caption upstream's demo writes over each.
STATES = (("disabled", "Disabled"), ("readonly", "Read-only"), ("invalid", "Invalid"))


def narrow(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """`max-w-80 w-full`: the control fills its box, and the box stops at 20rem.

    `boxed` caps the control at 20rem and follows it with a spacer. A layout hands a child
    carrying no stretch its size hint, so the control settled at its own width rather than at
    the cap and the chip fit cut against the wrong room. The stretch is given here rather than
    in `_pickers.boxed`, which demos outside this wave share.
    """
    holder = boxed(widget)
    holder.layout().setStretch(0, 1)
    return holder


class UserMultiPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("user-multi-picker-demo")
        self._context = context
        self._pickers: list = []
        self.demo_ready = True

        body = column(self)
        body.addWidget(
            section(
                "Several people or scripts",
                field("Several people at once", self._picker(), parent=self),
                case="multi",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "A token field: Backspace walks the chips",
                field(
                    "Three people already chosen",
                    self._picker(summary="chips", value=TOKENS),
                    parent=self,
                ),
                case="tokens",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "People only, inactive included",
                field(
                    "No script users, and people whose status is dis",
                    self._picker(include_api_users=False, include_inactive=True),
                    parent=self,
                ),
                case="people-only",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Bare references, resolved on the way in",
                field(
                    "Types and ids in, names resolved on the way in",
                    self._picker(value=BARE),
                    parent=self,
                ),
                case="hydrate",
                parent=self,
            )
        )

        summaries: list = []
        for summary in SUMMARIES:
            summaries.append(
                field(
                    f"{summary}, full width",
                    self._picker(value=FIVE, summary=summary, clearable=False),
                    name=summary,
                    parent=self,
                )
            )
            summaries.append(
                field(
                    f"{summary}, at most 20rem",
                    narrow(self._picker(value=FIVE, summary=summary, clearable=False)),
                    name=f"{summary}-narrow",
                    parent=self,
                )
            )
        summaries.append(
            field(
                "chips, two at most",
                self._picker(value=FIVE, summary="chips", max=2, clearable=False),
                name="max",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "What the control shows for five selected, wide and narrow",
                *summaries,
                case="summary",
                parent=self,
            )
        )

        states = [
            field(size, self._picker(value=PRESET, size=size, follow=False), parent=self)
            for size in SIZES
        ]
        states.extend(
            field(caption, self._picker(value=PRESET, **{flag: True}), parent=self)
            for flag, caption in STATES
        )
        body.addWidget(
            section(
                "Sizes, then disabled, read-only, invalid", *states, case="states", parent=self
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _picker(self, follow: bool = True, **props: Any) -> UserMultiPicker:
        picker = UserMultiPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def _pending(self) -> bool:
        for picker in self.findChildren(UserMultiPicker):
            labels = picker.control.labels
            for ref, label in zip(picker.value, labels):
                if not label or label == placeholder_name(ref):
                    return True
        return False

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return UserMultiPickerDemo(context, parent)
