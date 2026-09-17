"""Design rule 7, every clause, on every picker of the page it is run on.

The port of `~/dev/sg-widgets/tools/drives/picker-contract.js`, with the upstream drives the
picker base carries beside it: `picker-mandatory-clear.js`, `picker-pick-releases-chip.js`,
`picker-arrow-scroll.js`, `multi-picker-fit.js`, `picker-escape.js` and `picker-backspace.js`.

    .venv/bin/python tools/qa.py --page picker-control --drive tools/drives/picker-contract.py
    .venv/bin/python tools/qa.py --page entity-picker --drive tools/drives/picker-contract.py
    .venv/bin/python tools/qa.py --page entity-multi-picker --drive tools/drives/picker-contract.py
    .venv/bin/python tools/qa.py --page entity-picker --drive tools/drives/picker-contract.py --qt5

The ten clauses come from `tests/qt/test_picker_contract.check_contract`, so the drive and the
test walk the same code against the real demos rather than a picker built for the check. A demo
the page draws disabled or readonly takes the state clauses alone, as upstream's walk does.

Beside them the page's own behaviours, each one an upstream drive:

    mandatory-clear    a control the caller refuses a clear keeps its value and its chevron
    pick-releases-chip a pick made with a chip armed frees it and Backspace reaches the new one
    arrow-scroll       the highlight stays in the list across a load-more page and back
    multi-picker-fit   a narrow summary control fits whole chips, counts the rest, opens on `+n`
    hydrate            a bare `{type, id}` resolves to a name
    exclude            rows the caller excludes are not offered
    debounce           two keystrokes leave one read behind
    stale              an answer to a query the typist replaced is dropped
    error              a read armed to fail draws the error line
    escape             Escape closes the list and clears the query
    tab                Tab walks the caret, the clear control and the chevron, then leaves
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sg_widgets_qt.widgets.picker_control import PickerControl  # noqa: E402
from tests.qt.test_picker_contract import (  # noqa: E402
    CLAUSES,
    PickerShape,
    check_contract,
    press_control,
)

#: The mock's latency plus the debounce, with room for the hop back onto the GUI thread.
SETTLE_MS = 1200


class _Bot:
    """What `check_contract` asks of `qtbot`: a wait that turns the driver's own loop."""

    def __init__(self, wait) -> None:
        self._wait = wait

    def wait(self, ms: int = 0) -> None:
        self._wait(ms)

    def addWidget(self, _widget: QWidget) -> None:  # noqa: N802
        """The page owns every widget here; nothing is handed to the bot to keep."""

    def waitExposed(self, _widget: QWidget, timeout: int = 1000) -> None:  # noqa: N802
        self._wait(50)


def controls_of(page, find) -> list:
    """Every picker on the page, as the widget a caller holds and the control under it."""
    found = []
    seen = set()
    for control in find(PickerControl, all=True):
        owner = control
        walk = control.parentWidget()
        for _ in range(4):
            if walk is None:
                break
            if getattr(walk, "control", None) is control:
                owner = walk
                break
            walk = walk.parentWidget()
        if id(control) in seen:
            continue
        seen.add(id(control))
        found.append((owner, control))
    return found


def shape_of(control: PickerControl, wait) -> PickerShape:
    """The clauses a control's own props say apply to it."""
    return PickerShape(
        multiple=control.multiple,
        inline=control.inline,
        searchable=control.searchable if not control.inline else True,
        clearable=control.clearable,
        settle=lambda: wait(SETTLE_MS if control.row_model() is not None else 60),
    )


