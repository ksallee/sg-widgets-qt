"""The field value: every data type, through the widget face and through the delegate face.

Every test runs on both bindings, offscreen, and never reaches the network.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.render import FieldTextOptions
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import ImageMapIcon, StatusRecord
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.base import CHIP_HEIGHT, text_width
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_chip import EntityChip
from sg_widgets_qt.widgets.field_value import (
    FieldValue,
    FieldValueOptions,
    field_value_size_hint,
    paint_field_value,
    plan_field_value,
)
from sg_widgets_qt.widgets.status_badge import StatusBadge
from sg_widgets_qt.widgets.thumbnail import Thumbnail

#: The colour `GET /entity/statuses` sends: comma-separated decimal RGB, never hex (probe 010).
IN_PROGRESS = StatusRecord(
    id=306,
    code="ip",
    name="In Progress",
    bg_color="43,139,214",
    icon=ImageMapIcon(image_map_key="icon_ip"),
)

SHOT = {"type": "Shot", "id": 862, "name": "sh010_0010"}

ASSETS = [
    {"type": "Asset", "id": 1226, "name": "charAda"},
    {"type": "Asset", "id": 1227, "name": "charBabbage"},
    {"type": "Asset", "id": 1228, "name": "envForest"},
]

UPLOADED = {
    "url": "https://s3.example.com/9f2/sh010_0010_comp_v001.mov?X-Amz-Expires=900",
    "name": "sh010_0010_comp_v001.mov",
    "link_type": "upload",
    "type": "Attachment",
    "id": 1430,
}

LOCAL = {
    "link_type": "local",
    "name": "plate.exr",
    "local_path_mac": "/Volumes/shows/sh010/plate.exr",
    "local_path_linux": "/mnt/shows/sh010/plate.exr",
    "local_path_windows": "P:\\shows\\sh010\\plate.exr",
}


def status_field() -> FieldSchema:
    return FieldSchema(
        name="sg_status_list",
        display_name="Status",
        entity_type="Version",
        data_type="status_list",
        editable=True,
        mandatory=False,
        unique=False,
        valid_values=["ip", "fin"],
        display_values={"ip": "In progress", "fin": "Final"},
    )


class StubLoader(ImageLoader):
    """A loader that answers one pixmap on the spot, so no test reaches the network."""

    def __init__(self, pixmap: QtGui.QPixmap | None = None) -> None:
        super().__init__()
        self.asked: list[str] = []
        self._answer = pixmap

    def load(self, url, on_ready, size=None):  # noqa: D102
        self.asked.append(str(url))
        on_ready(self._answer)


@pytest.fixture
def loader():
    return StubLoader()


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget, width: int = 400):
    widget.setParent(parent)
    widget.resize(width, max(1, widget.sizeHint().height()))
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def options(**changes) -> FieldValueOptions:
    return FieldValueOptions(theme=theme_for("default"), **changes)


def painted(value, data_type, opts: FieldValueOptions, width: int = 400, height: int = 32):
    """The value drawn by the delegate face onto a white ground."""
    picture = QtGui.QPixmap(width, height)
    picture.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(picture)
    paint_field_value(painter, QtCore.QRect(0, 0, width, height), value, data_type, opts)
    painter.end()
    return picture.toImage()


def ink_count(image: QtGui.QImage) -> int:
    """How many pixels are not the white ground, which is what proves something was drawn."""
    white = QtGui.QColor("white").rgb()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) != white
    )


# --- the plan both faces read ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "value", "kind"),
    [
        ("text", "Plate delivered.", "text"),
        ("list", "Type A", "list"),
        ("number", 1001, "number"),
        ("float", "1.777778", "number"),
        ("percent", 50, "number"),
        ("currency", 12500, "number"),
        ("duration", 480, "number"),
        ("timecode", 3600000, "number"),
        ("footage", 24, "number"),
        ("date", "2026-09-02", "date"),
        ("date_time", "2026-09-02T15:58:21Z", "datetime"),
        ("checkbox", True, "checkbox"),
        ("status_list", "ip", "status"),
        ("entity", SHOT, "entity"),
        ("multi_entity", ASSETS, "multi_entity"),
        ("tag_list", ASSETS, "multi_entity"),
        ("entity_type", "Shot", "text"),
        ("color", "253,94,99", "color"),
        ("image", "https://example.test/a.jpg", "image"),
        ("url", UPLOADED, "url"),
        ("uuid", "8f14e45f-ea0e", "text"),
        ("jsonb", '{"a": 1}', "text"),
        ("serializable", "x", "text"),
        ("calculated", "12", "text"),
        ("summary", "3", "text"),
        ("pivot_column", None, "empty"),
    ],
)
def test_every_data_type_draws_by_its_kind(root, data_type, value, kind):
    value_widget = place(root, FieldValue(value=value, data_type=data_type))
    assert value_widget.kind == kind
    # The delegate face reads the same plan, so the two never disagree on what a value is.
    assert plan_field_value(value, data_type, options()).kind == kind


def test_the_empty_value_is_a_marker_and_never_a_dash(root):
    value_widget = place(root, FieldValue(value=None, data_type="text"))
    assert value_widget.kind == "empty"
    assert value_widget.plan.text == "empty"
    assert place(root, FieldValue(value="", data_type="text")).kind == "empty"
    assert place(root, FieldValue(value=[], data_type="multi_entity")).kind == "empty"
    # Zero and false are values, not emptiness (field_types/number, checkbox).
    assert place(root, FieldValue(value=0, data_type="number")).kind == "number"
    assert place(root, FieldValue(value=False, data_type="checkbox")).kind == "checkbox"


def test_a_number_is_tabular_and_takes_its_alignment_from_the_collection(root):
    """The web widget draws a number `tabular-nums` and leaves it in the flow of the line.

    Right-aligning a column is the table's decision, and a table hands it down through
    `FieldValueOptions.align`; a value on its own has no column and reads left to right.
    """
    number = place(root, FieldValue(value=1001, data_type="number"))
    assert number.plan.tabular is True
    assert number.plan.align == "left"
    assert plan_field_value(1001, "number", options(align="right")).align == "right"
    # A uuid is text, in the same face as the rest (field-value.tsx draws no code face).
    uuid = place(root, FieldValue(value="8f14e45f", data_type="uuid"))
    assert uuid.plan.mono is False
    assert uuid.plan.tabular is False
    # A colour keeps the mono face, which the web widget gives it and nothing else.
    assert place(root, FieldValue(value="253,94,99", data_type="color")).plan.mono is True


def test_the_site_preferences_reach_every_formatter(root):
    def text_of(value, data_type, **kwargs):
        return place(root, FieldValue(value=value, data_type=data_type, **kwargs)).plan.text

    assert text_of(480, "duration") == "8:00"
    assert text_of(480, "duration", hours_per_day=8) == "1d"
    assert text_of("1.777778", "float", precision=2) == "1.78"
    assert text_of(12500, "currency", currency_symbol="€") == "€12,500.00"
    assert text_of(3600000, "timecode", frame_rate=24) == "01:00:00:00"
    assert text_of("2026-09-02", "date", locale="de-DE") == "02.09.2026"
    assert text_of("2026-09-02T23:58:21Z", "date_time", time_zone="Asia/Tokyo").startswith(
        "Sep 3, 2026"
    )


# --- the widget face -------------------------------------------------------------------------


def test_a_linked_row_is_a_chip_and_a_status_is_a_badge(root, loader):
    linked = place(root, FieldValue(value=SHOT, data_type="entity", loader=loader))
    chips = linked.findChildren(EntityChip)
    assert len(chips) == 1
    assert chips[0].label == "sh010_0010"

    badge = place(
        root,
        FieldValue(
            value="ip",
            data_type="status_list",
            statuses={"ip": IN_PROGRESS},
            field=status_field(),
            loader=loader,
        ),
    )
    found = badge.findChildren(StatusBadge)
    assert len(found) == 1
    assert found[0].status_name == "In Progress"

    picture = place(root, FieldValue(value="https://example.test/a.jpg", data_type="image", loader=loader))
    assert len(picture.findChildren(Thumbnail)) == 1


def test_a_multi_entity_row_wraps_the_chips_it_has_no_room_for(root, loader):
    """The web widget lays its chips out with `flex-wrap`, so a chip that does not fit drops.

    Nothing is hidden and nothing is counted: a cell only one line high shows the first line,
    the way the web table's own cell clips what runs past it.
    """
    value = FieldValue(value=ASSETS, data_type="multi_entity", loader=loader)
    place(root, value, width=1000)
    row = value.child
    assert len(row.chips) == len(ASSETS)
    assert row.lines == 1

    place(root, value, width=150)
    value.resize(150, value.heightForWidth(150))
    QtWidgets.QApplication.processEvents()
    assert len(row.chips) == len(ASSETS)
    assert row.lines > 1
    # The block is as tall as the lines it took, so nothing is cut off the bottom.
    assert value.heightForWidth(150) >= row.lines * CHIP_HEIGHT["sm"]


def test_a_compact_collection_draws_the_chip_a_step_smaller(root, loader):
    default = place(root, FieldValue(value=SHOT, data_type="entity", loader=loader))
    compact = place(
        root, FieldValue(value=SHOT, data_type="entity", density="compact", loader=loader)
    )
    assert default.child.chips[0].size_step == "sm"
    assert compact.child.chips[0].size_step == "xs"
    assert compact.child.sizeHint().height() == CHIP_HEIGHT["xs"]


def test_a_url_takes_the_keyboard_and_a_local_link_carries_its_path(root):
    uploaded = place(root, FieldValue(value=UPLOADED, data_type="url"))
    assert uploaded.plan.text == "sh010_0010_comp_v001.mov"
    assert uploaded.url.startswith("https://s3.example.com/")
    assert uploaded.focusPolicy() == QtCore.Qt.FocusPolicy.TabFocus

    local = place(root, FieldValue(value=LOCAL, data_type="url"))
    assert local.plan.text == "plate.exr"
    assert local.plan.link.local is not None
    assert local.plan.tooltip in (
        LOCAL["local_path_mac"],
        LOCAL["local_path_linux"],
        LOCAL["local_path_windows"],
    )
    assert local.url.startswith("file:")

    # An app that opens paths its own way rewrites the href.
    rewritten = place(
        root,
        FieldValue(value=LOCAL, data_type="url", local_href=lambda link: "sg://open"),
    )
    assert rewritten.url == "sg://open"

    # A value that opens nowhere never takes the focus.
    assert place(root, FieldValue(value=1001, data_type="number")).focusPolicy() == (
        QtCore.Qt.FocusPolicy.NoFocus
    )


def test_a_colour_draws_its_own_swatch_and_the_sentinel_reads_as_a_step(root):
    swatch = place(root, FieldValue(value="253,94,99", data_type="color"))
    assert swatch.plan.rgb is not None
    assert (swatch.plan.rgb.r, swatch.plan.rgb.g, swatch.plan.rgb.b) == (253, 94, 99)
    image = swatch.grab().toImage()
    wanted = QtGui.QColor(253, 94, 99).rgb()
    assert any(
        image.pixel(x, y) == wanted
        for y in range(image.height())
        for x in range(min(20, image.width()))
    )

    # `Task.color` holds the token `pipeline_step` rather than a colour (field_types/color).
    sentinel = place(root, FieldValue(value="pipeline_step", data_type="color"))
    assert sentinel.plan.sentinel is True
    assert sentinel.plan.text == "pipeline step"
    assert sentinel.plan.rgb is None


# --- the delegate face -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "value"),
    [
        ("text", "Plate delivered."),
        ("number", 1001),
        ("date", "2026-09-02"),
        ("date_time", "2026-09-02T15:58:21Z"),
        ("checkbox", True),
        ("checkbox", False),
        ("status_list", "ip"),
        ("entity", SHOT),
        ("multi_entity", ASSETS),
        ("image", "https://example.test/a.jpg"),
        ("url", UPLOADED),
        ("color", "253,94,99"),
        ("uuid", "8f14e45f-ea0e"),
        ("pivot_column", None),
    ],
)
def test_the_delegate_face_draws_every_data_type(qtbot, loader, data_type, value):
    opts = options(statuses={"ip": IN_PROGRESS}, field=status_field(), loader=loader)
    assert ink_count(painted(value, data_type, opts)) > 0
    hint = field_value_size_hint(value, data_type, opts)
    assert hint.width() > 0
    assert hint.height() > 0


def test_the_delegate_face_and_the_widget_agree_on_the_text(root):
    for data_type, value in [
        ("number", 1001),
        ("float", "1.777778"),
        ("date", "2026-09-02"),
        ("list", "Type A"),
        ("url", UPLOADED),
        ("color", "253,94,99"),
    ]:
        widget = place(root, FieldValue(value=value, data_type=data_type))
        assert widget.plan.text == plan_field_value(value, data_type, options()).text


def test_a_cell_takes_its_alignment_and_its_schema_from_its_column(qtbot):
    from sg_widgets_core.collection import CollectionColumn

    column = CollectionColumn(
        path="sg_status_list",
        header="Status",
        data_type="status_list",
        align="left",
        field=status_field(),
    )
    plan = plan_field_value("fin", column, options())
    assert plan.kind == "status"
    # The Status row's name first, then the field's display value, then the code itself.
    assert plan.text == "Final"
    assert plan_field_value("fin", column, options(statuses={"fin": IN_PROGRESS})).text == (
        "In Progress"
    )

    number = CollectionColumn(path="cut_duration", header="Cut", data_type="number", align="right")
    assert plan_field_value(12, number, options()).align == "right"
    assert plan_field_value(12, number, options(align="left")).align == "left"


def test_a_cell_keeps_free_text_on_one_line(qtbot):
    """A cell is one line, so a description's newlines collapse rather than growing the row."""
    value = "Plate delivered.\nSecond pass pending."
    tall = field_value_size_hint(value, "text", options(wrap=True), width=120)
    flat = field_value_size_hint(value, "text", options())
    assert tall.height() > flat.height()
    assert ink_count(painted(value, "text", options(), height=20)) > 0


