"""The controls that set the view, as one row.

The port of `DemoToolbar.astro` and the header half of `SiteControls.astro`. One row is built from
a list of pref keys, so the header and each stage's caption carry the same controls over the same
`Prefs`: a change on one example holds for every other example and for the next page.
"""
from __future__ import annotations

from collections.abc import Sequence

from qtpy import QtCore, QtWidgets

from ..theme import PALETTES
from . import chrome
from .prefs import ALLOWED, Prefs, label_for

__all__ = ["PrefsToolbar", "HEADER_KEYS", "STAGE_KEYS"]

#: What the header carries.
HEADER_KEYS: tuple[str, ...] = ("palette", "theme", "size", "radius", "motion", "source")

#: What a stage's caption carries.
STAGE_KEYS: tuple[str, ...] = ("size", "density", "radius", "motion")


def _options(key: str) -> list[tuple[str, str]]:
    values = PALETTES if key == "palette" else list(ALLOWED[key])
    return [(value, label_for(key, value)) for value in values]


class PrefsToolbar(QtWidgets.QWidget):
    """A row of controls over one `Prefs`."""

    def __init__(
        self,
        prefs: Prefs,
        keys: Sequence[str] = STAGE_KEYS,
        size: str = "sm",
        live_enabled: bool = True,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toolbar")
        self._prefs = prefs
        self._keys = list(keys)
        self._size = size
        self._live_enabled = live_enabled
        #: The control per key, so a caller reaches one by name.
        self.controls: dict[str, QtWidgets.QWidget] = {}

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for key in self._keys:
            control = self._build(key)
            if control is not None:
                self.controls[key] = control
                layout.addWidget(control)
        layout.addStretch(1)
        prefs.changed.connect(self._follow)

    def _build(self, key: str) -> QtWidgets.QWidget | None:
        if key == "theme":
            made = chrome.switch(
                label="Dark",
                checked=self._prefs.dark,
                size=self._size,
                parent=self,
                on_toggle=lambda on: self._prefs.set("theme", "dark" if on else "light"),
            )
            made.setObjectName("theme-switch")
            return made
        if key == "motion":
            made = chrome.toggle(
                text="Reduce motion",
                pressed=self._prefs.reduced_motion,
                size=self._size,
                parent=self,
                on_toggle=lambda on: self._prefs.set("motion", "reduced" if on else "normal"),
            )
            made.setObjectName("motion-toggle")
            return made
        if key not in ALLOWED:
            return None
        made = chrome.select(
            _options(key),
            value=self._prefs.get(key),
            size=self._size,
            parent=self,
            on_pick=lambda value, key=key: self._prefs.set(key, value),
        )
        made.setObjectName(key + "-select")
        if key == "source" and not self._live_enabled:
            made.setEnabled(False)
            made.setToolTip("Live needs the three keys in .env.local at the repo root.")
        return made

    def _follow(self) -> None:
        """Put the view back on the controls, so a change made elsewhere shows here."""
        for key, control in self.controls.items():
            if key == "theme":
                setter = getattr(control, "set_checked", None)
                if setter is not None:
                    setter(self._prefs.dark)
            elif key == "motion":
                setter = getattr(control, "set_checked", None)
                if setter is not None:
                    setter(self._prefs.reduced_motion)
            else:
                setter = getattr(control, "set_value", None)
                if setter is not None:
                    setter(self._prefs.get(key))
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        hint = super().sizeHint()
        return QtCore.QSize(hint.width(), chrome.HEIGHTS.get(self._size, 32))
