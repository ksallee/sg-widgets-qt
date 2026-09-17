"""The entity chip: its label, its variants, where it points, its glyph, its card and its cross.

Every test runs on both bindings, offscreen, and never reaches the network: the thumbnail here is
a `data:` url, which the loader decodes where it stands.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.filter import EntityRef
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.base import CHIP_HEIGHT
from sg_widgets_qt.primitives.hover_card import HoverCardContent
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_chip import ENTITY_CHIP_VARIANT_VALUES, EntityChip

#: An 8 by 8 block, as a self-contained data URI.
RED_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAACXBIWXMAAA7EAAAOxAGV"
    "Kw4bAAAAFklEQVQYlWM8oaHxnwEPYMInOXwUAAArkgInxYgTRAAAAABJRU5ErkJggg=="
)

SHOT = EntityRef(type="Shot", id=862, name="sh010_0010")
UNNAMED = EntityRef(type="Version", id=17055)
SITE = "https://site.example.com"


@pytest.fixture
def loader():
    return ImageLoader()


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 300)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget):
    widget.setParent(parent)
    widget.resize(max(1, widget.sizeHint().width()), max(1, widget.sizeHint().height()))
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def image(widget: QtWidgets.QWidget) -> QtGui.QImage:
    pixmap = widget.grab()
    assert not pixmap.isNull()
    return pixmap.toImage()


def counts(shot: QtGui.QImage) -> dict:
    tally: dict = {}
    for y in range(shot.height()):
        for x in range(shot.width()):
            name = shot.pixelColor(x, y).name()
            tally[name] = tally.get(name, 0) + 1
    return tally


def test_constructs_and_paints(root, loader):
    chip = place(root, EntityChip(entity=SHOT, loader=loader))
    assert chip.objectName() == "entity-chip"
    assert chip.label == "sh010_0010"
    assert chip.named is True
    assert chip.toolTip() == "sh010_0010"
    assert counts(image(chip))


def test_a_row_with_no_name_shows_its_type_and_id(root, loader):
    chip = place(root, EntityChip(entity=UNNAMED, loader=loader))
    assert chip.named is False
    assert chip.label == "Version #17055"
    assert counts(image(chip))


@pytest.mark.parametrize("variant", ENTITY_CHIP_VARIANT_VALUES)
def test_every_variant_constructs_and_paints(root, loader, variant):
    chip = place(root, EntityChip(entity=SHOT, variant=variant, site_url=SITE, loader=loader))
    assert chip.variant == variant
    assert counts(image(chip))


def test_only_the_chip_variant_has_a_surface(root, loader):
    boxed = EntityChip(entity=SHOT, variant="chip", loader=loader)
    bare = EntityChip(entity=SHOT, variant="text", loader=loader)
    assert boxed.boxed is True
    assert bare.boxed is False
    assert boxed.sizeHint().height() == CHIP_HEIGHT["md"]
    assert bare.sizeHint().height() < boxed.sizeHint().height()


@pytest.mark.parametrize("step", sorted(CHIP_HEIGHT))
def test_every_step_of_the_chip_ladder(root, loader, step):
    chip = EntityChip(entity=SHOT, size=step, loader=loader)
    assert chip.sizeHint().height() == CHIP_HEIGHT[step]


def test_with_no_href_it_addresses_the_row_s_own_page(root, loader):
    chip = EntityChip(entity=SHOT, site_url=SITE, loader=loader)
    assert chip.url == SITE + "/detail/Shot/862"
    assert chip.interactive is True


def test_an_href_of_its_own_wins_and_a_resolver_is_called(root, loader):
    fixed = EntityChip(entity=SHOT, site_url=SITE, href="#entity-chip", loader=loader)
    assert fixed.url == "#entity-chip"
    resolved = EntityChip(
        entity=SHOT, site_url=SITE, href=lambda ref: f"app://{ref.type}/{ref.id}", loader=loader
    )
    assert resolved.url == "app://Shot/862"


def test_the_text_variant_never_links(root, loader):
    chip = EntityChip(entity=SHOT, variant="text", site_url=SITE, loader=loader)
    assert chip.url == ""
    assert chip.interactive is False


def test_a_thumbnail_replaces_the_type_glyph(root, loader):
    glyphed = place(root, EntityChip(entity=SHOT, loader=loader))
    pictured = place(root, EntityChip(entity=SHOT, thumbnail=RED_PNG, loader=loader))
    assert pictured.pixmap is not None
    assert QtGui.QColor(200, 40, 40).name() in counts(image(pictured))
    assert image(pictured) != image(glyphed)


def test_an_unlisted_type_takes_the_tag(root, loader):
    listed = place(root, EntityChip(entity=EntityRef(type="Shot", id=1, name="x"), loader=loader))
    custom = place(
        root, EntityChip(entity=EntityRef(type="CustomEntity07", id=1, name="x"), loader=loader)
    )
    assert image(listed) != image(custom)


def test_the_cross_fires_the_removed_signal_with_the_row(root, qtbot, loader):
    chip = place(root, EntityChip(entity=SHOT, removable=True, loader=loader))
    with qtbot.waitSignal(chip.removed, timeout=1000) as caught:
        qtbot.keyClick(chip, QtCore.Qt.Key.Key_Delete)
    assert caught.args == [SHOT]


def test_a_press_activates_an_interactive_chip(root, qtbot, loader):
    seen: list[str] = []
    chip = place(root, EntityChip(entity=SHOT, on_click=lambda: seen.append("hit"), loader=loader))
    with qtbot.waitSignal(chip.clicked, timeout=1000):
        qtbot.keyClick(chip, QtCore.Qt.Key.Key_Return)
    assert seen == ["hit"]


def test_an_inert_chip_takes_no_focus(root, loader):
    inert = EntityChip(entity=SHOT, variant="text", loader=loader)
    live = EntityChip(entity=SHOT, variant="chip", site_url=SITE, loader=loader)
    assert inert.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
    assert live.focusPolicy() == QtCore.Qt.FocusPolicy.TabFocus


def test_a_preview_puts_a_hover_card_on_the_chip(root, loader):
    plain = EntityChip(entity=SHOT, loader=loader)
    assert plain.hover_card is None
    previewed = EntityChip(entity=SHOT, preview=["sg_status_list"], loader=loader)
    assert previewed.hover_card is not None
    assert previewed.hover_card.is_open is False


def test_the_preview_builder_is_what_the_card_holds(root, loader):
    seen: list[tuple] = []

    def builder(entity, fields, context):
        seen.append((entity, tuple(fields), context))
        return HoverCardContent("Ported later", "entity-card")

    chip = EntityChip(entity=SHOT, preview=["sg_status_list", "user"], loader=loader)
    chip.set_preview_builder(builder)
    assert seen and seen[-1][0] == SHOT
    assert seen[-1][1] == ("sg_status_list", "user")
    assert chip.hover_card is not None


def test_every_setter_repaints(root, loader):
    chip = place(root, EntityChip(entity=SHOT, loader=loader))
    chip.set_entity(UNNAMED)
    chip.set_variant("link")
    chip.set_site_url(SITE)
    chip.set_size("lg")
    chip.set_removable(True)
    chip.set_remove_label("Drop it")
    chip.set_thumbnail(RED_PNG)
    QtWidgets.QApplication.processEvents()
    place(root, chip)
    assert chip.label == "Version #17055"
    assert chip.variant == "link"
    assert chip.site_url == SITE
    assert chip.remove_label == "Drop it"
    assert counts(image(chip))


def test_disabled_is_inert(root, loader):
    chip = place(root, EntityChip(entity=SHOT, removable=True, site_url=SITE, loader=loader))
    chip.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    assert chip.disabled_opacity() == 0.5
    assert counts(image(chip))
