"""Tokens, palettes, radius and the stylesheet the plain Qt widgets under ours wear.

A theme is the shadcn token set as `QColor`-convertible hex strings, plus a radius in pixels, the
two font families and the two flags a widget reads. `theme_for` builds one from the palettes
`tools/export_palettes.py` exports from upstream; `host_theme` builds one from a `QPalette`, so a
widget dropped into Maya, Houdini or Nuke wears the host's greys and its accent.

    theme = theme_for("nova", dark=True)
    apply_theme(root, theme)
    theme_of(child).color("ring")

`apply_theme` sets the generated stylesheet on one root widget and never on the application, so a
host's own stylesheet survives.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

__all__ = [
    "BUNDLED_FONTS",
    "MONO_FAMILY",
    "ensure_fonts",
    "PALETTES",
    "RADII",
    "TOKENS",
    "Theme",
    "ThemeBus",
    "apply_theme",
    "contrast_ratio",
    "generate_qss",
    "host_theme",
    "mix",
    "theme_bus",
    "theme_for",
    "theme_of",
    "to_color",
    "watch_theme",
    "with_alpha",
]

PALETTES_PATH = Path(__file__).with_name("palettes.json")

#: Every token themes.css names, in the order it writes them.
TOKENS: tuple[str, ...] = (
    "background",
    "foreground",
    "card",
    "card_foreground",
    "popover",
    "popover_foreground",
    "primary",
    "primary_foreground",
    "secondary",
    "secondary_foreground",
    "muted",
    "muted_foreground",
    "accent",
    "accent_foreground",
    "destructive",
    "destructive_foreground",
    "success",
    "success_foreground",
    "warning",
    "warning_foreground",
    "info",
    "info_foreground",
    "border",
    "input",
    "ring",
    "chart_1",
    "chart_2",
    "chart_3",
    "chart_4",
    "chart_5",
    "sidebar",
    "sidebar_foreground",
    "sidebar_primary",
    "sidebar_primary_foreground",
    "sidebar_accent",
    "sidebar_accent_foreground",
    "sidebar_border",
    "sidebar_ring",
)

#: The radius override the toolbar offers, in pixels, from the block at the foot of themes.css.
#: `default` keeps the radius the palette itself carries.
RADII: dict[str, int | None] = {
    "default": None,
    "none": 0,
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
}

#: The ladder a widget rounds on, as an offset from the theme's radius. `full` is a pill.
# Upstream `global.css`: sm 0.6, md 0.8, lg 1, xl 1.4, 2xl 1.8 of `--radius`.
RADIUS_LADDER: dict[str, float] = {"sm": 0.6, "md": 0.8, "lg": 1.0, "xl": 1.4, "2xl": 1.8, "3xl": 2.2, "4xl": 2.6}
RADIUS_FULL = 9999

_PROPERTY = "_sg_theme"
_DEFAULT_PALETTE = "default"
_HOST_NAME = "host"

# A host's `QPalette` has no role for a status colour or a chart series, and no radius, so those
# come from the default palette in the matching mode rather than from a colour written here.
_HOST_FROM_DEFAULT = (
    "destructive",
    "destructive_foreground",
    "success",
    "success_foreground",
    "warning",
    "warning_foreground",
    "info",
    "info_foreground",
)


@lru_cache(maxsize=256)
def _palettes() -> dict:
    return json.loads(PALETTES_PATH.read_text(encoding="utf-8"))


#: The palettes the showcase offers, in the order demo-prefs.ts lists them.
PALETTES: list[str] = list(_palettes())


# --- colour helpers --------------------------------------------------------------------------


@lru_cache(maxsize=256)
def _rgba(value: str) -> tuple[int, int, int, int]:
    """`#rrggbb` or `#rrggbbaa` as bytes. Qt's own 8 digit form is `#aarrggbb`, so parse it here."""
    text = value.strip().lstrip("#")
    if len(text) in (3, 4):
        text = "".join(c * 2 for c in text)
    if len(text) not in (6, 8):
        raise ValueError("unreadable colour: " + value)
    channels = [int(text[i : i + 2], 16) for i in range(0, len(text), 2)]
    if len(channels) == 3:
        channels.append(255)
    return channels[0], channels[1], channels[2], channels[3]


