"""The row of rule 9 as a model: the roles it answers, the picture it loads, the status it draws."""
from __future__ import annotations

import pytest
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor, QPainter, QPixmap
from qtpy.QtWidgets import QStyleOptionViewItem, QWidget

from sg_widgets_core.picker import PickerRow
from sg_widgets_core.render import initials_of, name_hue
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.primitives.row_delegate import initials_of as delegate_initials
from sg_widgets_qt.primitives.row_delegate import name_hue as delegate_hue
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.picker_row import PickerRowModel, PickerRowWidget, status_painter

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


def test_a_status_secondary_draws_as_a_glyph_and_a_name(host):
    paint = status_painter("In progress", "#2563eb")
    option = QStyleOptionViewItem()
    option.widget = host
    canvas = QPixmap(200, 24)
    canvas.fill(Qt.GlobalColor.white)
    device = QPainter(canvas)
    paint(device, canvas.rect(), option)
    device.end()
    image = canvas.toImage()
    marks = [
        image.pixelColor(x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y) != QColor(255, 255, 255)
    ]
    # The status colour is drawn as the dot, and the name beside it.
    assert marks
    assert any(colour.blue() > colour.red() for colour in marks)


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
