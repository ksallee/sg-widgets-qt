"""The row of rule 9 as a model: the roles it answers, the picture it loads, the status it draws."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPixmap
from qtpy.QtWidgets import QStyleOptionViewItem, QWidget

from sg_widgets_core.picker import PickerRow
from sg_widgets_core.render import initials_of, name_hue
from sg_widgets_core.status import StatusRecord
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.primitives.row_delegate import initials_of as delegate_initials
from sg_widgets_qt.primitives.row_delegate import label_weight
from sg_widgets_qt.primitives.row_delegate import name_hue as delegate_hue
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.picker_row import PickerRowModel, PickerRowWidget, status_painter
from sg_widgets_qt.widgets.search_control import SearchControl

SHOT = PickerRow(
    type="Shot",
    id=862,
    name="sh010_0010",
    values={"code": "sh010_0010", "description": "The opening plate", "sg_status_list": "ip"},
)
ADA = PickerRow(
    type="HumanUser",
    id=20,
    name="Ada Lovelace",
    values={"email": "ada@example.test", "image": "https://pictures.example.test/ada.png"},
)


class StubLoader(ImageLoader):
    """A loader that answers one pixmap on the spot, so no test reaches the network."""

    def __init__(self, pixmap: QPixmap | None) -> None:
        super().__init__()
        self.asked: list[str] = []
        self._answer = pixmap

    def load(self, url, on_ready, size=None):  # noqa: D102
        self.asked.append(str(url))
        on_ready(self._answer)


@pytest.fixture
def host(qtbot):
    widget = QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(420, 200)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def test_the_model_answers_every_part_of_the_row(host):
    model = PickerRowModel(
        [SHOT], host, query="sh010", sub_label_field="description", show_code=True
    )
    index = model.index(0, 0)
    assert model.data(index) == "sh010_0010"
    assert model.data(index, Roles.SUB_LABEL) == "The opening plate"
    assert model.data(index, Roles.GLYPH) == "clapperboard"
    assert model.data(index, Roles.ENTITY) is SHOT
    assert model.data(index, Roles.KIND) == "row"
    # `code` equals the label here, so it says nothing the label does not.
    assert model.data(index, Roles.CODE) == ""


def test_the_matched_words_come_back_as_runs(host):
    model = PickerRowModel([SHOT], host, query="010")
    runs = model.data(model.index(0, 0), Roles.RUNS)
    # Every occurrence is bold, because that is what the server matched on.
    assert [(text, matched) for text, matched, _ in runs] == [
        ("sh", False),
        ("010", True),
        ("_0", False),
        ("010", True),
    ]


def test_crumbs_lead_the_label_and_are_muted(host):
    model = PickerRowModel([SHOT], host)
    model.set_crumbs_of(lambda _row: ["Shots", "sh010"])
    runs = model.data(model.index(0, 0), Roles.RUNS)
    assert runs[0] == ("Shots", False, True)
    assert runs[1][2] is True
    assert runs[-1][2] is False


def test_a_picture_lands_on_the_row_that_asked_for_it(host, qtbot):
    picture = QPixmap(32, 32)
    picture.fill(QColor(10, 20, 30))
    loader = StubLoader(picture)
    model = PickerRowModel([ADA], host, loader=loader)
    index = model.index(0, 0)
    assert loader.asked == ["https://pictures.example.test/ada.png"]
    assert isinstance(model.data(index, Roles.PIXMAP), QPixmap)
    # A person with a picture draws it rather than initials.
    assert model.data(index, Roles.INITIALS) == ""


def test_a_person_with_no_picture_falls_back_to_initials(host):
    loader = StubLoader(None)
    model = PickerRowModel([ADA], host, loader=loader)
    assert model.data(model.index(0, 0), Roles.INITIALS) == "AL"


def test_a_status_secondary_draws_as_the_badge(host):
    """A status in a row's secondary column is a value, and rule 9 draws a value as the badge."""
    record = StatusRecord(id=1, code="ip", name="In Progress", bg_color="38,141,255")
    paint = status_painter("ip", statuses={"ip": record})
    option = QStyleOptionViewItem()
    option.widget = host
    canvas = QPixmap(200, 24)
    canvas.fill(Qt.GlobalColor.white)
    device = QPainter(canvas)
    paint(device, canvas.rect(), option)
    device.end()
    image = canvas.toImage()
    marks = [
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y) != QColor(255, 255, 255)
    ]
    assert marks
    # The badge is a bordered pill at the trailing edge, not a bare line of text.
    left = min(x for x, _ in marks)
    assert left > image.width() // 3
    top = min(y for _, y in marks)
    bottom = max(y for _, y in marks)
    assert any(x == left and top < y < bottom for x, y in marks)