def test_the_site_preferences_reach_the_delegate_face(qtbot):
    opts = options(text=FieldTextOptions(hours_per_day=8, decimals=2, currency_symbol="€"))
    assert plan_field_value(480, "duration", opts).text == "1d"
    assert plan_field_value("1.777778", "float", opts).text == "1.78"
    assert plan_field_value(12500, "currency", opts).text == "€12,500.00"


# --- what the upstream markup decided per type -------------------------------------------------


def test_a_checkbox_is_the_switch_the_web_widget_draws(root):
    """`field-value.tsx` renders `<Switch size="sm" checked disabled aria-readonly />`.

    A disabled switch with the dimming turned off: the two states read at full contrast and
    nothing about it invites a press. A tick and a cross would be a different reading of the
    same field, so the port draws the primitive the web widget names.
    """
    from sg_widgets_qt.primitives.checkbox import Switch

    on = place(root, FieldValue(value=True, data_type="checkbox"))
    off = place(root, FieldValue(value=False, data_type="checkbox"))
    assert isinstance(on.child, Switch)
    assert on.child.checked is True
    assert off.child.checked is False
    # Inert, out of the tab order, and never dimmed: `data-disabled:opacity-100` upstream.
    assert on.child.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
    assert on.child.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert on.child.isEnabled() is True
    assert on.plan.text == "Yes"
    assert off.plan.text == "No"


