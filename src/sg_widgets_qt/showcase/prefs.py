"""The view every demo wears: theme, palette, radius, motion, source, size and density.

The port of `apps/site/src/components/demo-prefs.ts`. The header controls and each stage's
toolbar write these, the demos read them, and `QSettings('sg-widgets', 'showcase')` carries them
from one run to the next, as `localStorage` does upstream.

`size` and `density` have no upstream key: a web demo sets a widget's size step in its own markup,
and here the toolbar sets it for every demo at once.

    prefs = Prefs()
    prefs.set("palette", "nova")
    prefs.apply(stage)
"""
from __future__ import annotations

from collections.abc import Sequence

from qtpy import QtCore, QtWidgets

from ..theme import PALETTES, RADII, Theme, apply_theme, theme_for

__all__ = [
    "ALLOWED",
    "APPLICATION",
    "DENSITIES",
    "FALLBACK",
    "LABELS",
    "MOTIONS",
    "ORGANIZATION",
    "PREFS",
    "Prefs",
    "RADIUS_NAMES",
    "SIZES",
    "SOURCES",
    "THEMES",
]

#: The organisation and application `QSettings` stores the view under.
ORGANIZATION = "sg-widgets"
APPLICATION = "showcase"

THEMES: tuple[str, ...] = ("light", "dark")
MOTIONS: tuple[str, ...] = ("normal", "reduced")
SOURCES: tuple[str, ...] = ("mock", "live")
SIZES: tuple[str, ...] = ("sm", "md", "lg")
DENSITIES: tuple[str, ...] = ("default", "compact")
RADIUS_NAMES: tuple[str, ...] = tuple(RADII)

#: What each key may hold.
ALLOWED: dict[str, tuple[str, ...]] = {
    "theme": THEMES,
    "palette": tuple(PALETTES),
    "radius": RADIUS_NAMES,
    "motion": MOTIONS,
    "source": SOURCES,
    "size": SIZES,
    "density": DENSITIES,
}

#: What each key holds until something says otherwise.
FALLBACK: dict[str, str] = {
    "theme": "light",
    "palette": PALETTES[0] if PALETTES else "default",
    "radius": "default",
    "motion": "normal",
    "source": "mock",
    "size": "md",
    "density": "default",
}

#: The keys, in the order the toolbar draws them.
PREFS: tuple[str, ...] = ("palette", "theme", "size", "radius", "motion", "source", "density")

#: What a control calls a value. A name with no entry is title cased.
LABELS: dict[str, str] = {
    "default": "Default",
    "none": "None",
    "sm": "Small",
    "md": "Medium",
    "lg": "Large",
    "xl": "Extra large",
    "light": "Light",
    "dark": "Dark",
    "normal": "Normal motion",
    "reduced": "Reduced motion",
    "mock": "Mock",
    "live": "Live",
    "compact": "Compact",
}


def label_for(key: str, value: str) -> str:
    """What a control calls one value of one key."""
    if key == "radius":
        return "Radius: " + ("theme" if value == "default" else value)
    if key == "size":
        return "Size: " + value
    if key == "density":
        return "Density: " + value
    return LABELS.get(value, value.replace("-", " ").title())


class Prefs(QtCore.QObject):
    """The view, as it stands. Read it; change it through `set`, `toggle` or `update`."""

    #: One or more keys changed.
    changed = QtCore.Signal()

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        persist: bool = True,
        **overrides: str,
    ) -> None:
        super().__init__(parent)
        self._persist = persist
        self._settings = QtCore.QSettings(ORGANIZATION, APPLICATION) if persist else None
        self._values = dict(FALLBACK)
        if self._settings is not None:
            for key in FALLBACK:
                stored = self._settings.value(key)
                if isinstance(stored, str) and stored in ALLOWED[key]:
                    self._values[key] = stored
        for key, value in overrides.items():
            if value is not None and key in ALLOWED and value in ALLOWED[key]:
                self._values[key] = value

    # --- reading -----------------------------------------------------------------------------

    def get(self, key: str) -> str:
        """One key's value."""
        return self._values[key]

    def values(self) -> dict[str, str]:
        """Every key, as a plain dict."""
        return dict(self._values)

    @property
    def theme(self) -> str:
        return self._values["theme"]

    @property
    def palette(self) -> str:
        return self._values["palette"]

    @property
    def radius(self) -> str:
        return self._values["radius"]

    @property
    def motion(self) -> str:
        return self._values["motion"]

    @property
    def source(self) -> str:
        return self._values["source"]

    @property
    def size(self) -> str:
        return self._values["size"]

    @property
    def density(self) -> str:
        return self._values["density"]

    @property
    def dark(self) -> bool:
        return self._values["theme"] == "dark"

    @property
    def reduced_motion(self) -> bool:
        return self._values["motion"] == "reduced"

    @property
    def live(self) -> bool:
        return self._values["source"] == "live"

    # --- writing -----------------------------------------------------------------------------

    def set(self, key: str, value: str) -> None:
        """Change one key. A value the key does not allow is ignored, as upstream ignores it."""
        self.update(**{key: value})

    def toggle(self, key: str) -> None:
        """Move one key to the other of its two values."""
        allowed = ALLOWED[key]
        self.set(key, allowed[0] if self._values[key] == allowed[1] else allowed[1])

    def update(self, **changes: str) -> None:
        """Change several keys and emit `changed` once."""
        moved = False
        for key, value in changes.items():
            if key not in ALLOWED or value not in ALLOWED[key] or self._values[key] == value:
                continue
            self._values[key] = value
            moved = True
            if self._settings is not None:
                self._settings.setValue(key, value)
        if moved:
            if self._settings is not None:
                self._settings.sync()
            self.changed.emit()

    # --- the theme ---------------------------------------------------------------------------

    def theme_object(self) -> Theme:
        """The `Theme` this view builds."""
        return theme_for(
            self.palette,
            dark=self.dark,
            radius=self.radius,
            reduced_motion=self.reduced_motion,
        )

    def apply(
        self,
        root: QtWidgets.QWidget,
        on: Sequence[QtWidgets.QWidget] | None = None,
    ) -> None:
        """Put the theme this view builds on one root widget.

        `on` names the widgets the stylesheet lands on instead of the root, for a root holding
        more than the reader is looking at.
        """
        apply_theme(root, self.theme_object(), on=on)