def demo_of(control: PickerControl) -> str:
    """The demo case a control sits in, so a failure names something a reader can find."""
    walk = control.parentWidget()
    for _ in range(6):
        if walk is None:
            return "page"
        name = walk.property("data_demo_case")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def settle_rows(control: PickerControl, wait, ms: int = 4000) -> bool:
    """Turn the loop until the list has a row to press, or give up."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if control.list_surface().row_count() > 0:
            return True
    return False


# --- the state clauses, for a control a demo draws inert -------------------------------


def state_clauses(control: PickerControl, wait, note) -> None:
    """Clauses 9 and 10 on a control the page itself draws readonly or disabled."""
    if control.readonly:
        if control.disabled_opacity() != 1.0:
            note("readonly", "a readonly control is drawn at less than full contrast")
        if control.open_control().isVisibleTo(control):
            note("readonly", "a readonly control keeps its chevron")
        if control.clear_control().isVisibleTo(control):
            note("readonly", "a readonly control keeps its clear control")
    if control.disabled and control.disabled_opacity() != 0.5:
        note("disabled", "a disabled control is not at half opacity")
    press_control(control)
    wait(200)
    if control.is_open:
        note("readonly" if control.readonly else "disabled", "an inert control opened its list")
        control.set_open(False)


# --- the upstream drives ----------------------------------------------------------------


def mandatory_clear(controls, note) -> str:
    """`picker-mandatory-clear.js`: a control refused a clear keeps its value and its chevron."""
    refused = [(owner, control) for owner, control in controls if not control.clearable]
    if not refused:
        return "no control refuses a clear on this page"
    for _owner, control in refused:
        where = demo_of(control)
        if control.clear_control().isVisibleTo(control):
            note("mandatory-clear", f"{where}: a control refused a clear draws one")
        if control.labels and not control.readonly and not control.open_control().isVisibleTo(control):
            note("mandatory-clear", f"{where}: it lost the chevron as well as the clear")
        if not control.labels:
            note("mandatory-clear", f"{where}: it lost its value")
    return f"{len(refused)} controls"


def empty_draws_no_clear(controls, note) -> None:
    """Clause 8 the other way round: an empty control never draws a clear."""
    for _owner, control in controls:
        if not control.labels and control.clear_control().isVisibleTo(control):
            note("clear-control", f"{demo_of(control)}: an empty control draws a clear control")


def pick_releases_chip(control: PickerControl, wait, note) -> str:
    """`picker-pick-releases-chip.js`: a pick made with a chip armed frees it."""
    if not control.multiple or not control.chip_row:
        return "not a token field"
    before = len(control.labels)
    if before < 2:
        return "too few chips to walk"
    caret = control.caret()
    control.set_open(True)
    if not settle_rows(control, wait):
        note("pick-releases-chip", "the list drew no row to take")
        control.set_open(False)
        return "no row"
    caret.setFocus()
    QTest.keyClick(caret, Qt.Key.Key_Backspace)
    wait(120)
    if control.armed != before - 1:
        note("pick-releases-chip", f"Backspace armed chip {control.armed}, wanted {before - 1}")
        control.set_open(False)
        return "not armed"
    QTest.keyClick(caret, Qt.Key.Key_Left)
    wait(120)
    if control.armed != before - 2:
        note("pick-releases-chip", f"ArrowLeft armed chip {control.armed}, wanted {before - 2}")
    if not control.is_open:
        note("pick-releases-chip", "arming a chip closed the list")
        control.set_open(True)
        settle_rows(control, wait)

    surface = control.list_surface()
    row = next(
        (
            i
            for i in range(surface.row_count())
            if not surface.is_load_more(i)
            and surface.model().index(i, 0).data(_CHECKED) is not True
        ),
        None,
    )
    if row is None:
        note("pick-releases-chip", "every row on show is already chosen")
        control.set_open(False)
        return "no free row"
    surface.activate(row)
    wait(SETTLE_MS)
    took = len(control.labels)
    if took <= before:
        note("pick-releases-chip", "the pick added no chip")
    if control.armed is not None:
        note("pick-releases-chip", f"chip {control.armed} is still armed after the pick")
    if not control.is_open:
        note("pick-releases-chip", "a pick closed a multi picker")
    if control.caret().window().focusWidget() is not control.caret():
        note("pick-releases-chip", "the caret did not go back to the input after the pick")
    QTest.keyClick(control.caret(), Qt.Key.Key_Backspace)
    wait(150)
    if control.armed != took - 1:
        note("pick-releases-chip", f"Backspace then armed chip {control.armed}, wanted {took - 1}")
    control.arm(None)
    control.set_open(False)
    wait(120)
    return f"{before} chips, then {took}"


def arrow_scroll(control: PickerControl, wait, note) -> dict:
    """`picker-arrow-scroll.js`: the highlight stays in the list across a load-more page."""
    surface = control.list_surface()
    control.set_open(True)
    if not settle_rows(control, wait):
        note("arrow-scroll", "the list drew no row")
        control.set_open(False)
        return {}
    caret = control.caret()
    caret.setFocus()
    bar = surface.verticalScrollBar()

    def in_view() -> bool | None:
        row = surface.highlighted()
        if row < 0:
            return None
        rect = surface.visualRect(surface.model().index(row, 0))
        frame = surface.viewport().rect()
        return rect.top() >= frame.top() - 1 and rect.bottom() <= frame.bottom() + 1

    out = steps = 0
    for _ in range(surface.row_count() + 2):
        QTest.keyClick(caret, Qt.Key.Key_Down)
        wait(40)
        seen = in_view()
        if seen is not None:
            steps += 1
        if seen is False:
            out += 1
    on_more = surface.is_load_more(surface.highlighted())
    scrolled = bar.value()
    before_rows = surface.row_count()
    before_value = bar.value()

    QTest.keyClick(caret, Qt.Key.Key_Return)
    grew = False
    end = time.time() + 6
    while time.time() < end:
        wait(60)
        if surface.row_count() > before_rows:
            grew = True
            break
    wait(300)
    after_page = in_view()
    out_after = 0
    for _ in range(5):
        QTest.keyClick(caret, Qt.Key.Key_Down)
        wait(40)
        if in_view() is False:
            out_after += 1
    held = bar.value()
    out_up = 0
    for _ in range(surface.row_count() + 4):
        QTest.keyClick(caret, Qt.Key.Key_Up)
        wait(30)
        if in_view() is False:
            out_up += 1
    back_at_top = bar.value()

    if steps == 0:
        note("arrow-scroll", "no row was ever highlighted")
    if out:
        note("arrow-scroll", f"the highlight left the list on {out} of {steps} presses down")
    if not on_more:
        note("arrow-scroll", "Down never reached the load-more row")
    if not grew:
        note("arrow-scroll", "Enter on the load-more row loaded no page")
    if after_page is False:
        note("arrow-scroll", "the highlight sat outside the list after a load-more page")
    if out_after:
        note("arrow-scroll", f"the highlight left the list on {out_after} presses in the new page")
    if scrolled <= 0:
        note("arrow-scroll", "the list never scrolled at all")
    # The page lands under the rows already read: the list stays where the reader left it.
    if grew and abs(held - before_value) > surface.viewport().height():
        note("arrow-scroll", f"the list jumped from {before_value} to {held} when the page landed")
    if out_up:
        note("arrow-scroll", f"the highlight left the list on {out_up} presses up")
    if back_at_top != 0:
        note("arrow-scroll", f"the list stopped at {back_at_top}px rather than the top")
    control.set_open(False)
    wait(150)
    return {
        "steps": steps,
        "out": out,
        "on_load_more": on_more,
        "grew": grew,
        "kept_scroll": [before_value, held],
        "back_at_top": back_at_top,
    }


def multi_picker_fit(control: PickerControl, wait, note) -> dict:
    """`multi-picker-fit.js`: whole chips, `+n` for the rest, one line, search in the popup."""
    chips = control.chips()
    shown = [chip for chip in chips if chip.isVisibleTo(control)]
    hidden = [chip for chip in chips if not chip.isVisibleTo(control)]
    pill = control.overflow_pill()
    left, right, _pad = control._insets()
    edge = control.width() - right
    cut = [chip for chip in shown if chip.x() + chip.sizeHint().width() > edge + 1]

    if not shown:
        note("multi-picker-fit", "the narrow control drew no chip at all")
    if cut:
        note("multi-picker-fit", f"{len(cut)} of {len(shown)} visible chips are cut")
    if hidden and not pill.isVisibleTo(control):
        note("multi-picker-fit", f"{len(hidden)} chips hidden with no +n")
    if pill.isVisibleTo(control) and pill.count != len(hidden):
        note("multi-picker-fit", f"the pill reads +{pill.count} for {len(hidden)} hidden")
    # Whole chips only: the ones drawn are the first n of the row, in order.
    if shown != chips[: len(shown)]:
        note("multi-picker-fit", "the chips drawn are not the leading ones of the row")
    if pill.isVisibleTo(control) and pill.x() + pill.width() > edge + 1:
        note("multi-picker-fit", "the +n pill is pushed past the row's edge")
    if control.height() > 40:
        note("multi-picker-fit", f"the control is {control.height()}px tall, wanted one line")
    if control.inline:
        note("multi-picker-fit", "the ellipsis control still holds an inline caret")

    # A press on the pill opens the list, where the hidden ones are.
    pill.pressed_signal.emit()
    wait(400)
    if not control.is_open:
        note("multi-picker-fit", "a press on the +n pill opened no list")
    elif not control.search_row().isVisibleTo(control.popup()):
        note("multi-picker-fit", "the summary control's popup has no search row")
    elif control.caret().window().focusWidget() is not control.caret():
        note("multi-picker-fit", "the popup's search box did not take the caret")
    control.set_open(False)
    wait(150)
    return {"shown": len(shown), "hidden": len(hidden), "pill": pill.count, "h": control.height()}


def escape_clears(control: PickerControl, wait, note) -> None:
    """`picker-escape.js`: Escape closes the list and leaves the query empty."""
    control.set_open(True)
    wait(200)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, "ab")
    wait(200)
    if control.query != "ab":
        note("escape", f"the caret holds {control.query!r} after two keys")
    QTest.keyClick(caret, Qt.Key.Key_Escape)
    wait(250)
    if control.is_open:
        note("escape", "Escape did not close the list")
        control.set_open(False)
    if control.query != "":
        note("escape", f"the query still reads {control.query!r} after Escape")
    if caret.text() != "":
        note("escape", f"the caret still shows {caret.text()!r} after Escape")
    wait(150)


def tab_walk(control: PickerControl, wait, note) -> list:
    """Tab walks the caret, the clear control and the chevron, then leaves the control."""
    if not control.inline or not control.labels:
        return []
    caret = control.caret()
    caret.setFocus()
    wait(50)
    seen = []
    for _ in range(3):
        QTest.keyClick(caret.window().focusWidget() or control, Qt.Key.Key_Tab)
        wait(50)
        holder = caret.window().focusWidget()
        seen.append(holder.objectName() if holder is not None else "")
    wanted = [control.clear_control().objectName(), control.open_control().objectName()]
    if seen[:2] != wanted:
        note("tab", f"Tab walked {seen}, wanted {wanted} then out of the control")
    elif seen[2] in wanted:
        note("tab", f"Tab stayed on {seen[2]} rather than leaving the control")
    control.arm(None)
    return seen


# --- the page's own reads -----------------------------------------------------------------


_CHECKED = None  # filled in by `drive`, which imports the roles the delegate reads.


def read_behaviours(page, find, wait, note) -> dict:  # noqa: C901
    """Hydration, exclude, the debounce, a stale answer and the error line."""
    from sg_widgets_qt.widgets.entity_picker import EntitySearchPicker

    seen: dict = {}
    pickers = find(EntitySearchPicker, all=True)
    if not pickers:
        return seen

    # Hydration: a picker handed a bare `{type, id}` reads the name behind it.
    bare = [p for p in pickers if p.control.labels and any(not ref.name for ref in _refs(p))]
    for picker in pickers:
        labels = picker.control.labels
        refs = _refs(picker)
        if not refs or not labels:
            continue
        placeholders = [
            label for ref, label in zip(refs, labels) if label.startswith(f"{ref.type} {ref.id}")
        ]
        if placeholders and picker not in bare:
            note("hydrate", f"{demo_of(picker.control)}: {placeholders} never resolved to a name")
    seen["hydrated"] = sum(1 for p in pickers if p.control.labels)

    # exclude: what the caller keeps out is not offered.
    excluded = [p for p in pickers if p.exclude]
    if excluded:
        picker = excluded[0]
        control = picker.control
        keys = {f"{ref.type}:{ref.id}" for ref in picker.exclude}
        control.set_open(True)
        settle_rows(control, wait)
        offered = set(control.items)
        if keys & offered:
            note("exclude", f"the list offers {sorted(keys & offered)}, which the caller excluded")
        seen["exclude"] = {"kept_out": sorted(keys), "rows": len(offered)}
        control.set_open(False)
        wait(150)

    context = page.context
    if context is None:
        return seen

    # The debounce: two keystrokes in one pause leave one read behind.
    picker = pickers[0]
    control = picker.control
    control.set_open(True)
    settle_rows(control, wait)
    wait(600)
    context.reset_reads()
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, "sh")
    wait(60)
    QTest.keyClicks(caret, "01")
    wait(SETTLE_MS + 600)
    # `search` is the protocol method a picker's query goes through; the mock's client is
    # counted under the same name `window.sgDemoReads` carries upstream.
    finds = context.reads.get("search", 0) + context.reads.get("find", 0)
    seen["debounce"] = {"keys": 4, "reads": dict(context.reads)}
    if finds == 0:
        note("debounce", "four keystrokes left no read at all")
    elif finds > 2:
        note("debounce", f"four keystrokes in one pause left {finds} reads behind")

    # A stale answer is dropped: the rows on show answer the query the caret holds.
    QTest.keyClicks(caret, "0")
    wait(30)
    for _ in range(3):
        QTest.keyClick(caret, Qt.Key.Key_Backspace)
        wait(20)
    wait(SETTLE_MS + 800)
    held = control.query
    answered = picker.state.query
    seen["stale"] = {"query": held, "answered": answered}
    if answered != held:
        note("stale", f"the rows answer {answered!r} while the caret holds {held!r}")
    control.set_open(False)
    wait(200)

    # The error line: the demo arms the mock's next call to fail.
    demo = _demo_widget(page)
    arm = getattr(demo, "_arm_failure", None)
    broken = _armed_picker(pickers, demo)
    if callable(arm) and broken is not None:
        arm()
        broken.control.set_open(True)
        end = time.time() + 6
        failed = False
        while time.time() < end:
            wait(80)
            if broken.control.error:
                failed = True
                break
        seen["error"] = {"line": bool(failed), "said": str(broken.control.error or "")[:60]}
        if not failed:
            note("error", "a read armed to fail drew no error")
        elif not broken.control.state_line().isVisibleTo(broken.control.popup()):
            note("error", "the error is held but the line is not drawn")
        broken.control.set_open(False)
        wait(200)
        broken.control.set_error(None)
    return seen


def _refs(picker) -> list:
    value = getattr(picker, "value", None)
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _demo_widget(page):
    for stage in page.stages:
        demo = stage.widget
        if demo is not None and hasattr(demo, "_arm_failure"):
            return demo
    return None


def _armed_picker(pickers, demo):
    """The picker reading the client the demo can arm: its own context, not the page's."""
    failing = getattr(demo, "_failing", None)
    if failing is None:
        return None
    for picker in pickers:
        if picker.context is failing.context:
            return picker
    return None


