# Porting conventions

How a TypeScript module, widget, demo, props file or docs page in `~/dev/sg-widgets` becomes its
Python counterpart here. One rule per difference. Where the rule is silent, port one for one.

## Names

| upstream | here |
|---|---|
| `packages/core/src/field-types.ts` | `src/sg_widgets_core/field_types.py` |
| `packages/core/test/field-types.test.ts` | `tests/core/test_field_types.py` |
| `packages/react/src/registry/sg/components/entity-picker.tsx` | `src/sg_widgets_qt/widgets/entity_picker.py` |
| `packages/react/src/components/ui/popover.tsx` | `src/sg_widgets_qt/primitives/popover.py` |
| `apps/site/src/demos/entity-picker/Demo.tsx` | `src/sg_widgets_qt/showcase/demos/entity_picker.py` |
| `apps/site/src/props/entity-picker.ts` | `docs/widgets/entity-picker.props.json` |
| `apps/site/src/content/docs/widgets/entity-picker.mdx` | `docs/widgets/entity-picker.md` |
| function `operatorsFor` | `operators_for` |
| class `MockClient` | `MockClient` |
| constant `NEGATING_OPERATORS` | `NEGATING_OPERATORS` |
| prop `labelField` | keyword `label_field` |
| event `onValueChange` | signal `value_changed` |
| slot / snippet `row` | a callable keyword `row_renderer`, or a subclass hook, as the widget's docs page says |
| React component `EntityPicker` | class `EntityPicker(QWidget)` |
| item name `entity-picker` | stays `entity-picker` in the manifest, the docs and the showcase |

Every module starts with `from __future__ import annotations`. `from .x import *` lines in a package `__init__` carry `# noqa: F403`.

## Types

| TypeScript | Python |
|---|---|
| `interface` describing options or a record the code builds | `@dataclass` with the same fields, defaults where upstream has `?` |
| `interface` describing a row the API answers | `@dataclass` too; `values: dict[str, Any]` where upstream has `attributes` plus `relationships` |
| `type X = 'a' \| 'b'` | `X = Literal['a', 'b']` and `X_VALUES: tuple[X, ...] = ('a', 'b')` |
| `Record<string, T>` | `dict[str, T]` |
| `T \| null`, `T \| undefined`, `T?` | `T \| None` in annotations (safe on 3.9 under `from __future__ import annotations`; ruff UP045 rejects `Optional`), default `None`. Never `T \| None` at runtime. |
| `unknown` | `Any` |
| `Promise<T>` | `T`. Core is synchronous. The Qt layer runs it on a worker. |
| `Map`, `Set` | `dict`, `set`; a `Map` whose order matters stays a `dict` |
| `Date` | ISO 8601 string as the API sends it; `datetime` only inside a formatter |
| `Error` subclass | `Exception` subclass with the same fields |
| `readonly` array | `tuple` in a constant, `list` in a field |
| `typeof x === 'string'` | `isinstance(x, str)` |
| `Object.entries` | `.items()` |
| `??` | `x if x is not None else y` |
| a closure returned by a factory | a class, or a closure; keep whichever reads like the upstream |
| `satisfies`, `as const` | nothing |

Row values. `EntityRow.values` is one flat map: the attributes, the relationships and any dotted
field under its literal key, which is what `shotgun_api3.find` answers and what `PickerRow.values`
already is upstream. A relationship value is `{'type': ..., 'id': ..., 'name': ...}` or a list of
them, or `None`. Where upstream reads `row.attributes[x]` or `row.relationships[x].data`, read
`row.values[x]`. Where upstream builds a row from `attributes` and `relationships`, build it from
one map.

Dates. The adapter turns every `datetime` shotgun_api3 answers into the ISO string the REST API
would have sent (`2026-03-04T12:00:00Z`) and a `date` into `2026-03-04`, so core stays on strings
like the upstream core. On a write the adapter turns them back.