def test_the_thumbnail_field_turns_the_leading_slot_off(host):
    loader = StubLoader(None)
    model = PickerRowModel([ADA], host, thumbnail=False, loader=loader)
    assert loader.asked == []
    assert model.read_fields() == []


def test_the_read_fields_name_everything_the_row_props_need(host):
    model = PickerRowModel(
        [SHOT],
        host,
        sub_label_field="description",
        secondary_field="sg_status_list",
        show_code=True,
        fields=["sg_sequence"],
    )
    assert model.read_fields(["id"]) == [
        "id",
        "description",
        "sg_status_list",
        "image",
        "code",
        "sg_sequence",
    ]


def test_appending_a_page_keeps_the_rows_already_there(host):
    model = PickerRowModel([SHOT], host)
    model.append_rows([ADA])
    assert model.rowCount() == 2
    assert model.row_at(1) is ADA
    assert model.index_of_key("HumanUser:20") == 1


def test_the_widget_paints_one_row_on_its_own(host, qtbot):
    widget = PickerRowWidget(SHOT, host, sub_label_field="description")
    qtbot.addWidget(widget)
    widget.resize(320, 48)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.sizeHint().height() > 0
    assert widget.model.rowCount() == 1
    widget.set_size("lg")
    assert widget.model.size == "lg"
    assert widget.grab().size() != QSize(0, 0)


def test_the_delegate_takes_its_hue_and_its_initials_from_core():
    assert delegate_hue("Ada Lovelace") == name_hue("Ada Lovelace")
    assert delegate_initials("Anna van der Meer") == initials_of("Anna van der Meer")


@dataclass
class Heading:
    """A group heading among the rows, which names no entity type."""

    name: str
    type: str = ""
    id: int = 0
    values: dict = field(default_factory=dict)


