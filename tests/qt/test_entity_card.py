"""The entity card: what it describes, what it reads, and its three states.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_core.client import EntityRow, SearchOptions
from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.entity_card import EntityCardOptions, entity_card_fields
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.mock import MockClient
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.base import THUMB_SIZE
from sg_widgets_qt.primitives.skeleton import Skeleton
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_card import (
    CARD_THUMB,
    EntityCard,
    _CardValue,
    _FieldLabel,
)
from sg_widgets_qt.widgets.state_line import StateLine
from sg_widgets_qt.widgets.status_badge import StatusBadge
from sg_widgets_qt.widgets.thumbnail import Thumbnail

#: Four paths. The first dotted through a link that accepts several types, and the last the row's
#: own status, which the header draws and the grid therefore does not.
FIELDS = ["entity.Shot.sg_sequence", "user", "description", "sg_status_list"]

#: A site to address rows on, so the name has somewhere to point.
SITE = "https://demo.example.com"


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
def context():
    return create_sg_context(
        MockClient(seed=1, latency_ms=0), SgContextOptions(site_url=SITE)
    )


@pytest.fixture
def rows(context):
    fields = entity_card_fields(
        context, "Version", EntityCardOptions(fields=list(FIELDS), image_path="image")
    )
    found = context.client.search("Version", SearchOptions(fields=fields, page={"size": 2}))
    assert found.data
    return found.data


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 500)
    widget.show()
    return widget


def settle(qtbot, card: EntityCard) -> EntityCard:
    """Wait for the card's own read, which runs on a worker and never on the GUI thread."""
    qtbot.waitUntil(lambda: not card.loading, timeout=5000)
    QtWidgets.QApplication.processEvents()
    return card


def place(root: QtWidgets.QWidget, card: EntityCard) -> EntityCard:
    card.setParent(root)
    card.resize(500, max(1, card.sizeHint().height()))
    card.show()
    QtWidgets.QApplication.processEvents()
    return card


def test_a_card_from_a_row_describes_it(qtbot, root, context, rows, loader):
    card = place(root, EntityCard(context=context, row=rows[0], fields=FIELDS, loader=loader))
    settle(qtbot, card)
    assert card.error is None
    assert card.name == rows[0].values["code"]
    assert card.model.type_label == "Version"
    assert card.url == f"{SITE}/detail/Version/{rows[0].id}"

    # The header names the row's own status, so the same field in the grid is not drawn twice.
    assert card.model.status is not None
    assert [column.path for column in card.model.columns] == FIELDS[:-1]
    assert len(card.findChildren(StatusBadge)) == 1
    assert len(card.findChildren(Thumbnail)) == 1

    # A hop names the type it travels through only where the field accepts several (probe 059).
    assert card.model.columns[0].label == "Link › Shot › Sequence"


def test_a_card_from_a_reference_reads_the_row(qtbot, root, context, rows, loader):
    card = place(
        root,
        EntityCard(
            context=context,
            entity=EntityRef(type=rows[0].type, id=rows[0].id),
            fields=FIELDS,
            loader=loader,
        ),
    )
    settle(qtbot, card)
    assert card.error is None
    assert card.model.entity.id == rows[0].id
    assert card.name == rows[0].values["code"]

    # A second reference replaces the first, and the card reads again.
    card.set_entity(EntityRef(type=rows[1].type, id=rows[1].id))
    settle(qtbot, card)
    assert card.model.entity.id == rows[1].id


def test_a_card_with_no_row_yet_shows_a_skeleton_shaped_like_it(qtbot, root, context, rows, loader):
    class _NeverPool:
        def submit(self, fn, *args, **kwargs):
            return None

    card = place(
        root,
        EntityCard(
            context=context, row=rows[0], fields=FIELDS, pool=_NeverPool(), loader=loader
        ),
    )
    assert card.loading is True
    assert card.model is None
    blocks = card.findChildren(Skeleton)
    # One for the picture, two for the name and the type, and two per field of the grid.
    assert len(blocks) == 3 + 2 * len(FIELDS)
    assert all(block.isVisible() for block in blocks)


