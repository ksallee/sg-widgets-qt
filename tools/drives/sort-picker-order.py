"""The order the sort picker emits, key by key, and the string it serialises to.

    .venv/bin/python tools/qa.py --page sort-picker --drive tools/drives/sort-picker-order.py
    .venv/bin/python tools/qa.py --page sort-picker --drive tools/drives/sort-picker-order.py --qt5

Order is meaningful, so the drive checks what `sort_changed` carries after every edit the state
matrix shoots: a key added, its direction turned, a key moved by the grip's keyboard handle, a
key removed. After each one:

  * `changed` and `sort_changed` carry the same list, once each,
  * the list is the order the rows are drawn in,
  * the string beside it is core's own `to_sort_string`: comma-joined, a leading `-` on a
    descending key (026_result_order),
  * the trigger names the keys in that order, comma-joined, and carries the count from two up.

Only sortable fields are offered, and never one already chosen, which the drive reads off the
picker's own `offers`.
"""
from __future__ import annotations

import time

from qtpy import QtWidgets

from sg_widgets_core.filter_ux import is_sortable, to_sort_string
from sg_widgets_qt.widgets.sort_picker import SortPicker


def wait_for(read, wait, ms: int = 8000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def wire_of(page):
    for one in page.findChildren(QtWidgets.QPlainTextEdit):
        if one.objectName() == "sort-string":
            return one
    return None


def drawn(picker: SortPicker) -> list[str]:
    """The paths the key rows are drawn for, in the order they stand."""
    return list(picker.key_rows().sortable().ids)


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(600)
    picker = find("sort-picker-main")
    if not isinstance(picker, SortPicker):
        every = find(SortPicker, all=True)
        picker = every[0] if every else None
    wire = wire_of(page)
    if picker is None or wire is None:
        return {"verdict": "FAIL the page has no sort picker with its sort string"}
    picker.set_open(True)
    wait_for(lambda: picker.open, wait, 4000)
    wait(400)

    keys: list = []
    pairs: list = []
    picker.sort_changed.connect(keys.append)
    picker.changed.connect(lambda value, sort: pairs.append((value, sort)))

    failures: list[str] = []
    steps: list[dict] = []

    def check(name: str) -> None:
        wait(250)
        held = picker.value
        order = [k.field for k in held]
        want = to_sort_string(held)
        steps.append({"step": name, "order": order, "sort": want})
        if not keys:
            failures.append(f"{name}: sort_changed carried nothing")
            return
        if [k.field for k in keys[-1]] != order:
            failures.append(f"{name}: sort_changed carried {[k.field for k in keys[-1]]}, the picker holds {order}")
        if len(pairs) != len(keys):
            failures.append(f"{name}: changed ran {len(pairs)} times to sort_changed's {len(keys)}")
        elif pairs[-1][1] != want:
            failures.append(f"{name}: changed carried the string {pairs[-1][1]!r}, core makes {want!r}")
        if drawn(picker) != order:
            failures.append(f"{name}: the rows are drawn {drawn(picker)}, the picker holds {order}")
        if wire.toPlainText().strip() not in (want, "(none)"):
            failures.append(f"{name}: the block reads {wire.toPlainText().strip()!r}, core makes {want!r}")
        label = ", ".join(picker.name_of(k.field) for k in held) if held else "Sort"
        if picker.trigger().text != label:
            failures.append(f"{name}: the trigger reads {picker.trigger().text!r}, wanted {label!r}")
        chip = str(len(held)) if len(held) > 1 else ""
        if picker.trigger().count != chip:
            failures.append(f"{name}: the trigger carries {picker.trigger().count!r}, wanted {chip!r}")

    opened = [k.field for k in picker.value]
    steps.append({"step": "rest", "order": opened, "sort": picker.sort})
    if picker.sort != to_sort_string(picker.value):
        failures.append(f"at rest the picker reads {picker.sort!r}, core makes {to_sort_string(picker.value)!r}")

    # Only a sortable field the caller offers, and never one already chosen.
    fields = picker.field_picker().context.schema.fields("Shot") if picker.context is not None else {}
    refused = [
        name
        for name, field in fields.items()
        if picker.offers(field, name) and (not is_sortable(field.data_type) or name in opened)
    ]
    if refused:
        failures.append(f"the list offers {refused}")

    before = len(keys)
    picker.add("description")
    wait_for(lambda b=before: len(keys) > b, wait, 4000)
    check("added")

    picker.set_direction(0, "desc")
    check("turned")

    # The grip's own keyboard handle: Alt with an arrow moves the row one place.
    rows = picker.key_rows().rows()
    if len(rows) > 1:
        picker.key_rows().sortable().move_by(1, -1)
        check("moved")
    else:
        failures.append("too few keys to move one")

    picker.remove(len(picker.value) - 1)
    check("removed")

    while len(picker.value) > 1:
        picker.remove(len(picker.value) - 1)
    check("one key")
    picker.remove(0)
    check("none")
    if picker.sort != "":
        failures.append(f"an empty list serialises to {picker.sort!r}")
    if picker.trigger().text != "Sort":
        failures.append(f"an empty trigger reads {picker.trigger().text!r}")

    return {
        "verdict": (
            f"PASS sort_changed and changed carry the same order after {len(steps)} states,"
            " the rows are drawn in it, and the string is core's own to_sort_string"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "steps": steps,
        "emitted": len(keys),
    }
