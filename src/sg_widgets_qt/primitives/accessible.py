"""The role, the name and the state a painted control hands a screen reader.

A leaf here is a bare `QWidget` that draws itself, so Qt has nothing to report about it: the
default interface answers the `Client` role and no state at all. `AccessibleControl` gives a
leaf the three things a reader needs, in plain Python, and one factory turns them into the
`QAccessibleInterface` the platform asks for.

PyQt5 wraps none of the accessibility classes, so `QAccessible` is absent there and the factory
is never installed. The names stay: `accessibleName` is a `QWidget` property on every binding,
and a leaf's `text` flows into it.
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtGui, QtWidgets

__all__ = [
    "ACCESSIBLE_ROLES",
    "AccessibleControl",
    "accessibility_available",
    "install_accessibility",
]

QAccessible = getattr(QtGui, "QAccessible", None)
QAccessibleWidget = getattr(QtWidgets, "QAccessibleWidget", None)

#: The role name a leaf declares, and the `QAccessible.Role` it stands for. A switch has no role
#: of its own in Qt, so it reports the check box it behaves as; a toggle is the button that stays
#: down, which is a checkable button.
ACCESSIBLE_ROLES: tuple[str, ...] = ("button", "checkbox", "combobox", "grouping")


def accessibility_available() -> bool:
    """True where the binding wraps `QAccessible` and a role can be reported."""
    return QAccessible is not None and QAccessibleWidget is not None


class AccessibleControl:
    """A painted leaf that names itself and reports a role and a state.

    `accessible_role` is one of `ACCESSIBLE_ROLES`. `accessible_label` is what the control reads
    when the caller named nothing, and `accessible_states` the flags to raise on the reported
    state, keyed by the `QAccessible.State` field they set.
    """

    accessible_role = "button"

    def accessible_label(self) -> str:
        """What the control reads when the caller set no name of its own."""
        return str(getattr(self, "text", "") or "")

    def accessible_value(self) -> str:
        """What the control holds, for a role that carries a value apart from its name."""
        return ""

    def accessible_states(self) -> dict[str, bool]:
        """The `QAccessible.State` fields to raise, beyond the ones Qt reads off the widget."""
        return {"pressed": bool(getattr(self, "pressed", False))}

    def setAccessibleName(self, name: str) -> None:  # noqa: N802
        """Name the control, and keep that name through every later change of its text."""
        self._named_by_caller = bool(name)
        QtWidgets.QWidget.setAccessibleName(self, name)

    def name_after_label(self) -> None:
        """Put the label in `accessibleName`, unless the caller named the control itself."""
        if getattr(self, "_named_by_caller", False):
            return
        QtWidgets.QWidget.setAccessibleName(self, self.accessible_label())


if accessibility_available():

    _ROLE_OF = {
        "button": QAccessible.Role.Button,
        "checkbox": QAccessible.Role.CheckBox,
        "combobox": QAccessible.Role.ComboBox,
        "grouping": QAccessible.Role.Grouping,
    }

    class _ControlInterface(QAccessibleWidget):
        """One painted leaf, read through what `AccessibleControl` declares."""

        def __init__(self, widget: QtWidgets.QWidget) -> None:
            super().__init__(widget, _ROLE_OF.get(widget.accessible_role, QAccessible.Role.Button))

        def text(self, kind) -> str:  # noqa: A003
            control = self.widget()
            if kind == QAccessible.Text.Name:
                return control.accessibleName() or control.accessible_label()
            if kind == QAccessible.Text.Value:
                return control.accessible_value()
            return super().text(kind)

        def state(self):
            reported = super().state()
            for field, raised in self.widget().accessible_states().items():
                setattr(reported, field, bool(raised))
            return reported

    def _factory(_key: str, obj: QtWidgets.QWidget):
        if isinstance(obj, AccessibleControl):
            return _ControlInterface(obj)
        return None

else:  # The binding wraps no accessibility classes: nothing to install.
    _factory: Callable[[str, QtWidgets.QWidget], object] | None = None


_installed = False


def install_accessibility() -> bool:
    """Install the factory the platform asks a painted leaf's interface of. Idempotent."""
    global _installed
    if _installed or not accessibility_available():
        return _installed
    QAccessible.installFactory(_factory)
    _installed = True
    return True


install_accessibility()