def test_a_read_that_failed_says_what_it_said(qtbot, root, context, loader):
    card = place(
        root,
        EntityCard(
            context=context, entity=EntityRef(type="Version", id=0), fields=FIELDS, loader=loader
        ),
    )
    settle(qtbot, card)
    assert card.model is None
    lines = card.findChildren(StateLine)
    assert len(lines) == 1
    assert lines[0].state == "error"
    assert lines[0].label == "Version 0 is not readable."

    # A caller's own label replaces what the read said.
    card.set_error_label("This version has gone")
    assert card.findChildren(StateLine)[0].label == "This version has gone"


def test_a_card_needs_a_context_and_a_row(qtbot, root, rows):
    without_context = place(root, EntityCard(row=rows[0], fields=FIELDS))
    assert without_context.error == "An entity card needs a context or a client."

    context = create_sg_context(MockClient(seed=1, latency_ms=0))
    without_row = place(root, EntityCard(context=context, fields=FIELDS))
    assert without_row.error == "An entity card needs a row or a reference."


def test_the_field_labels_sit_on_the_baseline_of_their_values(qtbot, root, context, rows, loader):
    card = place(root, EntityCard(context=context, row=rows[0], fields=FIELDS, loader=loader))
    settle(qtbot, card)
    labels = card.findChildren(_FieldLabel)
    values = card.values
    assert len(labels) == len(values) == len(FIELDS) - 1
    for label, value in zip(labels, values):
        # The label is a size under the value, so one baseline holds the two level.
        assert label._baseline == value.baseline()
        assert label.y() == value.y()


def test_a_value_is_drawn_by_its_data_type(qtbot, root, context, rows, loader):
    row = EntityRow(
        type=rows[0].type,
        id=rows[0].id,
        values={
            **rows[0].values,
            "sg_uploaded_movie": {
                "url": "https://s3.example.com/x.mov",
                "name": "x.mov",
                "link_type": "upload",
            },
        },
    )
    card = place(
        root,
        EntityCard(
            context=context,
            row=row,
            fields=["user", "description", "image", "sg_uploaded_movie"],
            loader=loader,
        ),
    )
    settle(qtbot, card)
    kinds = [value.kind for value in card.values]
    assert kinds == ["entity", "text", "image", "url"]

    linked = card.values[0]
    linked.resize(300, linked.sizeHint().height())
    linked.grab()
    assert [link.url for link in linked.links] == [
        f"{SITE}/detail/HumanUser/{row.values['user']['id']}"
    ]
    assert isinstance(card.values[2].child, Thumbnail)
    assert card.values[3].text == "x.mov"

    # A path that names no field is shown under its own text with an empty value (probe 059).
    empty = place(
        root, EntityCard(context=context, row=rows[0], fields=["no_such_field"], loader=loader)
    )
    settle(qtbot, empty)
    assert empty.model.columns[0].label == "no_such_field"
    assert empty.values[0].kind == "empty"


def test_a_size_moves_the_thumbnail_and_the_badge(qtbot, root, context, rows, loader):
    for size in ("sm", "md", "lg"):
        card = place(
            root,
            EntityCard(context=context, row=rows[0], fields=FIELDS, size=size, loader=loader),
        )
        settle(qtbot, card)
        picture = card.findChildren(Thumbnail)[0]
        assert picture.size == CARD_THUMB[size]
        assert picture.height() == THUMB_SIZE[CARD_THUMB[size]]
    card.set_size("sm")
    settle(qtbot, card)
    assert card.size == "sm"
    assert card.findChildren(Thumbnail)[0].size == "xl"


def test_the_chip_previews_through_a_card(qtbot, monkeypatch, root, context, rows, loader):
    from sg_widgets_qt.widgets.entity_chip import EntityChip, default_preview_builder

    # The default builder makes the card itself, so the stub loader goes in where it reads.
    monkeypatch.setattr("sg_widgets_qt.widgets.entity_card.image_loader", lambda: loader)

    chip = EntityChip(
        entity=EntityRef(type=rows[0].type, id=rows[0].id, name="sh010"),
        preview=["user"],
        context=context,
        parent=root,
    )
    qtbot.addWidget(chip)
    assert chip.hover_card is not None
    preview = default_preview_builder(chip.entity, chip.preview, context)
    qtbot.addWidget(preview)
    assert isinstance(preview, EntityCard)
    assert preview.fields == ["user"]
    settle(qtbot, preview)
    assert preview.name == rows[0].values["code"]


