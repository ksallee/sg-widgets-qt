"""The status badge: its label chain, its variants, its colour, its sizes and its cross.

Every test runs on both bindings, offscreen, and never reaches the network.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import HtmlIcon, ImageMapIcon, StatusRecord
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.base import CHIP_HEIGHT
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.status_badge import (
    STATUS_BADGE_VARIANT_VALUES,
    StatusBadge,
)

#: The colour `GET /entity/statuses` sends: comma-separated decimal RGB, never hex (probe 010).
IN_PROGRESS = StatusRecord(
    id=306,
    code="ip",
    name="In Progress",
    bg_color="43,139,214",
    icon=ImageMapIcon(image_map_key="icon_ip"),
)

ACTIVE = StatusRecord(id=1, code="act", name="Active", bg_color=None, icon=HtmlIcon(html="Active"))

PLAIN = StatusRecord(id=2, code="partial", name="Partial", bg_color=None, icon=None)


def field() -> FieldSchema:
    return FieldSchema(
        name="sg_status_list",
        display_name="Status",
        entity_type="Version",
        data_type="status_list",
        editable=True,
        mandatory=False,
        unique=False,
        valid_values=["ip", "fin"],
        display_values={"ip": "In Progress", "fin": "Final"},
    )


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
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, loader=loader))
    assert badge.objectName() == "status-badge"
    assert badge.status_name == "In Progress"
    assert badge.known is True
    assert counts(image(badge))


def test_an_empty_code_renders_nothing(root, loader):
    badge = place(root, StatusBadge(code="", loader=loader))
    assert badge.sizeHint().isEmpty()


def test_the_label_falls_back_through_the_schema_to_the_code(root, loader):
    from_row = StatusBadge(code="ip", status=IN_PROGRESS, field=field(), loader=loader)
    from_schema = StatusBadge(code="fin", field=field(), loader=loader)
    bare = StatusBadge(code="zz_retired", loader=loader)
    assert from_row.status_name == "In Progress"
    assert from_schema.status_name == "Final"
    assert from_schema.known is True
    assert bare.status_name == "zz_retired"
    assert bare.known is False


def test_the_other_name_is_the_tooltip(root, loader):
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, loader=loader))
    assert badge.toolTip() == "ip"
    badge.set_label("code")
    place(root, badge)
    assert badge.status_text == "ip"
    assert badge.toolTip() == "In Progress"


@pytest.mark.parametrize("variant", STATUS_BADGE_VARIANT_VALUES)
def test_every_variant_constructs_and_paints(root, loader, variant):
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, variant=variant, loader=loader))
    assert badge.variant == variant
    assert counts(image(badge))


def test_the_glyph_variant_has_no_pill(root, loader):
    bare = StatusBadge(code="ip", status=IN_PROGRESS, variant="glyph", loader=loader)
    boxed = StatusBadge(code="ip", status=IN_PROGRESS, variant="both", loader=loader)
    assert bare.bare is True
    assert bare.sizeHint().width() == bare.sizeHint().height()
    assert bare.sizeHint().width() < boxed.sizeHint().width()


@pytest.mark.parametrize("step", sorted(CHIP_HEIGHT))
def test_every_step_of_the_chip_ladder(root, loader, step):
    badge = StatusBadge(code="ip", status=IN_PROGRESS, size=step, loader=loader)
    assert badge.sizeHint().height() == CHIP_HEIGHT[step]


def test_color_paints_the_status_colour_and_a_readable_ink(root, loader):
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, color=True, loader=loader))
    rgb = badge.status_rgb()
    assert rgb is not None
    assert (rgb.r, rgb.g, rgb.b) == (43, 139, 214)
    assert QtGui.QColor(43, 139, 214).name() in counts(image(badge))


def test_a_status_with_no_colour_reads_as_muted_under_color(root, loader):
    badge = place(root, StatusBadge(code="partial", status=PLAIN, color=True, loader=loader))
    assert badge.status_rgb() is None
    assert counts(image(badge))


def test_an_html_icon_replaces_the_text(root, loader):
    badge = place(root, StatusBadge(code="act", status=ACTIVE, variant="icon", loader=loader))
    assert badge.glyph.kind == "html"
    assert badge.text == "Active"


def test_the_cross_fires_the_removed_signal_with_the_code(root, qtbot, loader):
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, removable=True, loader=loader))
    with qtbot.waitSignal(badge.removed, timeout=1000) as caught:
        qtbot.keyClick(badge, QtCore.Qt.Key.Key_Return)
    assert caught.args == ["ip"]


def test_on_remove_is_called_beside_the_signal(root, qtbot, loader):
    seen: list[str] = []
    badge = place(
        root,
        StatusBadge(
            code="ip", status=IN_PROGRESS, removable=True, on_remove=seen.append, loader=loader
        ),
    )
    qtbot.keyClick(badge, QtCore.Qt.Key.Key_Space)
    assert seen == ["ip"]


def test_the_icon_and_glyph_variants_have_no_room_for_a_cross(root, loader):
    icon = StatusBadge(code="ip", status=IN_PROGRESS, variant="icon", removable=True, loader=loader)
    bare = StatusBadge(code="ip", status=IN_PROGRESS, variant="glyph", removable=True, loader=loader)
    both = StatusBadge(code="ip", status=IN_PROGRESS, variant="both", removable=True, loader=loader)
    assert icon.removable is True
    assert icon.sizeHint().width() < both.sizeHint().width()
    assert bare.sizeHint().width() == bare.sizeHint().height()


def test_every_setter_repaints(root, loader):
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, loader=loader))
    badge.set_code("fin")
    badge.set_status(None)
    badge.set_field(field())
    badge.set_variant("text")
    badge.set_color(True)
    badge.set_label("code")
    badge.set_size("lg")
    badge.set_site_url("https://site.example.com")
    badge.set_removable(True)
    badge.set_remove_label("Drop it")
    place(root, badge)
    assert badge.code == "fin"
    assert badge.status_name == "Final"
    assert badge.remove_label == "Drop it"
    assert counts(image(badge))


def test_disabled_is_inert(root, loader):
    badge = place(root, StatusBadge(code="ip", status=IN_PROGRESS, removable=True, loader=loader))
    badge.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    assert badge.disabled_opacity() == 0.5
    assert counts(image(badge))
