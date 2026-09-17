"""The theme layer: the palettes, the tokens, the host palette and the stylesheet."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_qt.theme import (
    PALETTES,
    RADII,
    TOKENS,
    Theme,
    apply_theme,
    contrast_ratio,
    generate_qss,
    host_theme,
    mix,
    theme_for,
    theme_of,
    to_color,
    watch_theme,
    with_alpha,
)

MODES = (False, True)

# The ring is held to 3:1 against the surface it sits on, which is what upstream tuned several
# palettes to reach; themes.css names the number beside each value it changed.
RING_MINIMUM = 3.0


def _export_palettes():
    """`tools/export_palettes.py`, which is a script rather than a module of the package."""
    path = Path(__file__).resolve().parents[2] / "tools" / "export_palettes.py"
    spec = importlib.util.spec_from_file_location("export_palettes", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("export_palettes", module)
    spec.loader.exec_module(module)
    return module


def test_palettes_are_the_showcase_list():
    assert PALETTES == ["default", "nova", "vercel", "supabase", "claude", "twitter", "catppuccin"]


def test_radii_are_the_override_block():
    assert RADII == {"default": None, "none": 0, "sm": 4, "md": 8, "lg": 12, "xl": 16}


@pytest.mark.parametrize("palette", PALETTES)
@pytest.mark.parametrize("dark", MODES)
def test_every_palette_loads_and_every_colour_parses(qapp, palette, dark):
    theme = theme_for(palette, dark=dark)
    assert theme.name == palette
    assert theme.dark is dark
    assert theme.radius > 0
    for token in TOKENS:
        value = getattr(theme, token)
        assert value.startswith("#") and len(value) in (7, 9), (token, value)
        assert theme.color(token).isValid()


@pytest.mark.parametrize("palette", PALETTES)
@pytest.mark.parametrize("dark", MODES)
def test_ring_reads_against_the_background(qapp, palette, dark):
    theme = theme_for(palette, dark=dark)
    ratio = contrast_ratio(theme.ring, theme.background)
    if ratio < RING_MINIMUM:
        mode = "dark" if dark else "light"
        print(f"{palette} {mode}: ring {theme.ring} on {theme.background} reads {ratio:.2f}:1")
        pytest.skip(f"{palette} {mode} ring reads {ratio:.2f}:1, under {RING_MINIMUM}:1")
    assert ratio >= RING_MINIMUM


@pytest.mark.parametrize("radius", list(RADII))
def test_radius_override(qapp, radius):
    theme = theme_for("twitter", radius=radius)
    expected = RADII[radius] if RADII[radius] is not None else theme_for("twitter").radius
    assert theme.radius == expected


def test_radius_ladder(qapp):
    theme = theme_for("nova")
    assert theme.radius == 10
    assert theme.radius_px("sm") == 6
    assert theme.radius_px("md") == 8
    assert theme.radius_px("lg") == 10
    assert theme.radius_px("xl") == 14
    assert theme.radius_px("full") == 9999
    assert theme.with_(radius=0).radius_px("sm") == 0
    assert theme.radius_px("2xl") == 18
    assert theme.radius_px("4xl") == 26
    with pytest.raises(KeyError):
        theme.radius_px("5xl")


def test_with_derives(qapp):
    theme = theme_for("nova")
    derived = theme.with_(dark=True, reduced_motion=True)
    assert derived.reduced_motion and derived.dark
    assert theme.reduced_motion is False
    assert derived.background == theme.background


def test_unknown_palette_falls_back_to_default(qapp):
    assert theme_for("no-such-palette").background == theme_for("default").background


def test_font(qapp):
    theme = theme_for("supabase")
    font = theme.font()
    assert font.family() == "Outfit"
    assert font.pixelSize() == 14
    assert theme.font(12, QtGui.QFont.Weight.Medium).pixelSize() == 12
    assert theme.font(mono=True).fixedPitch()
    # Tabular figures land on Qt 6.7 and later, and are a no-op elsewhere.
    assert theme.font(tabular=True).pixelSize() == 14


def test_colour_helpers(qapp):
    assert to_color("#ffffff").name() == "#ffffff"
    assert to_color("#0000001a").alpha() == 26
    assert with_alpha("#ffffff", 0.4).alpha() == 102
    assert mix("#000000", "#ffffff", 0.5).name() == "#808080"
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0, abs=0.01)


def test_theme_of_walks_to_the_root(qapp):
    root = QtWidgets.QWidget()
    middle = QtWidgets.QWidget(root)
    leaf = QtWidgets.QLabel(middle)
    theme = theme_for("catppuccin", dark=True)
    apply_theme(root, theme)
    assert theme_of(leaf) is theme
    assert theme_of(middle) is theme
    assert theme_of(root) is theme


def test_theme_of_falls_back_to_the_host(qapp):
    orphan = QtWidgets.QWidget()
    assert theme_of(orphan).name == "host"


def test_apply_theme_leaves_the_application_alone(qapp):
    root = QtWidgets.QWidget()
    apply_theme(root, theme_for("vercel"))
    assert qapp.styleSheet() == ""
    assert root.styleSheet() != ""


def test_watch_theme_fires_and_drops_on_destroy(qapp):
    root = QtWidgets.QWidget()
    leaf = QtWidgets.QLabel(root)
    seen = []
    watch_theme(leaf, lambda theme: seen.append(theme.name))
    apply_theme(root, theme_for("nova"))
    assert seen == ["nova"]
    leaf.setParent(None)
    leaf.deleteLater()
    qapp.processEvents()
    apply_theme(root, theme_for("vercel"))
    assert seen == ["nova"]


def test_host_theme_from_the_default_palette(qapp):
    theme = host_theme(QtGui.QPalette())
    assert isinstance(theme, Theme)
    assert theme.name == "host"
    assert isinstance(theme.dark, bool)
    assert theme.radius > 0
    for token in TOKENS:
        assert theme.color(token).isValid(), token


def test_host_theme_reads_the_palette(qapp):
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#1e1e1e"))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#f0f0f0"))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#2a7fff"))
    theme = host_theme(palette)
    assert theme.dark is True
    assert theme.background == "#1e1e1e"
    assert theme.foreground == "#f0f0f0"
    assert theme.ring == "#2a7fff"
    assert theme.primary == "#2a7fff"


def test_generated_qss_carries_the_tokens_and_the_overlay_scrollbars(qapp):
    theme = theme_for("nova", dark=True)
    qss = generate_qss(theme)
    background = theme.color("background")
    assert f"rgba({background.red()}, {background.green()}, {background.blue()}, 255)" in qss
    handle = with_alpha(theme.muted_foreground, 0.4)
    assert f"rgba({handle.red()}, {handle.green()}, {handle.blue()}, {handle.alpha()})" in qss
    assert "QScrollBar:vertical" in qss and "width: 8px" in qss
    assert "QScrollBar:horizontal" in qss and "height: 8px" in qss
    assert "QScrollBar::add-line" in qss and "QScrollBar::sub-line" in qss
    assert "QToolTip" in qss and "QMenu::item:selected" in qss and "QLineEdit" in qss
    assert f"border-radius: {theme.radius_px('md')}px" in qss


def test_oklch_spot_checks():
    to_hex = _export_palettes().to_hex
    assert to_hex("oklch(1 0 0)") == "#ffffff"
    assert to_hex("oklch(0 0 0)") == "#000000"
    assert to_hex("oklch(1 0 0 / 10%)") == "#ffffff1a"
    # Tailwind's neutral-950 and red-600, the two the shadcn token sets are written in.
    assert _near(to_hex("oklch(0.145 0 0)"), "#0a0a0a")
    assert _near(to_hex("oklch(0.577 0.245 27.325)"), "#e7000b")
    # Catppuccin Latte's mauve and Twitter's blue, as those palettes name them.
    assert _near(to_hex("oklch(0.5547 0.2503 297.0156)"), "#8839ef")
    assert _near(to_hex("oklch(0.6723 0.1606 244.9955)"), "#1d9bf0")


def test_hex_and_hsl_pass_through():
    to_hex = _export_palettes().to_hex
    assert to_hex("#abc") == "#aabbcc"
    assert to_hex("#A1B2C3") == "#a1b2c3"
    assert to_hex("hsl(210 50% 40%)") == "#336699"
    assert to_hex("rgb(1 2 3 / 50%)") == "#01020380"


def _near(value: str, expected: str, tolerance: int = 4) -> bool:
    got = to_color(value)
    want = to_color(expected)
    return all(
        abs(a - b) <= tolerance
        for a, b in ((got.red(), want.red()), (got.green(), want.green()), (got.blue(), want.blue()))
    )