def test_a_value_keeps_its_own_newlines(qtbot, root, context, rows, loader):
    row = EntityRow(
        type=rows[0].type,
        id=rows[0].id,
        values={**rows[0].values, "description": "Plate delivered.\nSecond pass pending."},
    )
    card = place(root, EntityCard(context=context, row=row, fields=["description"], loader=loader))
    settle(qtbot, card)
    value = card.values[0]
    assert isinstance(value, _CardValue)
    assert value.hasHeightForWidth() is True
    assert value.heightForWidth(80) > value.heightForWidth(600)


def test_the_header_skeleton_is_shaped_like_the_name_and_the_line_under_it(
    qtbot, root, context, rows, loader
):
    """A skeleton stands in for what it replaces: three quarters for the name, half under it.

    Upstream draws `w-3/4` and `w-1/2` there. A block that runs the whole header instead reads as
    a loading bar rather than as the card that is coming.
    """

    class _NeverPool:
        def submit(self, fn, *args, **kwargs):
            return None

    card = place(
        root,
        EntityCard(
            context=context, row=rows[0], fields=FIELDS, pool=_NeverPool(), loader=loader
        ),
    )
    QtWidgets.QApplication.processEvents()
    blocks = [block for block in card.findChildren(Skeleton) if block.isVisible()]
    picture = max(blocks, key=lambda block: block.height())
    header = [
        block
        for block in blocks
        if block is not picture and block.mapTo(card, block.rect().topLeft()).y() < picture.height()
    ]
    assert len(header) == 2
    name, meta = sorted(header, key=lambda block: block.mapTo(card, block.rect().topLeft()).y())
    room = name.parentWidget().parentWidget().width()
    assert room > 0
    assert 0.65 < name.width() / room < 0.85
    assert 0.4 < meta.width() / room < 0.6


def test_a_card_takes_its_selection_and_reports_only_a_change(qtbot, root, context, rows, loader):
    """A collection owns the selection, so the card takes it and says when it moved."""
    card = place(root, EntityCard(context=context, row=rows[0], fields=FIELDS, loader=loader))
    settle(qtbot, card)
    reported: list[bool] = []
    card.selected_changed.connect(reported.append)
    card.set_selected(True)
    card.set_selected(True)
    card.set_selected(False)
    assert reported == [True, False]
    assert card.selected is False


def test_the_name_emits_clicked_and_addresses_the_row(qtbot, monkeypatch, root, context, rows, loader):
    """A press on the name opens the row's own page and says so, and never leaves the test."""
    card = place(root, EntityCard(context=context, row=rows[0], fields=FIELDS, loader=loader))
    settle(qtbot, card)
    opened: list[str] = []
    monkeypatch.setattr(
        QtGui.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    fired: list[int] = []
    card.clicked.connect(lambda: fired.append(1))
    name = card.findChild(QtWidgets.QWidget, "entity-card-name")
    assert name is not None
    name._activate()
    assert fired == [1]
    assert card.url.startswith(SITE)
    assert "/detail/" in card.url
    assert opened == [card.url]


def test_a_value_underlines_a_link_only_under_the_pointer(qtbot, root, context, rows, loader):
    """A card is a stack of values: underlining every link turns the stack into a rule.

    Upstream's link class carries `hover:underline` and no underline at rest, so a value that
    happens to point somewhere reads as text until the pointer is on it.
    """
    card = place(root, EntityCard(context=context, row=rows[0], fields=FIELDS, loader=loader))
    settle(qtbot, card)
    linked = [value for value in card.values if value.kind in ("entity", "multi_entity")]
    assert linked
    value = linked[0]
    value.resize(320, max(1, value.sizeHint().height()))
    QtWidgets.QApplication.processEvents()

    def drawn() -> QtGui.QImage:
        picture = QtGui.QPixmap(value.size())
        picture.fill(QtGui.QColor("white"))
        value.render(picture)
        return picture.toImage()

    at_rest = drawn()
    assert value._links, "the value drew no link to hover"
    value._set_hovered_link(0)
    QtWidgets.QApplication.processEvents()
    hovered = drawn()
    assert hovered != at_rest
    # And the underline goes again once the pointer leaves the value.
    value.on_hover_changed(False)
    QtWidgets.QApplication.processEvents()
    assert drawn() == at_rest
