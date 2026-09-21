"""The leaf primitives: the ladders, the painting, the signals, the states and the focus ring.

Every test runs on both bindings, offscreen, and paints into a pixmap rather than a window.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.primitives import (
    BUTTON_SIZES,
    CHIP_HEIGHT,
    CONTROL_HEIGHT,
    DURATION,
    Badge,
    Button,
    Checkbox,
    Chip,
    Input,
    Kbd,
    Label,
    Separator,
    Skeleton,
    Switch,
    Textarea,
    Toggle,
    ToggleGroup,
)
from sg_widgets_qt.primitives.input import TEXTAREA_MIN_HEIGHT
from sg_widgets_qt.showcase.demos._leaf import build
from sg_widgets_qt.theme import apply_theme, theme_for

BUTTON_VARIANTS = ("default", "outline", "secondary", "ghost", "destructive", "link")


@pytest.fixture
def root(qtbot):
    """A shown root wearing the default light theme, which every leaf reads through."""
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """Put a leaf on a root at its own size hint and show it."""
    widget.setParent(parent)
    widget.resize(widget.sizeHint())
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def image(widget: QtWidgets.QWidget) -> QtGui.QImage:
    pixmap = widget.grab()
    assert not pixmap.isNull()
    return pixmap.toImage()


def centre_colour(widget: QtWidgets.QWidget) -> QtGui.QColor:
    """The fill at mid-height, 5px in from the left edge: inside the surface, never on a glyph."""
    shot = image(widget)
    return shot.pixelColor(5, shot.height() // 2)


def counts(shot: QtGui.QImage) -> dict:
    tally: dict = {}
    for y in range(shot.height()):
        for x in range(shot.width()):
            name = shot.pixelColor(x, y).name()
            tally[name] = tally.get(name, 0) + 1
    return tally


# --- construction and the ladders --------------------------------------------------------------


@pytest.mark.parametrize("variant", BUTTON_VARIANTS)
def test_every_button_variant_constructs_and_paints(root, variant):
    button = place(root, Button("Save", icon="plus", variant=variant))
    assert not button.grab().isNull()


@pytest.mark.parametrize("size", list(BUTTON_SIZES))
def test_button_takes_its_step_of_the_ladder(root, size):
    button = place(root, Button("Save", size=size))
    assert button.sizeHint().height() == BUTTON_SIZES[size].height


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_input_takes_the_control_ladder(root, size):
    field = place(root, Input(placeholder="Search", size=size))
    assert field.sizeHint().height() == CONTROL_HEIGHT[size]
    assert not field.grab().isNull()


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_toggle_takes_the_control_ladder(root, size):
    toggle = place(root, Toggle("Bold", icon="type", size=size))
    assert toggle.sizeHint().height() == CONTROL_HEIGHT[size]


@pytest.mark.parametrize("size", list(CHIP_HEIGHT))
def test_badge_and_chip_take_the_chip_ladder(root, size):
    badge = place(root, Badge("Ready", size=size, removable=True))
    chip = place(root, Chip("Ada Lovelace", size=size, icon="user"))
    assert badge.sizeHint().height() == CHIP_HEIGHT[size]
    assert chip.sizeHint().height() == CHIP_HEIGHT[size]
    assert not badge.grab().isNull()
    assert not chip.grab().isNull()


def test_textarea_keeps_its_minimum_height(root):
    area = place(root, Textarea(placeholder="A note"))
    assert area.sizeHint().height() == TEXTAREA_MIN_HEIGHT
    assert not area.grab().isNull()


def test_input_and_textarea_expand_horizontally(root):
    policy = QtWidgets.QSizePolicy.Policy
    assert Input().sizePolicy().horizontalPolicy() == policy.Expanding
    assert Textarea().sizePolicy().horizontalPolicy() == policy.Expanding
    assert Button("Save").sizePolicy().horizontalPolicy() == policy.Fixed


def test_the_quiet_leaves_construct_and_paint(root):
    for widget in (Label("Status"), Kbd("Ctrl"), Separator(), Separator("vertical")):
        placed = place(root, widget)
        placed.resize(max(1, placed.sizeHint().width()), max(1, placed.sizeHint().height()))
        assert not placed.grab().isNull()


def test_every_leaf_of_the_demo_paints(root):
    page = build(root)
    page.resize(1100, page.sizeHint().height())
    page.show()
    QtWidgets.QApplication.processEvents()
    assert not page.grab().isNull()


# --- the painted colours -----------------------------------------------------------------------


def test_a_filled_button_paints_primary_at_its_centre(root):
    button = place(root, Button("Save"))
    assert centre_colour(button).name() == theme_for("default").primary


def test_a_checked_checkbox_is_filled_primary(root, qtbot):
    box = place(root, Checkbox())
    box.set_checked(True)
    qtbot.wait(DURATION["hover"] * 2)
    tally = counts(image(box))
    primary = theme_for("default").primary
    # The box is 16 square with a tick through it, so the fill is the colour most of it wears.
    assert tally.get(primary, 0) > 40


def test_an_unchecked_checkbox_is_not_filled(root):
    box = place(root, Checkbox())
    tally = counts(image(box))
    assert tally.get(theme_for("default").primary, 0) == 0


# --- signals -------------------------------------------------------------------------------------


def test_a_button_fires_on_click_and_on_space(root, qtbot):
    button = place(root, Button("Save"))
    with qtbot.waitSignal(button.clicked, timeout=1000):
        qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(button.clicked, timeout=1000):
        qtbot.keyClick(button, QtCore.Qt.Key.Key_Space)
    with qtbot.waitSignal(button.clicked, timeout=1000):
        qtbot.keyClick(button, QtCore.Qt.Key.Key_Return)


def test_a_disabled_button_ignores_a_click(root, qtbot):
    button = place(root, Button("Save"))
    button.setEnabled(False)
    fired = []
    button.clicked.connect(lambda: fired.append(True))
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    qtbot.keyClick(button, QtCore.Qt.Key.Key_Space)
    assert fired == []


def test_a_checkbox_toggles_on_click_and_on_space(root, qtbot):
    box = place(root, Checkbox("Only mine"))
    with qtbot.waitSignal(box.toggled, timeout=1000):
        qtbot.mouseClick(box, QtCore.Qt.MouseButton.LeftButton)
    assert box.checked is True
    with qtbot.waitSignal(box.toggled, timeout=1000):
        qtbot.keyClick(box, QtCore.Qt.Key.Key_Space)
    assert box.checked is False


def test_a_disabled_checkbox_ignores_a_click(root, qtbot):
    box = place(root, Checkbox("Only mine"))
    box.setEnabled(False)
    qtbot.mouseClick(box, QtCore.Qt.MouseButton.LeftButton)
    assert box.checked is False


def test_a_tri_state_checkbox_walks_off_on_partial(root):
    box = place(root, Checkbox("Some", tri_state=True))
    states = []
    box.state_changed.connect(states.append)
    box.toggle()
    box.toggle()
    box.toggle()
    assert states == [2, 1, 0]


def test_a_switch_toggles_on_space(root, qtbot):
    switch = place(root, Switch())
    with qtbot.waitSignal(switch.toggled, timeout=1000):
        qtbot.keyClick(switch, QtCore.Qt.Key.Key_Space)
    assert switch.checked is True


def test_a_toggle_toggles_on_space(root, qtbot):
    toggle = place(root, Toggle("Bold", icon="type"))
    with qtbot.waitSignal(toggle.toggled, timeout=1000):
        qtbot.keyClick(toggle, QtCore.Qt.Key.Key_Space)
    assert toggle.checked is True


def test_a_badge_removes_on_space_and_on_its_cross(root, qtbot):
    badge = place(root, Badge("Ready", size="md", removable=True))
    with qtbot.waitSignal(badge.removed, timeout=1000):
        qtbot.keyClick(badge, QtCore.Qt.Key.Key_Space)
    cross = badge.rect().center()
    cross.setX(badge.width() - 10)
    with qtbot.waitSignal(badge.removed, timeout=1000):
        qtbot.mouseClick(badge, QtCore.Qt.MouseButton.LeftButton, pos=cross)


def test_a_toggle_group_holds_one_value_and_walks_on_the_arrows(root, qtbot):
    group = place(root, ToggleGroup([("list", "List"), ("grid", "Grid")], value="list"))
    assert group.value == "list"
    with qtbot.waitSignal(group.value_changed, timeout=1000):
        qtbot.keyClick(group.toggles()[0], QtCore.Qt.Key.Key_Right)
    assert group.value == "grid"
    qtbot.keyClick(group.toggles()[1], QtCore.Qt.Key.Key_Left)
    assert group.value == "list"


def test_a_toggle_group_can_hold_several(root):
    group = place(root, ToggleGroup(["a", "b", "c"], value=["a"], multiple=True))
    group.toggles()[2].toggle()
    assert group.value == ["a", "c"]


# --- states ---------------------------------------------------------------------------------------


def test_the_focus_ring_is_painted_on_tab_focus_and_not_on_a_click(root):
    button = place(root, Button("Save"))
    button.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    QtWidgets.QApplication.processEvents()
    clicked = image(button)
    assert button.keyboard_focus is False

    button.clearFocus()
    button.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    QtWidgets.QApplication.processEvents()
    tabbed = image(button)
    assert button.keyboard_focus is True

    assert tabbed != clicked
    assert counts(tabbed).get(theme_for("default").ring, 0) > 0
    assert counts(clicked).get(theme_for("default").ring, 0) == 0


def test_a_disabled_leaf_paints_at_half_opacity(root):
    button = place(root, Button("Save"))
    lit = centre_colour(button)
    button.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    assert centre_colour(button) != lit


def test_an_invalid_input_paints_the_destructive_border(root):
    field = place(root, Input(placeholder="Needs a value"))
    field.resize(200, field.sizeHint().height())
    plain = counts(image(field))
    field.set_invalid(True)
    QtWidgets.QApplication.processEvents()
    invalid = counts(image(field))
    destructive = theme_for("default").destructive
    assert invalid.get(destructive, 0) > plain.get(destructive, 0)


def test_a_readonly_input_keeps_its_contrast(root):
    field = place(root, Input(readonly=True))
    assert field.isReadOnly() is True
    assert not field.grab().isNull()


def test_an_elided_label_carries_the_full_text_as_its_tooltip(root):
    label = place(root, Label("A very long label that will not fit in forty pixels"))
    label.resize(40, label.sizeHint().height())
    label.grab()
    assert label.toolTip() == "A very long label that will not fit in forty pixels"
    label.resize(label.sizeHint())
    label.grab()
    assert label.toolTip() == ""


def test_a_skeleton_shimmers_and_stops_under_reduced_motion(qtbot):
    lit = QtWidgets.QWidget()
    apply_theme(lit, theme_for("default"))
    qtbot.addWidget(lit)
    moving = Skeleton(width=120, height=14, parent=lit)
    assert moving.running is True
    moving.set_animated(False)
    assert moving.running is False

    still = QtWidgets.QWidget()
    apply_theme(still, theme_for("default", reduced_motion=True))
    qtbot.addWidget(still)
    quiet = Skeleton(width=120, height=14, parent=still)
    assert quiet.running is False
    quiet.set_animated(True)
    assert quiet.running is False
    assert not quiet.grab().isNull()


def test_a_busy_button_draws_a_spinner_in_place_of_its_glyph(root):
    button = place(root, Button("Saving", icon="check"))
    quiet = image(button)
    button.set_busy(True)
    QtWidgets.QApplication.processEvents()
    assert button.busy is True
    assert image(button) != quiet


def test_an_expanded_button_keeps_its_hover_background(root):
    button = place(root, Button("Filters", variant="ghost"))
    plain = image(button)
    button.set_expanded(True)
    QtWidgets.QApplication.processEvents()
    assert image(button) != plain


def test_an_inert_field_wears_the_input_wash(root):
    # `disabled:bg-input/50` of `input.tsx`: an inert field is not a plain box.
    live = place(root, Input(placeholder="https://example.com/plate.mov"))
    inert = place(root, Input(placeholder="https://example.com/plate.mov"))
    inert.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    middle = (live.width() // 2, live.height() // 2)
    assert inert.grab().toImage().pixelColor(*middle) != live.grab().toImage().pixelColor(*middle)


def _ink_of(page: QtGui.QImage, field: QtWidgets.QWidget, background: str) -> str:
    """The colour a field's text is drawn in, read off a shot of the page it stands on.

    The run of pixels the glyphs cover is a minority of the band, so the reading is the commonest
    colour in it that is neither the page nor the field's own surface.
    """
    import collections

    box = field.geometry()
    counted: collections.Counter = collections.Counter()
    for y in range(box.top() + 6, box.top() + 26):
        for x in range(box.left() + 14, box.left() + 130):
            counted[page.pixelColor(x, y).name()] += 1
    surface = counted.most_common(1)[0][0]
    return next(name for name, _ in counted.most_common() if name not in (background, surface))


def test_the_ink_qt_draws_itself_is_the_theme_s_on_both_bindings(qtbot):
    # No stylesheet names the ink any more: a stylesheet beats every palette under it, and Qt 5
    # then derives the placeholder from its `color`, which put the typed ink under the
    # placeholder on that binding. `input.tsx` has `placeholder:text-muted-foreground` and
    # `disabled:opacity-50`, and both are colours in the palette here.
    theme = theme_for("default")
    root = QtWidgets.QWidget()
    apply_theme(root, theme)
    root.setAutoFillBackground(True)
    palette = root.palette()
    palette.setColor(root.backgroundRole(), theme.color("background"))
    root.setPalette(palette)
    qtbot.addWidget(root)

    column = QtWidgets.QVBoxLayout(root)
    column.setSpacing(8)
    empty = Input(placeholder="Placeholder")
    typed = Input()
    inert = Input()
    inert_empty = Input(placeholder="Placeholder")
    area = Textarea()
    for field in (empty, typed, inert, inert_empty, area):
        column.addWidget(field)
    typed.setText("Value")
    inert.setText("Value")
    inert.setEnabled(False)
    inert_empty.setEnabled(False)
    area.setPlainText("Value")
    root.resize(300, 340)
    root.show()
    QtWidgets.QApplication.processEvents()

    page = root.grab().toImage()
    background = theme.color("background").name()
    assert _ink_of(page, empty, background) == theme.color("muted_foreground").name()
    assert _ink_of(page, typed, background) == theme.color("foreground").name()
    assert _ink_of(page, area, background) == theme.color("foreground").name()
    # The inert pair is the same two inks at half strength over the inert wash, so what is read
    # is that they are neither the full ink nor the page.
    faded = _ink_of(page, inert, background)
    faded_empty = _ink_of(page, inert_empty, background)
    assert faded not in (theme.color("foreground").name(), background)
    assert faded_empty not in (theme.color("muted_foreground").name(), background)
    assert QtGui.QColor(faded).lightness() > QtGui.QColor(theme.color("foreground")).lightness()
    assert (
        QtGui.QColor(faded_empty).lightness()
        > QtGui.QColor(theme.color("muted_foreground")).lightness()
    )


def test_the_switch_thumb_is_the_glyph_step(root):
    # `size-4` of the thumb in `switch.tsx`, inside the 32 by 18 track.
    from sg_widgets_qt.primitives.checkbox import SWITCH_HEIGHT, SWITCH_THUMB, SWITCH_WIDTH

    assert (SWITCH_WIDTH, SWITCH_HEIGHT, SWITCH_THUMB) == (32, 18, 16)
    switch = place(root, Switch(True))
    assert not switch.grab().isNull()


def test_textarea_grows_with_its_text_and_holds_a_dragged_height(root):
    """`field-sizing-content` and the browser's corner handle, on one box.

    The box asks for the height of its lines above the 64px floor, and a drag on its corner
    sets the height by hand and holds it, as a browser's handle does, until it is let go.
    """
    from qtpy.QtCore import QEvent, QPoint, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import QApplication

    area = place(root, Textarea(placeholder="A note"))
    assert area.sizeHint().height() == 64
    area.setPlainText("\n".join(f"line {i}" for i in range(12)))
    grown = area.sizeHint().height()
    assert grown > 64 and grown == area.content_height()
    # A drag on the corner: forty pixels down makes the box forty pixels taller.
    area.resize(area.width(), grown)
    grip = area._grip_rect().center()
    QTest.mousePress(area.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip)
    # Qt 5's QTest.mouseMove moves the cursor rather than sending an event, so the drag is
    # posted as the events a pointer sends.
    for kind, held in ((QEvent.Type.MouseMove, Qt.MouseButton.LeftButton), (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
        point = grip + QPoint(0, 40)
        QApplication.sendEvent(
            area.viewport(),
            QMouseEvent(kind, QPointF(point), QPointF(area.viewport().mapToGlobal(point)), Qt.MouseButton.LeftButton, held, Qt.KeyboardModifier.NoModifier),
        )
    assert area.dragged_height == grown + 40
    assert area.sizeHint().height() == grown + 40
    # A hand-set height holds while text comes and goes.
    area.setPlainText("one line")
    assert area.sizeHint().height() == grown + 40
    area.set_dragged_height(None)
    assert area.content_height() < 64 < grown
    assert area.sizeHint().height() == 64, "back on the floor once the hand-set height is let go"


def test_the_textarea_scrolls_on_the_overlay_bars(root):
    """Rule 0: every scroll area here wears the thin overlay bars, the textarea included."""
    from sg_widgets_qt.primitives.scrollbar import overlay_scrollbars_of

    area = place(root, Textarea(placeholder="A note"))
    bars = overlay_scrollbars_of(area)
    assert bars is not None, "the textarea is drawn by the host's own scrollbar"
    assert area.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    # A box held under its text is scrollable, and the overlay bar is what stands for it.
    area.setPlainText("\n".join(f"line {i}" for i in range(40)))
    area.set_dragged_height(80)
    area.resize(area.width(), 80)
    QtWidgets.QApplication.processEvents()
    assert bars[0].scrollable()
    assert bars[0].isVisible()