class StubSchema:
    """The one schema read the secondary's plan makes."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []

    def field(self, entity_type: str, path: str):  # noqa: D102, ANN201
        self.asked.append((entity_type, path))
        return None


class StubContext:
    """A context with a schema and no status table."""

    def __init__(self) -> None:
        self.schema = StubSchema()
        self.statuses = None


def test_the_secondary_schema_is_read_off_the_first_row_that_names_a_type(host, qtbot):
    """A grouped list leads with a heading, which must not hold the plan back."""
    context = StubContext()
    model = PickerRowModel(
        [Heading("Shot"), SHOT], host, context=context, secondary_field="sg_status_list"
    )
    qtbot.waitUntil(lambda: bool(context.schema.asked), timeout=3000)
    assert context.schema.asked == [("Shot", "sg_status_list")]
    assert model.rowCount() == 2


def test_a_label_behind_crumbs_is_drawn_one_weight_step_up():
    plain = [("sh010_0010", False, False)]
    crumbed = [("Shots", False, True), (" › ", False, True), ("FX", False, False)]
    assert label_weight(plain) == QFont.Weight.Normal
    assert label_weight(crumbed) == QFont.Weight.Medium


def test_a_glyph_the_caller_named_is_drawn_with_no_picture_box(host, qtbot):
    """A tree level names its glyph beside a picture field, so the glyph is the fallback.

    `picker-row.tsx` keeps the thumbnail ladder there and draws the glyph inside it; only a
    row that was never to have a picture (`thumbnail={false}`) takes the glyph's own slot.
    """
    named = PickerRowModel([SHOT], host, thumbnail="image")
    named.set_glyph_of(lambda _row: "folder")
    assert named.bare_glyph is False

    control = SearchControl(host, model=named)
    qtbot.addWidget(control)
    assert control.list_surface().row_delegate().bare_glyph is False

    pictureless = PickerRowModel([SHOT], host, thumbnail=False)
    pictureless.set_glyph_of(lambda _row: "folder")
    assert pictureless.bare_glyph is True


def test_a_page_landing_under_the_rows_is_an_insert_not_a_reset(qtbot):
    # A reset drops a view's scroll position and its keyboard cursor, so the list would jump
    # to the top under a reader. Only a set of rows that is not an extension is a reset.
    model = PickerRowModel([SHOT], loader=ImageLoader(timeout=0))
    events: list = []
    model.modelReset.connect(lambda: events.append("reset"))
    model.rowsInserted.connect(lambda _p, first, last: events.append(("inserted", first, last)))

    model.set_rows([SHOT, ADA])
    assert events == [("inserted", 1, 1)]
    assert model.rowCount() == 2

    events.clear()
    model.set_rows([SHOT, ADA])
    assert events == []

    events.clear()
    model.set_rows([ADA])
    assert events == ["reset"]
    assert model.rowCount() == 1


def test_the_sub_label_marks_its_matched_runs_too(host):
    """A row matched on its email shows why, as upstream's MatchText on the sub-label does."""
    model = PickerRowModel([ADA], host, query="ada", sub_label_field="email")
    runs = model.data(model.index(0, 0), Roles.SUB_RUNS)
    assert "".join(text for text, _ in runs) == "ada@example.test"
    assert [text for text, matched in runs if matched] == ["ada"]
    # A row with no query marks nothing and keeps its line whole.
    plain = PickerRowModel([ADA], host, sub_label_field="email")
    assert [text for text, matched in plain.data(plain.index(0, 0), Roles.SUB_RUNS) if matched] == []


def test_a_bare_glyph_row_takes_the_glyphs_own_slot(qtbot):
    # Rule 9: the leading slot is as big as what it holds. A row that draws its own glyph and
    # never expected a picture stands on the row pitch, not on the thumbnail one.
    from sg_widgets_qt.primitives.list_view import ListSurface
    from sg_widgets_qt.primitives.row_delegate import (
        LEAD,
        LEAD_GLYPH,
        ROW_LINE,
        ROW_PAD_Y,
        RowDelegate,
    )

    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    view = ListSurface(root)
    model = PickerRowModel([SHOT], loader=ImageLoader(timeout=0))
    view.setModel(model)
    delegate = RowDelegate(view, size="md")
    option = QStyleOptionViewItem()
    option.rect = QPixmap(320, 48).rect()
    option.widget = view

    picture = delegate.sizeHint(option, view.model().index(0, 0)).height()
    assert delegate._lead_size() == LEAD["md"]
    assert picture == LEAD["md"] + 2 * ROW_PAD_Y

    delegate.set_bare_glyph(True)
    glyph = delegate.sizeHint(option, view.model().index(0, 0)).height()
    assert delegate._lead_size() == LEAD_GLYPH["md"]
    assert glyph < picture, "a bare glyph row is not on the thumbnail pitch"
    # Nothing in the row is taller than its own label any more, so the label sets the pitch,
    # and a label's height is the line its type step sits on rather than the font's own metrics.
    assert glyph == max(ROW_LINE["md"], LEAD_GLYPH["md"]) + 2 * ROW_PAD_Y
