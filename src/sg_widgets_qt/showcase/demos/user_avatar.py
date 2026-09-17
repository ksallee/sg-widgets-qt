"""The avatar at every step, over the site's people and over invented names.

The port of `apps/site/src/demos/user-avatar/Demo.tsx`. People with a picture are read first, so a
site shows real avatars; the sections under them are names alone, which is what the initials and
the hue behind them fall out of.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.client import SearchOptions

from ...images import image_loader
from ...widgets.state_line import StateLine
from ...widgets.user_avatar import UserAvatar
from ...workers import default_pool
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: How many of the site's people the demo shows.
PEOPLE = 6

#: The code a disabled person's status field holds (entity_types/HumanUser).
DISABLED_CODE = "dis"

#: Names with one word, two, a particle and a login, so every shape of initials is on show.
NAMES = ("Ada Lovelace", "Anna van der Meer", "Madonna", "j.doe", "")

#: The names the tinted row uses.
TINTED = ("Ada Lovelace", "Anna van der Meer", "Madonna", "j.doe", "Grace Hopper", "Alan Turing")

#: A script account rather than a person.
API_NAME = "sg_widgets_demo"

#: A picture that fails to decode, which falls back to the initials.
BROKEN = "data:image/png;base64,iVBORw0KGgo="


class UserAvatarDemo(QtWidgets.QWidget):
    """The site's people, the initials fallback, the tint, and a script account."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("user-avatar-demo")
        self._context = context
        self._avatars: list[UserAvatar] = []
        self._read_done = False

        self._body = lay.column(self)
        self._state = StateLine(state="empty", label="Loading people…", pad="none", parent=self)
        self._state.setObjectName("demo-state")
        self._body.addWidget(self._state)
        self._body.addWidget(self._invented())

        default_pool().submit(self._read, on_result=self._answered, on_error=self._failed)

    def demo_ready(self) -> bool:
        """True once the people have answered and every picture they named has landed."""
        return self._read_done and image_loader().pending == 0

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds, where the example does not name its own."""
        for avatar in self._avatars:
            avatar.set_size(size)

    # --- the read ---

    def _read(self) -> list[tuple[str, str | None, bool]]:
        client = self._context.client
        fields = ["name", "image", "sg_status_list"]
        with_image = client.search(
            "HumanUser",
            SearchOptions(
                filters={"logical_operator": "and", "conditions": [["image", "is_not", None]]},
                fields=fields,
                page={"size": PEOPLE},
            ),
        )
        rows = list(with_image.data)
        if len(rows) < PEOPLE:
            rest = client.search(
                "HumanUser",
                SearchOptions(
                    filters={"logical_operator": "and", "conditions": [["image", "is", None]]},
                    fields=fields,
                    page={"size": PEOPLE - len(rows)},
                ),
            )
            rows.extend(rest.data)
        return [
            (
                str(row.values.get("name") or ""),
                row.values.get("image"),
                row.values.get("sg_status_list") == DISABLED_CODE,
            )
            for row in rows
        ]

    def _answered(self, rows: Any) -> None:
        if not lay.alive(self):
            return
        people: list[tuple[str, str | None, bool]] = list(rows or [])
        if not people:
            self._state.apply_state("empty")
            self._read_done = True
            return
        self._state.setParent(None)
        self._body.insertWidget(0, self._from_the_site(people))
        self._read_done = True

    def _failed(self, error: BaseException) -> None:
        if not lay.alive(self):
            return
        self._state.apply_state("error", message=str(error))
        self._read_done = True

    # --- the sections ---

    def _from_the_site(self, people: list[tuple[str, str | None, bool]]) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)
        first = people[0]
        column.addWidget(
            lay.section(
                "Sizes",
                lay.row(
                    *(
                        UserAvatar(name=first[0], image=first[1], size=step, parent=self)
                        for step in ("sm", "md", "lg")
                    )
                ),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "The site's people",
                lay.flow(
                    *(
                        self._avatar(name=name, image=image, inactive=inactive)
                        for name, image, inactive in people
                    )
                ),
                parent=self,
            )
        )
        return holder

    def _avatar(self, **kwargs: Any) -> UserAvatar:
        avatar = UserAvatar(parent=self, **kwargs)
        self._avatars.append(avatar)
        return avatar

    def _invented(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)

        column.addWidget(
            lay.section(
                "Initials fallback",
                lay.flow(*(self._avatar(name=name) for name in NAMES)),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "Initials, tinted from the name",
                lay.flow(
                    *(self._avatar(name=name, color="auto") for name in TINTED),
                    self._avatar(name="Bo Chen", color="auto", inactive=True),
                ),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "Inactive, and an image that fails to load",
                lay.row(
                    self._avatar(name="Grace Hopper", inactive=True),
                    self._avatar(name="Alan Turing", image=BROKEN),
                ),
                parent=self,
            )
        )
        api = lay.section(
            "API users",
            lay.row(
                UserAvatar(name=API_NAME, api_user=True, size="sm", parent=self),
                UserAvatar(name=API_NAME, api_user=True, size="md", parent=self),
                UserAvatar(name=API_NAME, api_user=True, size="lg", parent=self),
                self._avatar(name=API_NAME, api_user=True, inactive=True),
            ),
            parent=self,
        )
        api.setObjectName("case-api")
        column.addWidget(api)
        return holder


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return UserAvatarDemo(context, parent)