def test_a_url_is_an_underline_and_nothing_else(root):
    """The web widget's anchor carries `underline` and no mark of its own, so neither does this.

    Where a link goes is the link's business; a glyph beside it is a second thing to read.
    """
    value = place(root, FieldValue(value=UPLOADED, data_type="url"))
    plain = field_value_size_hint(UPLOADED, "url", options())
    metrics = QtGui.QFontMetrics(theme_for("default").font(14))
    # The value asks for its text and not a pixel more, so nothing is drawn beside it.
    assert plain.width() == text_width(metrics, value.plan.text)


# --- the two faces, pixel for pixel ------------------------------------------------------------


FACE_CASES = [
    ("text", "Plate delivered."),
    ("list", "Type A"),
    ("number", 1001),
    ("float", "1.777778"),
    ("percent", 50),
    ("currency", 12500),
    ("duration", 480),
    ("timecode", 3600000),
    ("footage", 24),
    ("date", "2026-09-02"),
    ("date_time", "2026-09-02T15:58:21Z"),
    ("checkbox", True),
    ("checkbox", False),
    ("status_list", "ip"),
    ("status_list", "unknown_code"),
    ("entity", SHOT),
    ("multi_entity", ASSETS),
    ("tag_list", ASSETS),
    ("entity_type", "Sequence"),
    ("uuid", "8f14e45f-ea0e"),
    ("jsonb", '{"a": 1}'),
    ("serializable", "x"),
    ("calculated", "12"),
    ("summary", "3"),
    ("color", "253,94,99"),
    ("color", "pipeline_step"),
    ("url", UPLOADED),
    ("url", LOCAL),
    ("pivot_column", None),
    ("text", None),
]


