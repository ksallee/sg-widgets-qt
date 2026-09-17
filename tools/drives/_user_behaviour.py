"""What the two user pickers' behaviour drives share: the contract, the preset and the payload.

`tools/drives/user-picker.py` and `tools/drives/user-multi-picker.py` are the entry points; both
run `walk` over their own page. The ten clauses come from `tests/qt/test_picker_contract`, so the
drive and the test walk the same code against the real demos rather than a picker built for the
check.

Beside them, what the two docs pages promise and nothing else:

    preset        HumanUser and ApiUser, and HumanUser alone where `include_api_users=False`
    active        `sg_status_list is act`, dropped where `include_inactive` is set
    fields        `login`, `email` and `sg_status_list` are read on top of the caller's own
    search        the display-name chain and the email always, `login` while the query has no
                  whitespace, `starts_with` on the address until the query holds an `@`
    sub-label     the address under the name, and `API user` for a script account
    address       `le` matches the one person whose local part holds it, not the whole domain
    payload       `value_changed` carries exactly what the docs page's Events table says
"""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.filter import EntityRef, to_api3_hash
from sg_widgets_core.picker import (
    USER_PICKER_FIELDS,
    PickerRow,
    user_search_fields,
)
from sg_widgets_qt.widgets.picker_control import PickerControl
from tests.qt.test_picker_contract import CLAUSES, PickerShape, check_contract, press_control

__all__ = ["walk"]

#: The mock's latency plus the debounce, with room for the hop back onto the GUI thread.
SETTLE_MS = 1200

#: The active condition every person search carries (entity_types/HumanUser).
ACTIVE = ["sg_status_list", "is", "act"]

#: A query whose local part one person alone holds, which the domain must not widen.
NARROW = "le"
#: The person that query is meant to answer, and the address that names them.
NARROW_NAME = "Cleo Dias"
#: A query that reaches past the `@`, so the address is matched whole.
WIDE = "ada.lovelace@"
WIDE_NAME = "Ada Lovelace"


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


# --- finding the pickers ------------------------------------------------------------------


def pickers_of(find, kind) -> list:
    """Every user picker on the page, in the order the demo lays them out."""
    return [one for one in find(kind, all=True) if one.isVisible()]


def demo_of(picker) -> str:
    """The demo case a picker sits in, so a failure names something a reader can find."""
    walk_up = picker.control.parentWidget()
    for _ in range(8):
        if walk_up is None:
            return "page"
        name = walk_up.property("data_demo_case")
        if name:
            return str(name)
        walk_up = walk_up.parentWidget()
    return "page"


