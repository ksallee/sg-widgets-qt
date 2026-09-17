"""The states of the search wave, one function each, for the shot matrix.

Every `tools/drives/<widget>-<state>.py` is a two-line file over one function here, and every
one of them has its twin under `tools/drives/upstream/<widget>-<state>.js`, which drives the
upstream page into the same state. A shot of each pair is what the QA pass reads.

`:hover` and keyboard focus are widget state here rather than CSS, so this file can reach them
where the upstream body cannot; the README under `upstream/` says so.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QApplication, QScrollArea

from sg_widgets_qt.primitives.roles import Roles

__all__ = [
    "context_selector_open",
    "context_selector_sizes",
    "global_search_error",
    "global_search_load_more",
    "global_search_loading",
    "global_search_no_match",
    "global_search_open_empty",
    "global_search_rows",
    "global_search_sizes",
    "global_search_trigger_focus",
    "global_search_trigger_hover",
    "hierarchical_search_error",
    "hierarchical_search_no_match",
    "hierarchical_search_rows",
    "hierarchical_search_walked",
    "search_control_highlighted",
    "search_control_loading",
    "search_control_no_match",
    "search_control_rows",
]

#: The query the crew list answers rows for, and one it answers nothing for.
CREW_QUERY = "an"
SITE_QUERY = "sh"
TREE_QUERY = "sh010_0010 comp"
NO_MATCH = "zzzqqq"


def press(widget, key: int) -> None:
    """One key, delivered to the widget itself, so a headless run needs no focus."""
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))


def settle(control, wait, ms: int = 12000) -> None:
    """Spin until the read in flight has answered or failed."""
    deadline = time.monotonic() + ms / 1000.0
    while control.loading and time.monotonic() < deadline:
        wait(25)


def popup_shot(widget, name: str, prefs=None) -> str:
    """Save a top-level surface to `shots/`, which `window.grab()` cannot reach.

    A dialog and a popover are windows of their own, so the page shot holds only the scrim
    under them. The drive grabs the surface itself and says where it put it.
    """
    from pathlib import Path

    dark = bool(getattr(prefs, "theme", "") == "dark")
    target = Path("shots") / f"{name}{'-dark' if dark else ''}-popup.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(target))
    return str(target)


def mock_of(client):
    """The mock under the cache and the counter, which is what arms a failure."""
    seen = client
    for _ in range(6):
        if hasattr(seen, "fail_next"):
            return seen
        seen = getattr(seen, "_client", None)
        if seen is None:
            return None
    return None


def _answered(control, wait, query: str, settle_ms: int = 12000) -> dict:
    """Put a query in the box and wait the read out."""
    control.input().setText(query)
    control.flush()
    settle(control, wait, settle_ms)
    wait(500)
    return {"verdict": "PASS", "view": control.view, "rows": control.model.rowCount()}


# --- search-control ------------------------------------------------------------------------


def search_control_loading(page, wait, find, prefs=None) -> dict:
    control = find("search-control-query")
    control.input().setText(CREW_QUERY)
    # The pause is 250ms and the demo's read waits 300ms, so the skeletons are up at 320ms.
    wait(320)
    return {"verdict": "PASS", "view": control.view}


def search_control_rows(page, wait, find, prefs=None) -> dict:
    return _answered(find("search-control-query"), wait, CREW_QUERY)


def search_control_no_match(page, wait, find, prefs=None) -> dict:
    return _answered(find("search-control-query"), wait, "zzzzz")


def search_control_highlighted(page, wait, find, prefs=None) -> dict:
    control = find("search-control-query")
    _answered(control, wait, CREW_QUERY)
    surface = control.list_surface()
    surface.set_highlight(0)
    press(control.input(), Qt.Key.Key_Down)
    wait(80)
    press(control.input(), Qt.Key.Key_Down)
    wait(300)
    return {"verdict": "PASS", "highlighted": surface.highlighted()}


# --- global-search -------------------------------------------------------------------------


def global_search_open_empty(page, wait, find, prefs=None) -> dict:
    palette = find("global-search-palette")
    palette.set_open(True)
    wait(600)
    dialog = palette.search_control().dialog()
    shot = popup_shot(dialog, "global-search-open-empty", prefs) if dialog is not None else ""
    return {"verdict": "PASS", "recents": len(palette.recents), "popup": shot}


def global_search_loading(page, wait, find, prefs=None) -> dict:
    control = find("global-search-inline").search_control()
    control.input().setText(SITE_QUERY)
    wait(280)
    return {"verdict": "PASS", "view": control.view}


def global_search_rows(page, wait, find, prefs=None) -> dict:
    return _answered(find("global-search-inline").search_control(), wait, SITE_QUERY)


def global_search_no_match(page, wait, find, prefs=None) -> dict:
    return _answered(find("global-search-inline").search_control(), wait, NO_MATCH)


def global_search_load_more(page, wait, find, prefs=None) -> dict:
    control = find("global-search-inline").search_control()
    _answered(control, wait, SITE_QUERY)
    first = len(control.items)
    control.load_more()
    settle(control, wait)
    wait(500)
    surface = control.list_surface()
    surface.scrollToBottom()
    wait(400)
    return {"verdict": "PASS", "first": first, "after": len(control.items)}


def global_search_error(page, wait, find, prefs=None) -> dict:
    """Upstream has no hook for this state; the mock here is armed to fail the next read."""
    control = find("global-search-inline").search_control()
    mock = mock_of(page.context.client)
    if mock is None:
        return {"verdict": "FAIL the demo client cannot be armed to fail"}
    mock.fail_next()
    answer = _answered(control, wait, "sh03")
    mock.fail_next(None)
    return answer


def global_search_sizes(page, wait, find, prefs=None) -> dict:
    last = find("global-search-lg")
    if last is not None:
        _scroll_to(last)
    wait(400)
    return {"verdict": "PASS", "triggers": len(find("global-search-trigger", all=True) or [])}


def global_search_trigger_hover(page, wait, find, prefs=None) -> dict:
    """Hover is widget state here, not a CSS class, so the shot can hold it."""
    trigger = find("global-search-palette").trigger()
    trigger.set_hovered(True)
    wait(400)
    return {"verdict": "PASS", "hovered": bool(trigger.hovered)}


def global_search_trigger_focus(page, wait, find, prefs=None) -> dict:
    trigger = find("global-search-palette").trigger()
    trigger.setFocus(Qt.FocusReason.TabFocusReason)
    wait(400)
    return {"verdict": "PASS", "focus": bool(getattr(trigger, "keyboard_focus", False))}


# --- hierarchical-search -------------------------------------------------------------------


def hierarchical_search_walked(page, wait, find, prefs=None) -> dict:
    tree = find("hierarchical-search")
    control = tree.search_control()
    settle(control, wait)
    wait(300)
    surface = control.list_surface()
    kinds = [
        str(control.model.data(control.model.index(i, 0), Roles.KIND) or "row")
        for i in range(control.model.rowCount())
    ]
    at = next((i for i, kind in enumerate(kinds) if kind == "row"), 0)
    # The last folder of the root, so the level below it has rows of its own.
    surface.set_highlight(control.model.rowCount() - 1)
    press(control.input(), Qt.Key.Key_Right)
    settle(control, wait)
    wait(500)
    return {"verdict": "PASS", "level": tree.level_path, "rows": control.model.rowCount(), "at": at}


def hierarchical_search_rows(page, wait, find, prefs=None) -> dict:
    return _answered(find("hierarchical-search").search_control(), wait, TREE_QUERY)


def hierarchical_search_no_match(page, wait, find, prefs=None) -> dict:
    return _answered(find("hierarchical-search").search_control(), wait, NO_MATCH)


def hierarchical_search_error(page, wait, find, prefs=None) -> dict:
    """Upstream has no hook for this state; the mock here is armed to fail the next read."""
    control = find("hierarchical-search").search_control()
    mock = mock_of(page.context.client)
    if mock is None:
        return {"verdict": "FAIL the demo client cannot be armed to fail"}
    mock.fail_next()
    answer = _answered(control, wait, "sh020")
    mock.fail_next(None)
    return answer


# --- context-selector ----------------------------------------------------------------------


def context_selector_open(page, wait, find, prefs=None) -> dict:
    selector = find("context-selector")
    selector.set_open(True)
    settle(selector.tasks_control(), wait)
    wait(700)
    shot = popup_shot(selector.popover(), "context-selector-open", prefs)
    return {"verdict": "PASS", "tasks": len(selector.tasks_control().items), "popup": shot}


def context_selector_sizes(page, wait, find, prefs=None) -> dict:
    last = find("context-selector-lg")
    if last is not None:
        _scroll_to(last)
    wait(400)
    return {"verdict": "PASS", "triggers": len(find("context-selector-trigger", all=True) or [])}


def _scroll_to(widget) -> None:
    """Put a widget of the page in view, which is what `scrollIntoView` does upstream."""
    node = widget
    while node is not None and not isinstance(node, QScrollArea):
        node = node.parentWidget()
    if isinstance(node, QScrollArea):
        node.ensureWidgetVisible(widget, 0, 40)