def rendered(widget: QtWidgets.QWidget, size: QtCore.QSize) -> QtGui.QImage:
    """The widget and every child under it, into an image of `size`."""
    image = QtGui.QImage(size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    widget.render(
        image,
        QtCore.QPoint(0, 0),
        QtGui.QRegion(0, 0, size.width(), size.height()),
        QtWidgets.QWidget.RenderFlag.DrawChildren,
    )
    return image


def through_delegate(value: FieldValue, size: QtCore.QSize) -> QtGui.QImage:
    """The same value through the delegate face, into an image of the same size."""
    image = QtGui.QImage(size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    paint_field_value(
        painter,
        QtCore.QRect(0, 0, size.width(), size.height()),
        value.value,
        value.data_type,
        value.options(),
    )
    painter.end()
    return image


@pytest.mark.parametrize(("data_type", "value"), FACE_CASES)
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("density", ["default", "compact"])
def test_the_two_faces_draw_the_same_pixels(qtbot, loader, data_type, value, dark, density):
    """A cell and a widget never disagree about a value, which is what the docs page claims.

    The widget composes EntityChip, StatusBadge and Thumbnail; the delegate paints the same
    shapes itself. The only proof the two have not drifted is the pixels.
    """
    root = QtWidgets.QWidget()
    apply_theme(root, theme_for("default", dark=dark))
    qtbot.addWidget(root)
    root.resize(600, 200)
    root.show()

    size = QtCore.QSize(320, 32)
    widget = FieldValue(
        value=value,
        data_type=data_type,
        density=density,
        statuses={"ip": IN_PROGRESS},
        field=status_field(),
        loader=loader,
        parent=root,
    )
    widget.resize(size)
    widget.show()
    QtWidgets.QApplication.processEvents()
    assert rendered(widget, size) == through_delegate(widget, size)


def test_a_status_with_nothing_to_draw_keeps_the_badge_bare(qtbot, loader):
    """A code the site has no Status row for is a bordered label, never a stand-in dot.

    Upstream's badge draws its glyph only where the status has one; `fallback` is the bare glyph
    variant's, and a value is never that variant.
    """
    known = options(statuses={"ip": IN_PROGRESS}, loader=loader)
    unknown = options(statuses={}, loader=loader)
    with_glyph = field_value_size_hint("ip", "status_list", known)
    without = field_value_size_hint("ip", "status_list", unknown)
    # The glyph and the room beside it are what the wider badge is carrying.
    assert with_glyph.width() > without.width()
    assert with_glyph.height() == without.height() == CHIP_HEIGHT["sm"]


def test_the_colour_sentinel_keeps_its_token_in_the_tooltip(root):
    """The value shown is words; the value held is the token (field_types/color)."""
    sentinel = place(root, FieldValue(value="pipeline_step", data_type="color"))
    assert sentinel.plan.text == "pipeline step"
    assert sentinel.plan.tooltip == "pipeline_step"
    assert sentinel.toolTip() == "pipeline_step"
    colour = place(root, FieldValue(value="253,94,99", data_type="color"))
    assert colour.plan.tooltip == "253,94,99"


def test_a_linked_value_leaves_the_tooltip_to_its_chips(root, loader):
    """A chip carries its own, so the value around it carries none, as upstream does."""
    linked = place(root, FieldValue(value=SHOT, data_type="entity", loader=loader))
    assert linked.plan.tooltip == ""
    assert linked.toolTip() == ""
    many = place(root, FieldValue(value=ASSETS, data_type="multi_entity", loader=loader))
    assert many.toolTip() == ""
    # A single-line rendering still carries the full value, which is the design rule.
    assert place(root, FieldValue(value="Type A", data_type="list")).toolTip() == "Type A"