Locale. `Intl.DateTimeFormat` and `Intl.NumberFormat` have no equal in the standard library.
`sg_widgets_core.render` formats with `locale` limited to the patterns in `LOCALES` (`en-US`,
`en-GB`, `fr-FR`, `de-DE`, `ja-JP`) and `time_zone` through `zoneinfo`. A locale not in the table
formats as `en-US`. The docs page for FieldValue says so.

## Client

`SgClient` is a `typing.Protocol` with the upstream methods in snake_case, synchronous.
`ShotgunClient` implements it on `shotgun_api3.Shotgun`; `MockClient` on generated fixtures. One
connection per thread, through `threading.local`, because a `Shotgun` object is not thread-safe.

| upstream | shotgun_api3 call |
|---|---|
| `entityTypes()` | `schema_entity_read()` |
| `fields(type, projectId?)` | `schema_field_read(type, project_entity=...)` |
| `fieldWithProject(type, field, projectId)` | `schema_field_read(type, field, project_entity)` |
| `search(type, {filters, fields, sort, page})` | `find(type, filters, fields, order, limit, page)`; `has_more` is `len(rows) == page.size` |
| `textSearch(text, entityTypes, page)` | `text_search(text, entity_types, project_ids, limit)` |
| `statuses()` | `find('Status', [], [...])` |
| `update(type, id, patch)` | `update(type, id, patch)` then `find_one` for the whole row |
| `hierarchyExpand(path)` | `nav_expand(path)` |
| `hierarchySearch(rootPath, entity)` | `nav_search_entity(root_path, entity)` |
| `summarize(type, options)` | `summarize(type, filters, summary_fields, grouping)` |
| `create(type, body)` | `create(type, body, return_fields)` |
| `upload(type, id, file)` | `upload` or `upload_thumbnail` |
| `threadContents(noteId, entityFields)` | `note_thread_read(note_id, entity_fields)` |
| `eventLog(options)` | `find('EventLogEntry', ...)` with `event_log_filters` |
| `following(userId, options)` | `following(user, project, entity_type)` |

Filters. The upstream wire shape `{logical_operator, conditions}` with `[path, relation, values]`
conditions is what `shotgun_api3` takes as a filter dict, so `to_filter_array` and the tree are
ported unchanged and handed to `find` as they are. A `WireCondition` stays a three-item list.

Not ported: `proxy-client.ts`, `proxy-handler.ts`, `session-auth.ts` (a browser proxy and the
App Session Launcher flow). `STATUS.md` lists them under Not ported with the reason.

## Tests

One pytest file per upstream test file. One test function per upstream `it`, same name in
snake_case, same inputs, same expected values, same corpus citation in a comment. A `describe`
block becomes a class or a prefix. Where a test depends on `Date.now`, the mock clock is `MOCK_NOW`
as upstream. Tests never reach the network.

## Widgets

A widget is a `QWidget` subclass. Its props are keyword arguments of `__init__` and properties
with the same names; every prop is also settable after construction through `set_<name>`. Events
are Qt signals named in past tense (`value_changed`, `open_changed`, `error`). A slot is a
callable keyword (`row_renderer`) or a method a subclass overrides, and the docs page names which.
The `class / className` prop becomes nothing: a caller styles through the theme.

`size` (`sm`, `md`, `lg`), `readonly`, `disabled`, `invalid`, `clearable`, `density` keep their
upstream names and meaning. `w-full` becomes an expanding horizontal size policy and no fixed
width.

The docs page for a widget is the upstream page with the install block replaced by the import
line and the framework notes replaced by Qt ones. Everything else stays, including the API
behaviour section and its citations.

## The manifest

After an item lands:

    python tools/sync_record.py <item> --upstream <path> [<path> ...] --ported <path> [<path> ...] --status complete|partial|skipped [--note "..."]

Upstream paths are relative to `~/dev/sg-widgets`, ported paths relative to this repo. The item
name is `core/<module>`, `primitives/<name>`, `widgets/<name>`, `demos/<name>`, `docs/<name>`.
