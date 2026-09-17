"""Option derivation for the schema pickers.

Everything the entity-type picker, the field picker and the column picker need to
turn a schema read into a list of rows: which types a caller allows, which fields
may be selected, which may be descended into, and what a dotted path is called.
The widgets hold state and draw; they decide nothing here.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Callable

from .client import EntityTypeInfo
from .field_types import is_filterable
from .presentation import PathLabelOptions, path_label
from .schema import FieldSchema
from .schema_service import PathSegment, SchemaService

__all__ = [
    "DEFAULT_MAX_DEPTH",
    "UNRESOLVED_PATH_LABEL",
    "EntityTypeOptions",
    "EntityTypeOptionsInput",
    "EntityTypeRestrictions",
    "ExtraField",
    "FieldHop",
    "FieldOption",
    "FieldOptionsInput",
    "FieldPathOption",
    "FieldPickerRestrictions",
    "current_type",
    "derive_field_options",
    "entity_type_options",
    "field_path_of",
    "filter_entity_types",
    "friendly_field_path",
    "matches_tokens",
    "move_field_path",
    "path_types",
    "resolve_field_path_options",
    "search_field_options",
    "search_field_path_options",
    "toggle_field_path",
    "traversal_targets",
]


def matches_tokens(query: str, *haystacks: str | None) -> bool:
    """Every whitespace-separated token of the query must appear in one of the haystacks."""
    tokens = [t for t in re.split(r"\s+", query.lower()) if t]
    if len(tokens) == 0:
        return True
    text = " ".join(h for h in haystacks if h).lower()
    return all(token in text for token in tokens)


@dataclass
class EntityTypeRestrictions:
    #: Codes a caller offers. Empty or absent means every type.
    allow: list[str] | None = None
    #: Codes a caller withholds, applied after `allow`.
    deny: list[str] | None = None


@dataclass
class EntityTypeOptionsInput(EntityTypeRestrictions):
    query: str | None = None


def filter_entity_types(
    types: Sequence[EntityTypeInfo],
    restrictions: EntityTypeRestrictions | None = None,
) -> list[EntityTypeInfo]:
    """The types a picker may offer, allow first and deny second.

    Applied to the derived list rather than to the read, so a caller narrowing the set
    sees the list change with no second call. `/schema` is 12KB and holds every enabled
    type, custom slots included (probe 002).
    """
    settings = restrictions if restrictions is not None else EntityTypeRestrictions()
    allow = set(settings.allow) if settings.allow else None
    deny = set(settings.deny) if settings.deny else None
    return [
        t for t in types
        if (allow is None or t.name in allow) and (deny is None or t.name not in deny)
    ]


@dataclass
class EntityTypeOptions:
    """What an entity-type picker draws: the rows on offer and the label a code takes."""

    #: Types on offer, `allow` first and `deny` second.
    types: list[EntityTypeInfo]
    #: Those the query matches, on display name or code.
    shown: list[EntityTypeInfo]
    #: A code's display name, or the code itself where the site offers no such type.
    label_of: Callable[[str], str]


def entity_type_options(
    loaded: Sequence[EntityTypeInfo] | None,
    options: EntityTypeOptionsInput | None = None,
) -> EntityTypeOptions:
    """The options both entity-type pickers derive from one schema read.

    The vocabulary is one read of 12KB (probe 002), so the query narrows the derived
    list here rather than asking for it again. `loaded` is None while the read is in
    flight, which offers nothing and labels a code as itself.
    """
    settings = options if options is not None else EntityTypeOptionsInput()
    types = filter_entity_types(loaded, settings) if loaded is not None else []
    by_name = {t.name: t for t in types}
    query = settings.query if settings.query is not None else ""
    return EntityTypeOptions(
        types=types,
        shown=[t for t in types if matches_tokens(query, t.display_name, t.name)],
        label_of=lambda code: by_name[code].display_name if code in by_name else code,
    )


@dataclass
class FieldHop:
    """One traversal step: the link field followed, and the type it landed on."""

    #: Field code on the type the hop leaves.
    name: str
    display_name: str
    #: Type the hop lands on.
    through: str


def field_path_of(hops: Sequence[FieldHop], name: str) -> str:
    """`entity.Shot.code`: every hop names the type it travels through (field_types/entity)."""
    parts: list[str] = []
    for hop in hops:
        parts.extend([hop.name, hop.through])
    parts.append(name)
    return ".".join(parts)


def path_types(root_type: str, hops: Sequence[FieldHop]) -> list[str]:
    """The type each hop landed on, root first. A type already here is not descended into again."""
    return [root_type, *[hop.through for hop in hops]]


def current_type(root_type: str, hops: Sequence[FieldHop]) -> str:
    """The type a picker is reading fields from after these hops."""
    return hops[-1].through if len(hops) > 0 else root_type


def friendly_field_path(segments: Sequence[PathSegment], separator: str = " › ") -> str:
    """A resolved path as a person reads it."""
    return separator.join(segment.display_name for segment in segments)


@dataclass
class ExtraField:
    """A column a data source computes, offered alongside the real fields."""

    #: The value emitted when it is chosen.
    name: str
    display_name: str | None = None


#: How many hops a path may take unless a caller says otherwise.
DEFAULT_MAX_DEPTH = 2


@dataclass
class FieldPickerRestrictions:
    """What a field picker offers, as a widget holds it."""

    #: Allow descending through entity fields. Off by default.
    deep_links: bool = False
    #: How many hops a path may take. Default 2.
    max_depth: int = DEFAULT_MAX_DEPTH
    #: Data types a field must have to be selected. Traversal ignores this.
    data_types: str | list[str] | None = None
    #: A field is selectable only if it declares link targets and one of them is here. Traversal ignores this.
    valid_types: list[str] | None = None
    #: Full dotted paths to drop, so a root field and the same name behind a hop are separate.
    exclude: list[str] | None = None
    #: Dotted prefixes to drop, along with everything beneath them.
    hide_paths: list[str] | None = None
    #: Drop types the API refuses in a filter (017_filter_operators).
    filterable_only: bool = False
    #: Synthetic entries offered at the root only. They bypass `data_types` and `valid_types`.
    extra_fields: list[ExtraField] | None = None
    #: Caller's own visibility test, receiving the schema and the candidate's full path.
    filter: Callable[[FieldSchema, str], bool] | None = None


@dataclass
class FieldOption:
    #: Full dotted path from the root type. This is the emitted value.
    path: str
    #: Field code on the type it lives on.
    name: str
    display_name: str
    data_type: str
    #: The row may be chosen as the value.
    selectable: bool
    #: The row descends.
    traversable: bool
    #: Types a traversable row may descend into, minus the ones already on the path.
    targets: list[str]
    #: A synthetic entry rather than a schema field.
    computed: bool


@dataclass
class FieldOptionsInput:
    """One derivation: where the picker stands, and the restrictions it is under."""

    root_type: str
    #: Hops already taken. Empty at the root.
    hops: list[FieldHop] = dc_field(default_factory=list)
    deep_links: bool = False
    max_depth: int = DEFAULT_MAX_DEPTH
    data_types: str | list[str] | None = None
    valid_types: list[str] | None = None
    exclude: list[str] | None = None
    hide_paths: list[str] | None = None
    filterable_only: bool = False
    extra_fields: list[ExtraField] | None = None
    filter: Callable[[FieldSchema, str], bool] | None = None


def _as_set(value: str | list[str] | None) -> set[str] | None:
    if value is None:
        return None
    items = [value] if isinstance(value, str) else value
    return set(items) if len(items) > 0 else None


def traversal_targets(field: FieldSchema, input: FieldOptionsInput) -> list[str]:
    """The types a field may be descended into from here.

    Only a single `entity` field: a dotted path through a `multi_entity` field reads
    back nothing, 200 with the key absent from `attributes` (probe 016). A type already
    on the path is dropped, so `project.Project.users.HumanUser.projects` cannot loop.
    """
    if not input.deep_links:
        return []
    if field.data_type != "entity":
        return []
    hops = input.hops
    if len(hops) >= input.max_depth:
        return []
    visited = set(path_types(input.root_type, hops))
    return [t for t in (field.valid_types or []) if t not in visited]


def derive_field_options(fields: dict[str, FieldSchema], input: FieldOptionsInput) -> list[FieldOption]:
    """The rows a field picker shows for one type at one depth.

    `data_types` and `valid_types` bind what may be selected; a link field stays on the
    list so a restricted picker can still reach a nested field of the wanted type. Every
    other restriction hides the row outright and is measured against the full dotted
    path, so excluding a root field leaves the same name behind a hop alone. Computed
    entries come first, then the schema fields by display name.
    """
    hops = input.hops
    at_root = len(hops) == 0
    wanted_types = _as_set(input.data_types)
    wanted_targets = _as_set(input.valid_types)
    excluded = set(input.exclude or [])
    hidden = input.hide_paths or []

    options: list[FieldOption] = []

    if at_root:
        for extra in input.extra_fields or []:
            options.append(FieldOption(
                path=extra.name,
                name=extra.name,
                display_name=extra.display_name if extra.display_name is not None else extra.name,
                data_type="",
                selectable=True,
                traversable=False,
                targets=[],
                computed=True,
            ))

    real: list[FieldOption] = []
    for name, field in fields.items():
        path = field_path_of(hops, name)
        if path in excluded:
            continue
        if any(path == prefix or path.startswith(f"{prefix}.") for prefix in hidden):
            continue
        if input.filterable_only and not is_filterable(field.data_type):
            continue
        if input.filter is not None and not input.filter(field, path):
            continue

        targets = traversal_targets(field, input)
        selectable = (
            (wanted_types is None or field.data_type in wanted_types)
            and (wanted_targets is None or any(t in wanted_targets for t in (field.valid_types or [])))
        )
        if not selectable and len(targets) == 0:
            continue

        real.append(FieldOption(
            path=path,
            name=name,
            display_name=field.display_name,
            data_type=field.data_type,
            selectable=selectable,
            traversable=len(targets) > 0,
            targets=targets,
            computed=False,
        ))
    # Ordered case-insensitively, the way the display names collate upstream.
    real.sort(key=lambda option: (option.display_name.casefold(), option.name.casefold()))

    return [*options, *real]


def search_field_options(options: Sequence[FieldOption], query: str) -> list[FieldOption]:
    """Rows matching the search box."""
    if not query.strip():
        return list(options)
    return [o for o in options if matches_tokens(query, o.display_name, o.name, o.data_type)]


def toggle_field_path(paths: Sequence[str], path: str) -> list[str]:
    """The list with `path` appended, or dropped when it is already there."""
    if path in paths:
        return [entry for entry in paths if entry != path]
    return [*paths, path]


def move_field_path(paths: Sequence[str], from_index: int, to_index: int) -> list[str]:
    """The list with the entry at `from_index` moved to `to_index`.

    An index off either end leaves the order alone.
    """
    next_paths = list(paths)
    if (
        from_index < 0
        or from_index >= len(next_paths)
        or to_index < 0
        or to_index >= len(next_paths)
        or from_index == to_index
    ):
        return next_paths
    moved = next_paths.pop(from_index)
    next_paths.insert(to_index, moved)
    return next_paths


# ---------------------------------------------------------------------------- #
# fixed field paths                                                            #
# ---------------------------------------------------------------------------- #

#: The sub-label of a row whose path the schema does not hold.
UNRESOLVED_PATH_LABEL = "not in the schema"


@dataclass
class FieldPathOption:
    """One row of a fixed list of paths: what a caller offered, read through the schema."""

    #: The path as the caller wrote it. This is the emitted value.
    path: str
    #: The resolved path, display names joined, or the raw path where the schema has no such path.
    label: str
    #: Code of the leaf field, empty where the path does not resolve.
    name: str
    #: Data type of the leaf field, empty where the path does not resolve.
    data_type: str
    #: The muted line under the label: the leaf's data type, or that the schema has no such path.
    sub_label: str
    #: The schema resolved the path.
    resolved: bool


def resolve_field_path_options(
    schema: SchemaService,
    root_type: str,
    paths: Sequence[str],
    options: PathLabelOptions | None = None,
) -> list[FieldPathOption]:
    """A caller's fixed list of paths as flat rows, in the order given.

    Each path is resolved through every type it travels and labelled as the picker
    labels a chosen value. A path the schema does not hold keeps its place and is
    marked, so a list of columns never comes back shorter than it went in.
    """
    rows: list[FieldPathOption] = []
    for path in paths:
        try:
            segments = schema.resolve_path(root_type, path)
        except Exception:
            rows.append(FieldPathOption(
                path=path,
                label=path,
                name="",
                data_type="",
                sub_label=UNRESOLVED_PATH_LABEL,
                resolved=False,
            ))
            continue
        leaf = segments[-1]
        rows.append(FieldPathOption(
            path=path,
            label=path_label(segments, options),
            name=leaf.name,
            data_type=leaf.data_type,
            sub_label=leaf.data_type,
            resolved=True,
        ))
    return rows


def search_field_path_options(options: Sequence[FieldPathOption], query: str) -> list[FieldPathOption]:
    """Rows matching the search box, read on what the row shows and on the path behind it."""
    if not query.strip():
        return list(options)
    return [o for o in options if matches_tokens(query, o.label, o.path)]
