---
title: Entity Tree
description: A lazy tree over a project's navigation hierarchy.
---

Walks the navigation tree the web interface draws, one level per call, from a project down to its
shots and assets.

## Install

```python
from sg_widgets_qt.widgets.entity_tree import EntityTree
```

::demo{name="entity-tree" title="Entity Tree: a project seeded open to one shot, with checkboxes, a search, a thumbnail variant, and the three sizes beside a button"}

```python
tree = EntityTree(
    context=context,
    root_path="/Project/70",
    seed_path="/Project/70/Shot/sg_sequence/Sequence/100/id/862",
    checkable=True,
    searchable=True,
)
tree.checked_changed.connect(store)
```

## Behaviour

A node opens when it is clicked, when Right is pressed on it, or when a seed path runs through it.
Opening reads one level and keeps it: a node closed and opened again costs nothing. The node being
read shows a spinner in place of its chevron. Every level runs on a worker and the rows it brings
cross back on a queued signal, so the tree never reads on the thread it draws on.

A checkbox propagates both ways. Checking a branch checks everything under it, including a level read
after the box was ticked. Unchecking one child leaves the branch `mixed`, and it returns to `checked`
once every child is checked again. Only nodes that stand for a row are reported.

Typing in the search input searches the whole project, not the nodes already loaded. Every row the
words match is placed in the tree, the branches above it are opened, matched rows are marked and the
rest are dimmed. Clearing the input, or pressing Escape in it, restores the tree as it was.

A whole branch opens at once on Alt-click or Cmd/Ctrl-click on its chevron, and on `*` for every
branch at the focus level. Both read `expand_depth` levels below the node, with the node marked busy
until every one of them is in.

Each level's rows are read once per type over the ids the level returned, so `sub_label_field`,
`secondary_field`, `thumbnail` and the status badge cost no read per row. `thumbnail` is `False` by default and hides the leading slot with it, so a row nobody asked a picture of sits its label straight after the chevron and the box.

The view is a `QTreeView` over a model of the rows the engine says are visible, so a collapse is
the engine dropping rows rather than the view hiding them, and the row is drawn by `picker_row`'s
delegate with the chevron in front of it. The `row` render prop is that delegate: a caller that
wants its own drawing subclasses the one the tree installs. A status takes the row's right-hand
slot, and a `secondary_field` of the caller's own takes it instead.

## Props

::props{name="entity-tree" kind="props"}

## Events

::props{name="entity-tree" kind="events"}

## Slots

::props{name="entity-tree" kind="slots"}

## Keyboard

The tree keeps one tab stop. Focus follows the cursor, and the row it sits on is the one that carries
`tabindex="0"`.

::props{name="entity-tree" kind="keyboard"}

A disabled node takes no keys and no click: the arrows and type-ahead step over it, and the cursor
never lands on it.

## API behaviour

`POST /hierarchy/_expand` answers one level: the node itself, and children carrying a label, a ref
and `has_children`, which says whether opening is worth a call. Walking a project is therefore one
call per node (post_hierarchy_expand).

That endpoint refuses the vendor content types every other POST on this API requires and accepts only
`application/json`. `seed_entity_field` is documented and ignored, so it is not sent
(post_hierarchy_expand).

Which levels a project has is the site's own navigation configuration, not a fixed hierarchy: the
probed site's shot path runs through the field name `sg_sequence` (post_hierarchy_search). `seed_path`
is followed by taking whichever child is a prefix of it, never by parsing the path.
`POST /hierarchy/_search` answers `incremental_path`, one entry per level, and that array is a seed
path as it stands (post_hierarchy_search).

A field name a type does not have is dropped at 200, so one list of names reads every type of a level
(probe 003). A row's status badge comes from whichever field of its type is a `status_list`; Project's
`sg_status` is a plain `list` with no Status row behind its values, so a project carries no badge
(entity_types/Project, probe 009).

Searching is two calls a query. `POST /entity/_text_search` matches a row when every
whitespace-separated word appears in its name or in the name of the row it links to, and answers at
most 25 rows a page (probe 053). It says nothing about where a row sits, and
`POST /hierarchy/_search` does not match words, so each hit is then asked for its own path
(post_hierarchy_search). The words are scoped to the project on every searched type that carries a
`project` field.

A grouping field with no rows hides every row under it: a project with shots and no sequences answers
`/Project/<id>/Shot` as one empty child and no bucket, although the `__none__` path under that level
answers all of them. The tree asks for that path instead of drawing the empty row, reading the field
it runs through off the 400 the endpoint answers a bogus segment. The two endpoints spell the bucket
differently — `<field>/<GroupType>/__none__` from `_expand`, `<field>/__none__` from `_search` — and a
seed path is followed in either spelling (064_hierarchy_expand_buckets, post_hierarchy_expand).

## Reference

The model is core's own, shared with the web widgets. headless-tree (`@headless-tree/core` 1.7.0) is the reference for the
lazy loader, the tri-state checkboxes and the type-ahead; Zag's tree-view (`@zag-js/tree-view` 1.43.3)
for the state model and the ARIA, including `aria-checked="mixed"` and the roving tab stop; ReUI's
Tree (ReUI 2.5.2) for the markup, the `--tree-indent` step and the row classes.
