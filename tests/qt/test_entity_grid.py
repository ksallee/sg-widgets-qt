"""The entity grid: its tiles, its cursor, its selection, its paging and its states.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore
from qtpy.QtCore import Qt
from qtpy.QtGui import QImage, QKeyEvent, QPainter

from sg_widgets_core.collection import EntitySourceOptions, create_entity_source
from sg_widgets_core.filter import condition
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_card import (
    CARD_TILE_WIDTH,
    card_tile_checkbox_rect,
    card_tile_size,
)
from sg_widgets_qt.widgets.entity_grid import ENTITY_GRID_GAP, EntityGrid
from sg_widgets_qt.widgets.state_line import StateLine

from .collections import FailingClient, mock_context, settle

#: What a tile reads on this page.
FIELDS = ("code", "image", "sg_status_list", "user")


@pytest.fixture
def context():
    return mock_context()


def _grid(context, qtbot, **options) -> EntityGrid:
    source = options.pop("source", None) or create_entity_source(
        EntitySourceOptions(
            client=context.client, entity_type="Version", fields=list(FIELDS), page_size=12
        )
    )
    grid = EntityGrid(source=source, context=context, **options)
    apply_theme(grid, theme_for("default"))
    qtbot.addWidget(grid)
    grid.resize(900, 520)
    grid.show()
    settle(grid, grid.control.binding)
    return grid


def _press(grid: EntityGrid, key) -> None:
    grid.on_key(QKeyEvent(QtCore.QEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier))


def test_a_tile_reads_the_row_through_the_shared_face(context, qtbot):
    grid = _grid(context, qtbot, secondary_field="user", show_code=True)
    settle(grid, grid.control.binding)
    row = grid.control.rows[0]
    tile = grid.tile_of(row)
    assert tile.name
    assert tile.entity_type == "Version"
    assert tile.status_code
    # A Version whose media is ready is the one tile that carries the play mark.
    assert tile.playable is True
    assert grid.model.rowCount() == len(grid.control.rows)
    # The grid lays fixed widths out, and the gap is the density's.
    assert grid.view.gridSize().width() == CARD_TILE_WIDTH["md"] + ENTITY_GRID_GAP["default"]
    assert grid.view.gridSize().height() == card_tile_size("md").height() + ENTITY_GRID_GAP["default"]


def test_the_size_moves_the_tile_and_the_column_it_sits_in(context, qtbot):
    grid = _grid(context, qtbot)
    for step in ("sm", "md", "lg"):
        grid.set_size(step)
        assert grid.size == step
        assert grid.view.gridSize().width() == CARD_TILE_WIDTH[step] + ENTITY_GRID_GAP["default"]
    grid.set_density("compact")
    assert grid.view.gridSize().width() == CARD_TILE_WIDTH["lg"] + ENTITY_GRID_GAP["compact"]


def test_the_arrows_walk_the_tiles_and_space_takes_one(context, qtbot):
    grid = _grid(context, qtbot, selectable=True)
    settle(grid, grid.control.binding)
    grid.view.setFocus()
    _press(grid, Qt.Key.Key_Right)
    assert grid.control.cursor == 1
    _press(grid, Qt.Key.Key_Left)
    assert grid.control.cursor == 0
    across = grid.view.columns_across()
    _press(grid, Qt.Key.Key_Down)
    assert grid.control.cursor == across
    _press(grid, Qt.Key.Key_End)
    assert grid.control.cursor == len(grid.control.rows) - 1
    _press(grid, Qt.Key.Key_Home)
    assert grid.control.cursor == 0

    _press(grid, Qt.Key.Key_Space)
    assert len(grid.selection) == 1
    opened: list = []
    grid.selected.connect(opened.append)
    _press(grid, Qt.Key.Key_Return)
    assert len(opened) == 1


def test_a_held_back_tile_refuses_the_cursor_and_the_selection(context, qtbot):
    grid = _grid(context, qtbot, selectable=True)
    held = grid.control.rows[0].id
    grid.set_is_row_disabled(lambda row: row.id == held)
    grid.view.setFocus()
    # The cursor lands on the first tile it may land on, which is the second.
    assert grid.control.active == 1
    grid.control.toggle(grid.control.rows[0])
    assert grid.selection == []


def test_the_scroller_asks_for_the_next_page_and_the_footer_counts_what_is_loaded(context, qtbot):
    grid = _grid(context, qtbot, paging="scroll")
    assert grid.control.bottom() == "sentinel"
    assert grid.control.pager.loaded_label == "12 loaded"
    grid.control.on_last_visible(len(grid.control.rows) - 1)
    settle(grid, grid.control.binding)
    assert len(grid.control.rows) == 24
    assert grid.control.pager.loaded_label == "24 loaded"


def test_the_empty_and_the_error_states_replace_the_tiles(context, qtbot):
    empty = create_entity_source(
        EntitySourceOptions(
            client=context.client,
            entity_type="Version",
            fields=list(FIELDS),
            filters=condition("code", "is", "no such version"),
            page_size=12,
        )
    )
    grid = _grid(context, qtbot, source=empty, empty_label="Nothing to review")
    settle(grid, grid.control.binding)
    assert grid.control.view(len(grid.control.rows)) == "empty"
    line = grid.findChild(StateLine, "entity-grid-state")
    assert line is not None and line.label == "Nothing to review"

    failing = FailingClient(context.client, fail_search=True)
    broken = create_entity_source(
        EntitySourceOptions(
            client=failing, entity_type="Version", fields=list(FIELDS), page_size=12
        )
    )
    failed = _grid(context, qtbot, source=broken)
    settle(failed, failed.control.binding)
    assert failed.control.view(len(failed.control.rows)) == "error"
    said = failed.findChild(StateLine, "entity-grid-state")
    assert said is not None and said.state == "error" and "503" in said.label


def _tile_image(grid: EntityGrid, **overrides) -> QImage:
    """One tile drawn on its own, so a corner can be read pixel by pixel."""
    from sg_widgets_qt.widgets.entity_card import CardTileOptions, paint_card_tile

    row = grid.control.rows[0]
    size = card_tile_size(grid.size)
    image = QImage(size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    options = CardTileOptions(
        theme=theme_for("default"),
        size=grid.size,
        statuses=grid.statuses,
        selectable=True,
        **overrides,
    )
    paint_card_tile(painter, QtCore.QRect(QtCore.QPoint(0, 0), size), grid.tile_of(row), options)
    painter.end()
    return image


def test_the_tile_box_waits_for_the_pointer_and_stays_up_once_the_tile_is_taken(context, qtbot):
    # `opacity-0 group-hover/tile:opacity-100 …`, with `selected` forcing it on.
    grid = _grid(context, qtbot, selectable=True)
    box = card_tile_checkbox_rect(
        QtCore.QRect(QtCore.QPoint(0, 0), card_tile_size(grid.size))
    ).adjusted(2, 2, -2, -2)
    at_rest = _tile_image(grid).copy(box)
    assert _tile_image(grid, hovered=True).copy(box) != at_rest
    assert _tile_image(grid, selected=True).copy(box) != at_rest


def test_the_tile_corner_carries_the_glyph_alone(context, qtbot):
    # `StatusBadge variant="icon"`: the pill holds the glyph and no name.
    from sg_widgets_qt.widgets.field_value import FieldValueOptions, field_value_size_hint

    grid = _grid(context, qtbot)
    grid.set_statuses({record.code: record for record in context.client.statuses()})
    code = grid.tile_of(grid.control.rows[0]).status_code
    shared = {
        "theme": theme_for("default"),
        "statuses": grid.statuses,
        "site_url": grid.site_url,
        "density": "compact",
    }
    named = field_value_size_hint(code, "status_list", FieldValueOptions(**shared))
    alone = field_value_size_hint(
        code, "status_list", FieldValueOptions(status_variant="icon", **shared)
    )
    assert 0 < alone.width() < named.width()


def test_one_press_opens_a_tile_and_the_box_keeps_its_own(context, qtbot):
    # The docs page promises `selected` "by click or by Enter".
    grid = _grid(context, qtbot, selectable=True)
    opened: list = []
    grid.selected.connect(opened.append)
    index = grid.model.index(1, 0)
    middle = grid.view.visualRect(index).center()
    grid.on_tile_pressed(index, middle)
    assert [row.id for row in opened] == [grid.control.rows[1].id]
    # A press on the box takes the tile instead, and opens nothing.
    box = card_tile_checkbox_rect(grid.view.visualRect(index)).center()
    grid.on_tile_pressed(index, box)
    assert len(opened) == 1
    assert [ref.id for ref in grid.selection] == [grid.control.rows[1].id]


def test_the_cursor_survives_the_page_the_scroller_appended(context, qtbot):
    """A page reset the model and took the current index with it, so the ring went out.

    End puts the cursor on the last loaded tile, which is also what asks for the next page in
    `scroll`: the cursor the reader left must still be there once the tiles arrive.
    """
    grid = _grid(context, qtbot, paging="scroll")
    grid.view.setFocus(Qt.FocusReason.TabFocusReason)
    grid.view.setCurrentIndex(grid.model.index(0, 0))
    held = len(grid.control.rows)

    grid.view.keyPressEvent(
        QKeyEvent(QtCore.QEvent.Type.KeyPress, int(Qt.Key.Key_End), Qt.KeyboardModifier.NoModifier)
    )
    settle(grid, grid.control.binding)

    assert len(grid.control.rows) > held, "the end of the loaded tiles asked for a page"
    assert grid.view.currentIndex().isValid()
    assert grid.view.currentIndex().row() == held - 1


def test_a_re_read_stands_behind_tiles_that_keep_the_grids_height(qtbot):
    """A sort re-reads the rows; the tiles that stand in fill the rows the tiles stood in.

    Upstream draws eight tiles on any read; here a first read draws those eight and a re-read
    draws as many as filled the tiles' rows, so the page under the grid does not jump.
    """
    from qtpy.QtWidgets import QWidget

    from sg_widgets_core.collection import SortSpec

    slow = mock_context(latency_ms=400)
    source = create_entity_source(
        EntitySourceOptions(
            client=slow.client, entity_type="Version", fields=list(FIELDS), mode="pages", page_size=12
        )
    )
    grid = _grid(slow, qtbot, source=source)
    before = grid.height()
    rows_height = grid.view.height()
    grid.control.apply_sort([SortSpec(path="code", descending=True)])
    qtbot.wait(40)
    assert grid.control.snapshot().status == "loading"
    skeleton = grid.findChild(QWidget, "entity-grid-loading")
    assert skeleton.isVisible() and not grid.view.isVisible()
    # Two rows of three at this width and height: the box the tiles filled, not a cold read's eight.
    assert skeleton.tiles == 6
    assert abs(skeleton.height() - rows_height) <= 40
    assert abs(grid.height() - before) <= 40
    settle(grid, grid.control.binding)
    assert grid.view.isVisible() and abs(grid.height() - before) <= 2
