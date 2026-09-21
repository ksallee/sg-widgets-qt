"""The matched label: the runs core answers, the weight they take, and the elision.

Every test runs on both bindings, offscreen, and paints into a pixmap rather than a window.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_core.search import match_runs
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.match_text import MATCH_TEXT_SIZE, MatchText


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 300)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget, width: int = 400):
    widget.setParent(parent)
    widget.resize(width, widget.sizeHint().height())
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


def ink(shot: QtGui.QImage) -> int:
    """How many pixels the text put down, which is every pixel darker than the ground."""
    return sum(
        1
        for y in range(shot.height())
        for x in range(shot.width())
        if shot.pixelColor(x, y).lightness() < 128
    )


def test_constructs_and_paints(root):
    label = place(root, MatchText(text="Ada Lovelace", query="ad ve"))
    assert label.objectName() == "match-text"
    assert counts(image(label))


def test_the_runs_are_core_s(root):
    label = MatchText(text="Ada Lovelace", query="ad ve")
    assert [(run.text, run.match) for run in label.runs] == [
        (run.text, run.match) for run in match_runs("Ada Lovelace", "ad ve")
    ]
    assert [(run.text, run.match) for run in label.runs] == [
        ("Ad", True),
        ("a Lo", False),
        ("ve", True),
        ("lace", False),
    ]


def test_an_empty_query_marks_nothing(root):
    label = MatchText(text="Ada Lovelace", query="")
    assert [(run.text, run.match) for run in label.runs] == [("Ada Lovelace", False)]


def test_the_runs_rebuild_the_label_exactly(root):
    text = "Blue Moon Rising / Sequence sq020 / sh020_0050"
    label = MatchText(text=text, query="mo 020")
    assert "".join(run.text for run in label.runs) == text


def test_a_match_is_drawn_heavier(root):
    # The weight the painter is given, not the pixels that come back: a family whose DemiBold
    # face the platform cannot supply draws the two runs at one advance, and the label still
    # asks for the heavier face and never for a narrower box.
    plain = place(root, MatchText(text="Ada Lovelace", query=""))
    marked = place(root, MatchText(text="Ada Lovelace", query="ada lovelace"))
    quiet, heavy = marked.run_font(False), marked.run_font(True)
    assert heavy.weight() > quiet.weight()
    assert (heavy.family(), heavy.pixelSize()) == (quiet.family(), quiet.pixelSize())
    assert marked.sizeHint().width() >= plain.sizeHint().width()
    assert ink(image(marked)) >= ink(image(plain)) > 0


def test_a_match_is_weight_and_never_colour(root):
    theme = theme_for("default")
    marked = place(root, MatchText(text="Ada Lovelace", query="ada"))
    tally = counts(image(marked))
    assert theme.color("foreground").name() in tally
    assert theme.color("primary").name() not in tally
    assert theme.color("destructive").name() not in tally


def test_muted_draws_the_line_in_muted_foreground(root):
    theme = theme_for("default")
    label = place(root, MatchText(text="Waiting on Ada", query="ada", muted=True))
    assert theme.color("muted_foreground").name() in counts(image(label))


@pytest.mark.parametrize("step", sorted(MATCH_TEXT_SIZE))
def test_every_step_of_the_type_ladder(root, step):
    label = place(root, MatchText(text="Ada Lovelace", query="ad", size=step))
    assert label.size == step
    assert counts(image(label))


def test_a_label_that_does_not_fit_is_elided_and_carries_itself(root):
    text = "anna.van.der.meer@example.com and a great deal more besides"
    label = place(root, MatchText(text=text, query="meer"), width=80)
    image(label)
    assert label.toolTip() == text


def test_a_label_that_fits_carries_no_tooltip(root):
    label = place(root, MatchText(text="Ada Lovelace", query="ad"), width=400)
    image(label)
    assert label.toolTip() == ""


def test_setting_the_query_remarks_the_label(root):
    label = place(root, MatchText(text="Ada Lovelace", query=""))
    before = image(label)
    label.set_query("lovelace")
    QtWidgets.QApplication.processEvents()
    assert image(label) != before
    assert [run.match for run in label.runs] == [False, True]


def test_every_setter_repaints(root):
    label = place(root, MatchText(text="Ada Lovelace"))
    label.set_text("propCrate_model_v002")
    label.set_query("mo")
    label.set_size("lg")
    label.set_muted(True)
    QtWidgets.QApplication.processEvents()
    assert label.text == "propCrate_model_v002"
    assert label.query == "mo"
    assert label.size == "lg"
    assert label.muted is True
    assert counts(image(label))
