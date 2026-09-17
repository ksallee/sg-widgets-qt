# docs

The widget, core and start pages, and the tables the showcase draws beside them. Three scripts
produce them from `~/dev/sg-widgets`. Nothing under `docs/widgets/`, `docs/core/` or `docs/start/`
is written by hand, with one exception named below.

## What produces what

| script | writes |
|---|---|
| `tools/export_props.mjs` | `docs/widgets/<name>.props.json`, `docs/widgets/_index.json` |
| `tools/export_docs.py` | `docs/widgets/<name>.md`, `docs/core/<name>.md`, `docs/start/<name>.md` |
| `tools/props_types.py` | the `py_type` of every prop row in `docs/widgets/*.props.json` |

## The commands

    cd ~/dev/sg-widgets && node ~/dev/sg-widgets-qt/tools/export_props.mjs
    cd ~/dev/sg-widgets && ~/dev/sg-widgets-qt/.venv/bin/python ~/dev/sg-widgets-qt/tools/export_docs.py
    .venv/bin/python tools/props_types.py

The type pass runs after the props export, and reruns over whatever is on disk. Either exporter
finds the upstream checkout in `SG_WIDGETS`, in the directory it was run from, or at
`~/dev/sg-widgets`.

## The props JSON

One file per upstream props file, the `extends` chain resolved by the upstream's own `_resolve.ts`:

    { "name", "page", "declares", "props": [], "events": [], "slots": [], "keyboard": [] }

`page` is the page the rows are drawn on, which differs from `name` for an item that shares a page
with another. A row carries `owner` where it comes from the item's base. Two names are changed for
Python: a prop name is snake_case (`labelField` is `label_field`) and an event name is a Qt signal
name (`onValueChange` is `value_changed`, `onOpenChange` is `open_changed`, `onError` is `error`).
A `class / className` row is dropped, a Svelte-only row is dropped, and a React-only row is kept
without the flag. Everything else is the upstream cell, verbatim.

`py_type` sits beside `type` and is a mechanical translation, not a decision: `string` is `str`,
`X[]` is `list[X]`, `X | null` is `Optional[X]`, `Record<K, V>` is `dict[K, V]`, a literal union is
`Literal[...]`, a function is `Callable[...]`, and `EntityRef`, `SgContext`, `FilterGroup`,
`WireGroup`, `CollectionColumn` and `PickerRow` stay as they are. `number` is `int` where the
meaning counts something, `float` where it is a fraction, and `int | float` otherwise. A callback
parameter with no type of its own is `Any`, except `row`, `query` and `open`.

`_index.json` is the sidebar: `start` and `core` page names, the widgets `overview` page, and
`widgets` as `[{ "category": "Foundations", "items": ["thumbnail", ...] }, ...]` in the order
`apps/site/astro.config.mjs` gives. A page outside the sidebar, such as a page that names a
renamed item, is exported but not listed.

## The pages

A `.md` page keeps its `title` and `description` as YAML, and its prose verbatim, including the
API behaviour section and its corpus citations. The Astro islands become directives the showcase
reads:

    ::demo{name="entity-picker" title="…"}
    ::props{name="entity-picker" kind="props"}

`kind` is one of `props`, `events`, `slots` and `keyboard`. The install block becomes the import
line, and a site link becomes a link to the page beside it.

A paragraph that speaks of React, Svelte, Base UI, Bits UI, shadcn or the registry is followed by
a line reading `::qt-note`. The prose is left as the upstream wrote it; the marker is where the Qt
docs pass writes what differs here.

## Editing, and what a rerun does

The `.md` pages are the exception to "generated, never edited": each one is generated once and then
edited, by the Qt docs pass that answers every `::qt-note`. A rerun therefore never overwrites a
page that is already there. Where the conversion differs from the page on disk, it is written to
`<name>.md.new` beside it and named on stdout, so the two are merged by hand and a Qt note survives
a sync.

The JSON files carry no hand edits and are overwritten on every run.