def conditions(picker) -> list:
    """The pre-filter as the wire shape, so a condition can be looked for by path."""
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def settle_rows(control: PickerControl, wait, ms: int = 6000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if control.list_surface().row_count() > 0:
            return True
    return False


def settle_query(picker, control: PickerControl, query: str, wait, ms: int = 8000) -> None:
    """Type a query and turn the loop until the rows on show answer it."""
    caret = control.caret()
    caret.setFocus()
    caret.clear()
    control.set_query("")
    QTest.keyClicks(caret, query)
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if picker.state.query == query and not picker.state.loading:
            break
    wait(200)


def clear_value(picker, wait) -> None:
    """Empty a picker before a query is read off its list.

    A selection is pinned into the option list whatever the query — `withSelectedPinned`
    upstream — so a row left behind by an earlier check would read as a row the query matched.
    """
    picker.set_value([] if isinstance(picker.value, list) else None)
    wait(150)


def labels_on_show(control: PickerControl) -> list:
    """The label of every row the list draws."""
    from sg_widgets_qt.primitives.roles import Roles

    surface = control.list_surface()
    model = surface.model()
    out = []
    for row in range(surface.row_count()):
        if surface.is_load_more(row):
            continue
        out.append(model.index(row, 0).data(Roles.LABEL))
    return out


# --- the contract ---------------------------------------------------------------------------


def contract(pickers, wait, note, touched: set) -> list:
    """Rule 7, every clause that applies, once per shape the page draws.

    A clause takes a row, so the picker it runs on ends holding a value, and a selection is
    pinned into the option list whatever the query. Every picker it touches is recorded so the
    checks after it read one the walk left alone, which is what the upstream drives do by
    naming their own demo case.
    """
    bot = _Bot(wait)
    walked: list = []
    done = set()
    for picker in pickers:
        control = picker.control
        where = demo_of(picker)

        def under(clause: str, detail: str, where=where) -> None:
            note(f"{where}: {clause} — {detail}")

        if control.disabled or control.readonly:
            state_clauses(control, wait, under)
            walked.append({"demo": where, "ran": "disabled" if control.disabled else "readonly"})
            continue
        key = f"{control.multiple}|{control.inline}|{control.searchable}"
        if key in done:
            continue
        done.add(key)
        touched.add(id(picker))
        shape = PickerShape(
            multiple=control.multiple,
            inline=control.inline,
            searchable=control.searchable if not control.inline else True,
            clearable=control.clearable,
            settle=lambda: wait(SETTLE_MS),
        )
        try:
            checked = check_contract(bot, picker, shape)
        except AssertionError as failure:
            under("contract", str(failure))
            checked = []
        except Exception as failure:  # noqa: BLE001
            under("contract", f"{type(failure).__name__}: {failure}")
            checked = []
        missed = [
            clause
            for clause in CLAUSES
            if clause not in checked and clause not in ("value keys", "highlight in view", "pick")
        ]
        if missed:
            under("contract", f"never reached {missed}")
        walked.append({"demo": where, "shape": key, "clauses": checked})
        control.set_open(False)
        wait(150)
    return walked


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


# --- the person preset ------------------------------------------------------------------------


def preset(pickers, note) -> dict:
    """The four person props, as `docs/widgets/user-picker.md` states them."""
    seen: dict = {"types": {}, "active": {}, "fields": {}}
    for picker in pickers:
        where = demo_of(picker)
        wanted = ["HumanUser", "ApiUser"] if picker.include_api_users else ["HumanUser"]
        if picker.entity_types != wanted:
            note(f"{where}: preset — searches {picker.entity_types}, wanted {wanted}")
        seen["types"][where] = picker.entity_types

        held = conditions(picker)
        active = any(one == ACTIVE for one in held)
        # `sg_status_list` on HumanUser is `act` and `dis`, `act` the default
        # (entity_types/HumanUser); ApiUser has no status field, so core prunes it per type.
        if active is picker.include_inactive:
            note(
                f"{where}: preset — the active condition is "
                f"{'on' if active else 'off'} while include_inactive is {picker.include_inactive}"
            )
        seen["active"][where] = active

        read = list(picker.rows_model.fields)
        missing = [name for name in USER_PICKER_FIELDS if name not in read]
        if missing:
            note(f"{where}: preset — {missing} are never read, so the row cannot show them")
        own = [name for name in picker.fields if name not in read]
        if own:
            note(f"{where}: preset — the caller's own {own} were lost to the preset")
        seen["fields"][where] = read
    return seen


def search_fields(picker, note) -> dict:
    """The query is matched on the name chain and the email, and on `login` without whitespace."""
    where = demo_of(picker)
    # `picker.search_fields` answers the caller's own prop, as `fields` and `filters` do; the
    # composition the preset hands the search is what a query is actually matched on.
    made = picker.search._opts.search_fields
    if not callable(made):
        note(f"{where}: search — the preset left `search_fields` as {made!r}, wanted a callable")
        return {}
    seen = {}
    for query in ("le", "ada.lovelace@", "ada lovelace"):
        held = list(made(query))
        wanted = list(user_search_fields(query))
        paths = [one if isinstance(one, str) else one.path for one in held]
        operators = [None if isinstance(one, str) else one.operator for one in held]
        seen[query] = list(zip(paths, operators))
        if len(held) != len(wanted):
            note(f"{where}: search — {query!r} matches {paths}, wanted {len(wanted)} fields")
            continue
        has_login = "login" in paths
        # A login never holds whitespace, so it is dropped once the query does.
        if has_login is any(char.isspace() for char in query.strip()):
            note(f"{where}: search — {query!r} matches {paths}: the login rule is the wrong way")
        address = next((op for path, op in zip(paths, operators) if path == "email"), None)
        # Everyone shares a domain, so the address is `starts_with` until the query holds an `@`.
        want_op = "contains" if "@" in query else "starts_with"
        if address != want_op:
            note(f"{where}: search — {query!r} matches the address with {address}, wanted {want_op}")
    return seen


def sub_labels(picker, wait, note) -> dict:
    """The address under the name, and `API user` for a script account."""
    where = demo_of(picker)
    clear_value(picker, wait)
    model = picker.rows_model
    script = model.sub_label(PickerRow(type="ApiUser", id=90, name="bot"))
    if script != "API user":
        note(f"{where}: sub-label — a script account reads {script!r}, wanted 'API user'")
    control = picker.control
    control.set_open(True)
    settle_rows(control, wait)
    people = [row for row in picker.state.rows if row.type == "HumanUser"]
    wrong = [row.name for row in people if model.sub_label(row) != row.values.get("email")]
    if not people:
        note(f"{where}: sub-label — no person was offered, so the address was never drawn")
    if wrong:
        note(f"{where}: sub-label — {wrong} do not carry their address under the name")
    control.set_open(False)
    wait(150)
    return {"script": script, "people": len(people), "wrong": wrong}


def address_search(picker, wait, note) -> dict:
    """`user-picker-address.js`: the local part narrows, the domain never widens."""
    where = demo_of(picker)
    clear_value(picker, wait)
    control = picker.control
    control.set_open(True)
    settle_rows(control, wait)

    settle_query(picker, control, NARROW, wait)
    narrow = labels_on_show(control)
    if narrow != [NARROW_NAME]:
        note(f"{where}: address — {NARROW!r} matched {narrow}, wanted [{NARROW_NAME!r}]")

    settle_query(picker, control, WIDE, wait)
    wide = labels_on_show(control)
    if wide != [WIDE_NAME]:
        note(f"{where}: address — {WIDE!r} matched {wide}, wanted [{WIDE_NAME!r}]")
    runs = matched_runs(control)
    if not any(run.lower().startswith("ada") for run in runs):
        note(f"{where}: address — the matched run in the sub-label is {runs}")

    QTest.keyClick(control.caret(), Qt.Key.Key_Escape)
    wait(200)
    control.set_open(False)
    wait(150)
    return {"narrow": narrow, "wide": wide, "runs": runs}


def matched_runs(control: PickerControl) -> list:
    """What the delegate draws in DemiBold in each row's sub-label (rule 6).

    `Roles.SUB_RUNS` is the sub-label as `[(text, matched), ...]`, which is the same shape the
    upstream row renders as `<span class="font-semibold">`.
    """
    from sg_widgets_qt.primitives.roles import Roles

    surface = control.list_surface()
    model = surface.model()
    out = []
    for row in range(surface.row_count()):
        if surface.is_load_more(row):
            continue
        for part in model.index(row, 0).data(Roles.SUB_RUNS) or []:
            try:
                text, matched = part[0], part[1]
            except (TypeError, IndexError):
                continue
            if matched:
                out.append(str(text))
    return out


# --- the payload -------------------------------------------------------------------------------


def payload(picker, wait, note, multiple: bool) -> dict:
    """`value_changed` carries exactly what the docs page's Events table promises."""
    where = demo_of(picker)
    clear_value(picker, wait)
    answers: list = []
    picker.value_changed.connect(lambda *args: answers.append(args))
    control = picker.control
    control.set_open(True)
    if not settle_rows(control, wait):
        note(f"{where}: payload — the list drew no row to take")
        control.set_open(False)
        return {}
    control.list_surface().activate(0)
    wait(SETTLE_MS)
    if not answers:
        note(f"{where}: payload — a pick emitted no value_changed")
        control.set_open(False)
        return {}
    args = answers[-1]
    if len(args) != 2:
        note(f"{where}: payload — value_changed carried {len(args)} arguments, wanted 2")
        control.set_open(False)
        return {}
    value, rows = args
    if multiple:
        # `EntityRef[]`, `PickerRow[]`, per docs/widgets/user-multi-picker.md.
        if not isinstance(value, list) or not all(isinstance(one, EntityRef) for one in value):
            note(f"{where}: payload — the value is {value!r}, wanted a list of EntityRef")
        if not isinstance(rows, list) or not all(isinstance(one, PickerRow) for one in rows):
            note(f"{where}: payload — the rows are {rows!r}, wanted a list of PickerRow")
        if isinstance(value, list) and isinstance(rows, list) and len(value) != len(rows):
            note(f"{where}: payload — {len(value)} references against {len(rows)} rows")
        paired = list(zip(value or [], rows or []))
        if not control.is_open:
            note(f"{where}: payload — a pick closed a multi picker")
    else:
        # `EntityRef`, `PickerRow`, per docs/widgets/user-picker.md.
        if not isinstance(value, EntityRef):
            note(f"{where}: payload — the value is {value!r}, wanted an EntityRef")
        if not isinstance(rows, PickerRow):
            note(f"{where}: payload — the row is {rows!r}, wanted a PickerRow")
        paired = [(value, rows)]
        if control.is_open:
            note(f"{where}: payload — a pick left a single picker open")
    for ref, row in paired:
        if not isinstance(ref, EntityRef) or not isinstance(row, PickerRow):
            continue
        if (ref.type, ref.id) != (row.type, row.id):
            note(f"{where}: payload — {ref.type} {ref.id} is not the row {row.type} {row.id}")
        if ref.type not in ("HumanUser", "ApiUser"):
            note(f"{where}: payload — {ref.type} is not a person or a script account")
        if not ref.name:
            note(f"{where}: payload — the reference carries no name")
    control.set_open(False)
    wait(200)
    return {
        "value": [f"{one.type} {one.id} {one.name}" for one, _row in paired],
        "kind": "list" if multiple else "one",
    }


def hydration(pickers, note) -> dict:
    """A bare `{type, id}` handed in resolves to a name by one batched read."""
    seen = {}
    for picker in pickers:
        labels = picker.control.labels
        refs = picker.value if isinstance(picker.value, list) else ([picker.value] if picker.value else [])
        if not refs or not labels:
            continue
        stale = [
            label
            for ref, label in zip(refs, labels)
            if not label or label == f"{ref.type} {ref.id}"
        ]
        if stale:
            note(f"{demo_of(picker)}: hydrate — {stale} never resolved to a name")
        seen[demo_of(picker)] = list(labels)
    return seen


# --- the walk -----------------------------------------------------------------------------------


def walk(page, wait, find, kind, multiple: bool) -> dict:
    """Every behaviour both user pickers' docs pages promise, on the page they are drawn on."""
    wait(600)
    failures: list = []

    def note(detail: str) -> None:
        failures.append(f"{page.data_name} {detail}")

    found = pickers_of(find, kind)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no user picker on the page"}

    live = [one for one in found if not one.control.disabled and not one.control.readonly]
    touched: set = set()
    seen: dict = {"pickers": len(found)}
    seen["walked"] = contract(found, wait, note, touched)
    seen.update(preset(found, note))

    def spare(prefer: str = "") -> Any:
        """A live picker the contract left alone, and with nothing pinned into its list."""
        clean = [one for one in live if id(one) not in touched]
        whole = [one for one in clean if one.include_api_users and not one.include_inactive]
        named = [one for one in (whole or clean) if demo_of(one) == prefer]
        return (named or whole or clean or live)[0]

    if live:
        seen["search_fields"] = search_fields(live[0], note)
        seen["sub_labels"] = sub_labels(spare(), wait, note)
        # The upstream twin searches the `by-address` demo, which is the case whose placeholder
        # names what a person search matches.
        seen["address"] = address_search(spare("by-address"), wait, note)
        seen["payload"] = payload(spare(), wait, note, multiple)
    seen["hydrated"] = hydration(found, note)

    QApplication.processEvents()
    return {
        "verdict": (
            f"PASS every user picker on {page.data_name} keeps the contract and the preset"
            if not failures
            else "FAIL " + "; ".join(failures[:12])
        ),
        "failures": failures,
        "seen": seen,
    }
