"""Collection state.

The half of the collections' controlled props that has no Qt in it: how a row is
keyed, which rows are disabled, where a keyboard cursor lands over them, and
whether a `sort` or `filters` prop still says what the source says.

A two-way prop and a store that own the same value need one rule to stop them
writing to each other forever: a change is pushed only when the two no longer say
the same thing, which is what the `same_*` predicates answer.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Union

from .client import EntityRow
from .collection import SortSpec, SourceFilters, row_key, to_wire_group
from .filter import EntityRef
from .filter_ux import SortKey

__all__ = [
    "CollapseState",
    "RowDisabledFn",
    "RowIdFn",
    "SelectionState",
    "as_collapse_state",
    "collapse_all",
    "collapse_state_from",
    "collapsed_keys",
    "expand_all",
    "first_enabled_index",
    "ids_for_refs",
    "is_collapsed",
    "next_enabled_index",
    "refs_for_ids",
    "row_id_of",
    "row_is_disabled",
    "same_collapse",
    "same_filters",
    "same_ids",
    "same_refs",
    "same_sort",
    "selectable_refs",
    "selection_state",
    "to_sort_keys",
    "to_sort_specs",
    "toggle_collapsed",
    "toggle_id",
    "toggle_ref",
]

#: How a collection keys a row. Without one, `Type:id`.
RowIdFn = Callable[[EntityRow], str]

#: True for a row the keyboard skips and the selection refuses.
RowDisabledFn = Callable[[EntityRow], bool]


def row_id_of(row: EntityRow, get_row_id: RowIdFn | None = None) -> str:
    """A row's id: the caller's, or `Type:id`."""
    return get_row_id(row) if get_row_id else row_key(row)


def row_is_disabled(row: EntityRow, is_row_disabled: RowDisabledFn | None = None) -> bool:
    """True when the caller says the row is disabled."""
    return is_row_disabled(row) is True if is_row_disabled else False


def next_enabled_index(
    count: int,
    from_: int,
    step: int,
    disabled: Callable[[int], bool],
) -> int:
    """Where a cursor lands moving `step` from `from_`, skipping disabled entries.

    The walk stops at the ends rather than wrapping, and answers `from_` when every
    entry that way is disabled, so a key press on the last enabled row does nothing.
    """
    if count <= 0 or step == 0:
        return -1
    at = from_ + step
    while 0 <= at < count:
        if not disabled(at):
            return at
        at += step
    return from_ if 0 <= from_ < count else -1


def first_enabled_index(count: int, from_: int, step: int, disabled: Callable[[int], bool]) -> int:
    """The first enabled entry at or after `from_`, walking `step`. -1 when there is none."""
    at = max(0, min(from_, count - 1))
    while 0 <= at < count:
        if not disabled(at):
            return at
        at += step or 1
    return -1


def ids_for_refs(
    rows: Sequence[EntityRow],
    refs: Sequence[EntityRef],
    get_row_id: RowIdFn | None = None,
) -> list[str]:
    """The ids the rows of `refs` are keyed under. A ref no loaded row stands for is dropped."""
    by_ref = {row_key(row): row_id_of(row, get_row_id) for row in rows}
    ids: list[str] = []
    for ref in refs:
        id_ = by_ref.get(row_key(ref))
        if id_ is not None and id_ not in ids:
            ids.append(id_)
    return ids


def refs_for_ids(
    rows: Sequence[EntityRow],
    ids: Sequence[str],
    get_row_id: RowIdFn | None = None,
) -> list[EntityRef]:
    """The rows the ids stand for, in row order."""
    wanted = set(ids)
    return [
        EntityRef(type=row.type, id=row.id) for row in rows if row_id_of(row, get_row_id) in wanted
    ]


def toggle_id(ids: Sequence[str], id: str, on: bool | None = None) -> list[str]:
    """`ids` with `id` added or removed. `on` forces the direction."""
    held = id in ids
    wanted = (not held) if on is None else on
    if wanted == held:
        return list(ids)
    return [*ids, id] if wanted else [entry for entry in ids if entry != id]


def same_ids(a: Sequence[str], b: Sequence[str]) -> bool:
    """True when two id lists hold the same ids, whatever their order."""
    if len(a) != len(b):
        return False
    held = set(a)
    return all(id_ in held for id_ in b)


def same_refs(a: Sequence[EntityRef], b: Sequence[EntityRef]) -> bool:
    """True when two selections name the same rows, whatever their order."""
    return same_ids([row_key(ref) for ref in a], [row_key(ref) for ref in b])


def same_sort(a: Sequence[SortSpec], b: Sequence[SortSpec]) -> bool:
    """True when two sort lists name the same keys in the same order."""
    return len(a) == len(b) and all(
        key.path == b[at].path and key.descending == b[at].descending for at, key in enumerate(a)
    )


def same_filters(a: SourceFilters, b: SourceFilters) -> bool:
    """True when two filters reach the server as the same group.

    The editor's tree and the wire hash are two spellings of one filter, so a `filters`
    prop holding the tree and a source holding the hash agree, and neither overwrites
    the other.
    """
    return _stable(to_wire_group(a)) == _stable(to_wire_group(b))


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def to_sort_specs(keys: Sequence[SortKey]) -> list[SortSpec]:
    """A sort picker's keys as a source's sort."""
    return [SortSpec(path=key.field, descending=key.direction == "desc") for key in keys if key.field]


def to_sort_keys(sort: Sequence[SortSpec]) -> list[SortKey]:
    """A source's sort as a sort picker's keys."""
    return [
        SortKey(field=key.path, direction="desc" if key.descending else "asc") for key in sort if key.path
    ]


def toggle_ref(selection: Sequence[EntityRef], ref: EntityRef) -> list[EntityRef]:
    """A selection with `ref` added or removed."""
    key = row_key(ref)
    if any(row_key(entry) == key for entry in selection):
        return [entry for entry in selection if row_key(entry) != key]
    return [*selection, EntityRef(type=ref.type, id=ref.id)]


@dataclass
class SelectionState:
    """What a header checkbox reads: every selectable row, or some of them."""

    all: bool = False
    some: bool = False


def selection_state(
    rows: Sequence[EntityRow],
    selection: Sequence[EntityRef],
    is_row_disabled: RowDisabledFn | None = None,
) -> SelectionState:
    """The tri-state of a select-all control over the rows that are loaded.

    A disabled row refuses its own box, so it is left out of both readings and a page of
    nothing but disabled rows is neither all nor some.
    """
    chosen = {row_key(ref) for ref in selection}
    open_ = [row for row in rows if not row_is_disabled(row, is_row_disabled)]
    if len(open_) == 0:
        return SelectionState(all=False, some=False)
    picked = len([row for row in open_ if row_key(row) in chosen])
    return SelectionState(all=picked == len(open_), some=picked > 0)


def selectable_refs(
    rows: Sequence[EntityRow],
    is_row_disabled: RowDisabledFn | None = None,
) -> list[EntityRef]:
    """Every selectable loaded row, as a selection."""
    return [
        EntityRef(type=row.type, id=row.id)
        for row in rows
        if not row_is_disabled(row, is_row_disabled)
    ]


# -------------------------------------------------------------------------- #
# collapsed groups                                                            #
# -------------------------------------------------------------------------- #


@dataclass
class CollapseState:
    """Which groups are shut.

    A mode with exceptions rather than a set of keys, because the keys a list holds are
    only the ones loaded so far: Collapse all written as a list says nothing about the
    groups the next page brings, and they arrive open under a header that said
    everything was shut. `all` is what a group does unless `except_` names it.
    """

    #: True when every group is shut but the ones `except_` names.
    all: bool = False
    #: The keys that go the other way from `all`.
    except_: list[str] = dc_field(default_factory=list)


def collapse_all() -> CollapseState:
    """Every group shut, including the ones not loaded yet."""
    return CollapseState(all=True, except_=[])


def expand_all() -> CollapseState:
    """Every group open."""
    return CollapseState(all=False, except_=[])


def as_collapse_state(value: Union[Sequence[str], CollapseState, None]) -> CollapseState:
    """A caller's value as a state.

    A bare key list is the open mode with those keys shut, and a mode written without
    `except_` has none.
    """
    if not value:
        return expand_all()
    if isinstance(value, CollapseState):
        return CollapseState(all=value.all is True, except_=list(value.except_ or []))
    return CollapseState(all=False, except_=list(value))


def is_collapsed(state: CollapseState, key: str) -> bool:
    """True when the group under `key` is shut."""
    return not state.all if key in state.except_ else state.all


def toggle_collapsed(state: CollapseState, key: str, on: bool | None = None) -> CollapseState:
    """`state` with the group under `key` shut or open. `on` forces the direction."""
    wanted = (not is_collapsed(state, key)) if on is None else on
    return CollapseState(all=state.all, except_=toggle_id(state.except_, key, wanted != state.all))


def collapsed_keys(state: CollapseState, keys: Sequence[str]) -> list[str]:
    """The keys of `keys` that are shut, in the order given."""
    return [key for key in keys if is_collapsed(state, key)]


def collapse_state_from(
    state: CollapseState,
    shut: Sequence[str],
    keys: Sequence[str],
) -> CollapseState:
    """The state a set of shut keys reads as, under the mode already in force.

    For a widget whose own machinery answers which headers are shut rather than which
    key was pressed. The mode is kept, so the groups the next page brings still follow
    it, and an exception for a key no longer drawn is dropped.
    """
    is_shut = set(shut)
    return CollapseState(all=state.all, except_=[key for key in keys if (key in is_shut) != state.all])


def same_collapse(a: CollapseState, b: CollapseState) -> bool:
    """True when two collapse states shut the same groups."""
    return a.all == b.all and same_ids(a.except_, b.except_)