# --- the walk -------------------------------------------------------------------------------


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    global _CHECKED
    from sg_widgets_qt.primitives.roles import Roles

    _CHECKED = Roles.CHECKED

    wait(500)
    failures: list = []
    walked: list = []
    bot = _Bot(wait)
    controls = controls_of(page, find)
    if not controls:
        return {"verdict": f"FAIL {page.data_name}: no picker control on the page"}

    def note(clause: str, detail: str) -> None:
        failures.append(f"{page.data_name}: {clause} — {detail}")

    empty_draws_no_clear(controls, note)

    done = set()
    for owner, control in controls:
        where = demo_of(control)

        def under(clause: str, detail: str, where=where) -> None:
            failures.append(f"{page.data_name} {where}: {clause} — {detail}")

        if control.disabled or control.readonly:
            state_clauses(control, wait, under)
            walked.append({"demo": where, "ran": "disabled" if control.disabled else "readonly"})
            continue

        key = f"{control.multiple}|{control.inline}|{control.searchable}|{control.text_value}"
        if key in done:
            continue
        done.add(key)
        shape = shape_of(control, wait)
        try:
            checked = check_contract(bot, owner, shape)
        except AssertionError as failure:
            under("contract", f"{failure}")
            checked = []
        except Exception as failure:  # noqa: BLE001
            under("contract", f"{type(failure).__name__}: {failure}")
            checked = []
        missed = [
            clause
            for clause in CLAUSES
            if clause not in checked
            and clause not in ("value keys", "highlight in view", "pick")
        ]
        if missed:
            under("contract", f"never reached {missed}")
        walked.append({"demo": where, "shape": key, "clauses": checked})
        control.set_open(False)
        wait(150)

    seen: dict = {"walked": walked}
    seen["mandatory_clear"] = mandatory_clear(controls, note)

    tokens = next(
        (c for _o, c in controls if c.multiple and c.chip_row and c.inline and len(c.labels) > 1),
        None,
    )
    if tokens is not None:
        seen["pick_releases_chip"] = pick_releases_chip(tokens, wait, note)

    paged = next(
        (c for _o, c in controls if c.has_more and not c.readonly and not c.disabled), None
    )
    if paged is not None:
        seen["arrow_scroll"] = arrow_scroll(paged, wait, note)

    narrow = next(
        (
            c
            for _o, c in controls
            if c.multiple and c.summary == "ellipsis" and c.overflow_pill().count > 0
        ),
        None,
    )
    if narrow is not None:
        seen["multi_picker_fit"] = multi_picker_fit(narrow, wait, note)

    live = next((c for _o, c in controls if not c.readonly and not c.disabled and c.inline), None)
    if live is not None:
        escape_clears(live, wait, note)
        filled = next(
            (c for _o, c in controls if c.inline and c.labels and not c.readonly and not c.disabled),
            None,
        )
        if filled is not None:
            seen["tab"] = tab_walk(filled, wait, note)

    seen.update(read_behaviours(page, find, wait, note))

    QApplication.processEvents()
    return {
        "verdict": (
            f"PASS every picker on {page.data_name} keeps the contract"
            if not failures
            else "FAIL " + "; ".join(failures[:12])
        ),
        "failures": failures,
        "seen": seen,
    }