def to_color(value: QtGui.QColor | str) -> QtGui.QColor:
    """A token value as a `QColor`."""
    if isinstance(value, QtGui.QColor):
        return QtGui.QColor(value)
    return QtGui.QColor(*_rgba(value))


def with_alpha(color: QtGui.QColor | str, fraction: float) -> QtGui.QColor:
    """The colour at `fraction` of full opacity, its own alpha kept."""
    out = to_color(color)
    out.setAlpha(max(0, min(255, round(out.alpha() * fraction))))
    return out


def mix(a: QtGui.QColor | str, b: QtGui.QColor | str, t: float) -> QtGui.QColor:
    """`a` moved `t` of the way to `b`, alpha included."""
    first, second = to_color(a), to_color(b)
    t = max(0.0, min(1.0, t))
    return QtGui.QColor(
        *(
            round(x + (y - x) * t)
            for x, y in (
                (first.red(), second.red()),
                (first.green(), second.green()),
                (first.blue(), second.blue()),
                (first.alpha(), second.alpha()),
            )
        )
    )


def _luminance(color: QtGui.QColor) -> float:
    out = 0.0
    for channel, weight in ((color.red(), 0.2126), (color.green(), 0.7152), (color.blue(), 0.0722)):
        value = channel / 255.0
        out += weight * (value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return out


def contrast_ratio(a: QtGui.QColor | str, b: QtGui.QColor | str) -> float:
    """The WCAG contrast ratio between two colours, from 1 to 21."""
    first, second = _luminance(to_color(a)), _luminance(to_color(b))
    if first < second:
        first, second = second, first
    return (first + 0.05) / (second + 0.05)


def _qss_color(value: QtGui.QColor | str) -> str:
    color = to_color(value)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def _set_tabular(font: QtGui.QFont) -> None:
    """Tabular figures, where the binding is Qt 6.7 or newer. Older Qt leaves the font alone."""
    setter = getattr(font, "setFeature", None)
    if setter is None:
        return
    tag = getattr(QtGui.QFont, "Tag", None)
    try:
        setter(tag("tnum") if tag is not None else "tnum", 1)
    except (TypeError, ValueError):
        pass


# --- the theme -------------------------------------------------------------------------------


@dataclass
class Theme:
    """One palette in one mode: every token as a hex string, with the radius, fonts and flags."""

    background: str
    foreground: str
    card: str
    card_foreground: str
    popover: str
    popover_foreground: str
    primary: str
    primary_foreground: str
    secondary: str
    secondary_foreground: str
    muted: str
    muted_foreground: str
    accent: str
    accent_foreground: str
    destructive: str
    destructive_foreground: str
    success: str
    success_foreground: str
    warning: str
    warning_foreground: str
    info: str
    info_foreground: str
    border: str
    input: str
    ring: str
    chart_1: str
    chart_2: str
    chart_3: str
    chart_4: str
    chart_5: str
    sidebar: str
    sidebar_foreground: str
    sidebar_primary: str
    sidebar_primary_foreground: str
    sidebar_accent: str
    sidebar_accent_foreground: str
    sidebar_border: str
    sidebar_ring: str
    radius: int = 8
    font_sans: str = ""
    font_mono: str = ""
    dark: bool = False
    reduced_motion: bool = False
    name: str = _DEFAULT_PALETTE

    def color(self, token: str) -> QtGui.QColor:
        """The token as a `QColor`."""
        if token not in TOKENS:
            raise KeyError(token)
        return to_color(getattr(self, token))

    def radius_px(self, step: str = "lg") -> int:
        """A step of the radius ladder in pixels: `sm`, `md`, `lg`, `xl` or `full`."""
        if step == "full":
            return RADIUS_FULL
        if step not in RADIUS_LADDER:
            raise KeyError(step)
        return max(0, int(round(self.radius * RADIUS_LADDER[step])))

    def font(
        self,
        size: int = 14,
        weight: QtGui.QFont.Weight = QtGui.QFont.Weight.Normal,
        mono: bool = False,
        tabular: bool = False,
    ) -> QtGui.QFont:
        """The theme's family at `size` pixels. `tabular` asks for tabular figures."""
        font = QtGui.QFont()
        family = self.font_mono if mono else self.font_sans
        if family:
            font.setFamily(family)
        if mono:
            font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
            font.setFixedPitch(True)
        font.setPixelSize(int(size))
        font.setWeight(weight)
        if tabular:
            _set_tabular(font)
        return font

    def with_(self, **changes: object) -> Theme:
        """A copy with those fields changed."""
        return replace(self, **changes)  # type: ignore[arg-type]


_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONTS_LOADED = False
#: The families the palettes name, shipped as variable TrueType files under the OFL beside this
#: module, so a palette wears its own face on a host that has none of them installed.
BUNDLED_FONTS = ("Geist", "Geist Mono", "Montserrat", "Open Sans", "Outfit")
MONO_FAMILY = "Geist Mono"


def ensure_fonts() -> None:
    """Register the bundled families with the font database, once, when an application exists."""
    global _FONTS_LOADED
    if _FONTS_LOADED or QtGui.QGuiApplication.instance() is None:
        return
    _FONTS_LOADED = True
    for path in sorted(_FONTS_DIR.glob("*.ttf")):
        QtGui.QFontDatabase.addApplicationFont(str(path))


def theme_for(
    palette: str = _DEFAULT_PALETTE,
    dark: bool = False,
    radius: str = "default",
    reduced_motion: bool = False,
) -> Theme:
    """The theme for a palette in one mode, with an optional radius override."""
    data = _palettes()
    if palette not in data:
        palette = _DEFAULT_PALETTE
    values = dict(data[palette]["dark" if dark else "light"])
    override = RADII.get(radius)
    if override is not None:
        values["radius"] = override
    if not values.get("font_mono"):
        values["font_mono"] = MONO_FAMILY
    ensure_fonts()
    return Theme(name=palette, dark=dark, reduced_motion=reduced_motion, **values)


def host_theme(palette: QtGui.QPalette | None = None) -> Theme:
    """A theme derived from a host's `QPalette`, so a widget wears the host's greys and accent."""
    if palette is None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return theme_for(_DEFAULT_PALETTE).with_(name=_HOST_NAME)
        palette = app.palette()

    role = QtGui.QPalette.ColorRole
    window = palette.color(role.Window)
    window_text = palette.color(role.WindowText)
    base = palette.color(role.Base)
    text = palette.color(role.Text)
    button = palette.color(role.Button)
    button_text = palette.color(role.ButtonText)
    highlight = palette.color(role.Highlight)
    highlight_text = palette.color(role.HighlightedText)
    mid = palette.color(role.Mid)
    alternate = palette.color(role.AlternateBase)

    dark = window.lightnessF() < 0.5
    ground = theme_for(_DEFAULT_PALETTE, dark=dark)
    values = {token: getattr(ground, token) for token in _HOST_FROM_DEFAULT}
    values.update(
        background=window.name(),
        foreground=window_text.name(),
        card=base.name(),
        card_foreground=text.name(),
        popover=base.name(),
        popover_foreground=text.name(),
        primary=highlight.name(),
        primary_foreground=highlight_text.name(),
        secondary=button.name(),
        secondary_foreground=button_text.name(),
        muted=alternate.name(),
        muted_foreground=mix(window_text, window, 0.35).name(),
        accent=highlight.name(),
        accent_foreground=highlight_text.name(),
        border=mid.name(),
        input=mid.name(),
        ring=highlight.name(),
        chart_1=highlight.name(),
        chart_2=ground.success,
        chart_3=ground.warning,
        chart_4=ground.destructive,
        chart_5=mid.name(),
        sidebar=mix(window, window_text, 0.04).name(),
        sidebar_foreground=window_text.name(),
        sidebar_primary=highlight.name(),
        sidebar_primary_foreground=highlight_text.name(),
        sidebar_accent=mix(window, highlight, 0.18).name(),
        sidebar_accent_foreground=window_text.name(),
        sidebar_border=mid.name(),
        sidebar_ring=highlight.name(),
        radius=ground.radius,
        font_sans=_application_family(),
        font_mono=MONO_FAMILY,
        dark=dark,
        name=_HOST_NAME,
    )
    return Theme(**values)  # type: ignore[arg-type]


def _application_family() -> str:
    app = QtWidgets.QApplication.instance()
    return app.font().family() if app is not None else ""


# --- the stylesheet --------------------------------------------------------------------------


def generate_qss(theme: Theme) -> str:
    """The base stylesheet for the plain Qt widgets that appear inside ours.

    Our own widgets paint themselves from the tokens; this covers what Qt still draws: labels and
    frames, the viewports of the views we keep for their models, tooltips, menus, the line edit
    inside a picker, and the thin overlay scrollbars.
    """
    return _QSS.format(
        background=_qss_color(theme.background),
        foreground=_qss_color(theme.foreground),
        popover=_qss_color(theme.popover),
        popover_foreground=_qss_color(theme.popover_foreground),
        accent=_qss_color(theme.accent),
        accent_foreground=_qss_color(theme.accent_foreground),
        border=_qss_color(theme.border),
        handle=_qss_color(with_alpha(theme.muted_foreground, 0.4)),
        handle_hover=_qss_color(with_alpha(theme.muted_foreground, 0.6)),
        radius=theme.radius_px("md"),
        radius_sm=theme.radius_px("sm"),
    )


_QSS = """\
QLabel, .QFrame {{
    background: transparent;
    color: {foreground};
}}
QScrollArea, QAbstractScrollArea {{
    background: {background};
    border: none;
}}
QAbstractItemView {{
    background: {background};
    color: {foreground};
    border: none;
    outline: none;
    selection-background-color: {accent};
    selection-color: {accent_foreground};
}}
QLineEdit {{
    background: transparent;
    border: none;
    selection-background-color: {accent};
    selection-color: {accent_foreground};
}}
QToolTip {{
    background: {popover};
    color: {popover_foreground};
    border: 1px solid {border};
    border-radius: {radius}px;
    padding: 4px 8px;
}}
QMenu {{
    background: {popover};
    color: {popover_foreground};
    border: 1px solid {border};
    border-radius: {radius}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 8px;
    border-radius: {radius_sm}px;
}}
QMenu::item:selected {{
    background: {accent};
    color: {accent_foreground};
}}
QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 4px 0;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {handle};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:horizontal {{
    background: {handle};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: {handle_hover};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
    background: none;
    border: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
"""


# --- applying it -----------------------------------------------------------------------------


class ThemeBus(QtCore.QObject):
    """Carries the root a theme landed on, so live widgets under it repaint."""

    changed = QtCore.Signal(QtWidgets.QWidget)


theme_bus = ThemeBus()


def apply_theme(root: QtWidgets.QWidget, theme: Theme) -> None:
    """Put a theme on one root widget: the widgets under it read it, and it wears the stylesheet."""
    ensure_fonts()
    root.setProperty(_PROPERTY, theme)
    root.setStyleSheet(generate_qss(theme))
    theme_bus.changed.emit(root)


def theme_of(widget: QtWidgets.QWidget) -> Theme:
    """The nearest theme at or above a widget, or one derived from the host's palette."""
    node: QtWidgets.QWidget | None = widget
    while node is not None:
        found = node.property(_PROPERTY)
        if isinstance(found, Theme):
            return found
        node = node.parentWidget()
    return host_theme()


def watch_theme(widget: QtWidgets.QWidget, callback) -> None:
    """Call `callback(theme)` whenever a theme lands on this widget or an ancestor of it."""

    def on_changed(root: QtWidgets.QWidget) -> None:
        try:
            near = root is widget or root.isAncestorOf(widget)
        except RuntimeError:  # The widget went while the signal was in flight.
            return
        if near:
            callback(theme_of(widget))

    def on_destroyed(*_: object) -> None:
        try:
            theme_bus.changed.disconnect(on_changed)
        except (RuntimeError, TypeError):
            pass

    theme_bus.changed.connect(on_changed)
    widget.destroyed.connect(on_destroyed)
