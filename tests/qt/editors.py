"""What the eight value editor test files share: a themed root, and the keys a session answers."""
from __future__ import annotations

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from sg_widgets_qt.theme import apply_theme, theme_for

__all__ = ["escape", "place", "press_enter", "themed_root", "type_into"]


def themed_root(qtbot) -> QtWidgets.QWidget:
    """A shown root wearing the default light theme, which every editor reads through."""
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(720, 560)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, editor: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """Put an editor on a root at its own size hint and show it."""
    editor.setParent(parent)
    editor.resize(max(360, editor.sizeHint().width()), editor.sizeHint().height())
    editor.show()
    QtWidgets.QApplication.processEvents()
    return editor


def type_into(field: QtWidgets.QWidget, text: str) -> None:
    """Clear a field and type into it, key by key. An empty text empties the field."""
    field.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    field.selectAll()
    if text:
        QTest.keyClicks(field, text)
    else:
        QTest.keyClick(field, QtCore.Qt.Key.Key_Delete)


def press_enter(field: QtWidgets.QWidget) -> None:
    QTest.keyClick(field, QtCore.Qt.Key.Key_Return)


def escape(field: QtWidgets.QWidget) -> None:
    QTest.keyClick(field, QtCore.Qt.Key.Key_Escape)
