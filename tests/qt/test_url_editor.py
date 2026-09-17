"""The url editor: the two halves of a web link, and the local path it will not edit."""
from __future__ import annotations

import pytest

from sg_widgets_core.edit import UrlWriteValue
from sg_widgets_core.render import UrlValue
from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.widgets.url_editor import LOCAL_NOTE, UrlEditor

from .editors import escape, place, press_enter, themed_root, type_into

WEB = UrlValue(url="https://example.com/plate.mov", name="plate.mov", link_type="web")
LOCAL = UrlValue(
    link_type="local", name="plate.exr", local_path_mac="/Volumes/shows/sh010/plate.exr"
)


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_shows_both_halves(root):
    editor = place(root, UrlEditor(value=WEB))
    assert editor.objectName() == "url-editor"
    assert editor.url_input.text() == "https://example.com/plate.mov"
    assert editor.name_input.text() == "plate.mov"
    assert not editor.grab().isNull()


def test_a_commit_carries_the_write_shape(root):
    editor = place(root, UrlEditor(value=WEB))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.url_input, "https://example.com/final.mov")
    press_enter(editor.url_input)
    assert isinstance(seen[0], UrlWriteValue)
    assert seen[0].url == "https://example.com/final.mov"
    assert seen[0].name == "plate.mov"


def test_an_address_with_no_name_commits_the_address_alone(root):
    editor = place(root, UrlEditor(value=None))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.url_input, "https://example.com/plate.mov")
    press_enter(editor.url_input)
    assert seen[0].url == "https://example.com/plate.mov"
    assert seen[0].name is None


def test_a_raw_space_in_the_address_is_refused(root):
    editor = place(root, UrlEditor(value=WEB))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.url_input, "https://example.com/a b.mov")
    press_enter(editor.url_input)
    assert seen == []
    assert editor.message == "No spaces in a link. Percent-encode them."
    assert editor.reads_invalid is True


def test_a_name_with_no_address_is_refused(root):
    editor = place(root, UrlEditor(value=None))
    type_into(editor.name_input, "plate.mov")
    press_enter(editor.name_input)
    assert editor.message == "A name needs a link."


def test_both_halves_empty_clear_the_field(root):
    editor = place(root, UrlEditor(value=WEB))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.url_input, "")
    type_into(editor.name_input, "")
    press_enter(editor.name_input)
    assert seen == [None]


def test_escape_restores_both_halves(root):
    editor = place(root, UrlEditor(value=WEB))
    type_into(editor.url_input, "https://example.com/other.mov")
    escape(editor.url_input)
    assert editor.url_input.text() == "https://example.com/plate.mov"
    assert editor.name_input.text() == "plate.mov"


def test_a_local_path_says_so_and_takes_no_input(root):
    editor = place(root, UrlEditor(value=LOCAL))
    assert editor.local_only is True
    assert editor._note.text == LOCAL_NOTE
    assert editor.url_input.isEnabled() is False
    assert editor.name_input.isEnabled() is False


def test_readonly_drops_the_affordances_and_disabled_is_inert(root):
    readonly = place(root, UrlEditor(value=WEB, readonly=True))
    disabled = place(root, UrlEditor(value=WEB, disabled=True))
    assert readonly.url_input.isReadOnly() is True
    assert readonly.name_input.isReadOnly() is True
    assert disabled.isEnabled() is False
    type_into(readonly.url_input, "https://example.com/typed.mov")
    press_enter(readonly.url_input)
    assert readonly.url_input.text() == WEB.url
    assert readonly.value.url == WEB.url


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_both_inputs_stand_on_every_rung_of_the_ladder(root, size):
    editor = place(root, UrlEditor(value=WEB, size=size))
    assert editor.url_input.sizeHint().height() == CONTROL_HEIGHT[size]
    assert editor.name_input.sizeHint().height() == CONTROL_HEIGHT[size]
