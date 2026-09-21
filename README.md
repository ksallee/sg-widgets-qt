# sg-widgets-qt

Flow Production Tracking (formerly ShotGrid) widgets for Qt: pickers, editors, tables, trees, grids
and search, for Python 3.9 and up. Qt comes through [qtpy](https://github.com/spyder-ide/qtpy), so
one widget runs on PySide2, PySide6, PyQt5 and PyQt6, and a site is read through `shotgun_api3`.

![The showcase, with an entity table grouped by status](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/shots/states/entity-table-grouped.png)

| package | what |
|---|---|
| `sg_widgets_core` | Headless. Field data types and operator vocabularies, the filter tree, status logic, formatters, parsers, the client protocol, the shotgun_api3 client and a mock site. No Qt. |
| `sg_widgets_qt` | The theme (tokens, palettes, light and dark, host palette), the primitives, the widgets, and the showcase. |

Both packages carry `py.typed`, so a type checker reads their annotations.

## Install

```sh
pip install sg-widgets-qt              # brings qtpy and shotgun_api3; a DCC brings Qt
pip install "sg-widgets-qt[pyside6]"   # outside a DCC
```

A DCC imports its binding before your code runs and qtpy binds to that one, so installing a second
binding into a DCC's interpreter is what breaks it.

The pages ship inside the package, so an installed showcase opens the same sidebar a checkout
does. Demos run on a generated mock site. `.env.local` with `FPT_API_SITE_URL`,
`FPT_API_SCRIPT_NAME` and `FPT_API_API_KEY`, in the working directory or above it, lets the
showcase read a live site instead.

## A widget

```python
from sg_widgets_core import MockClient, create_sg_context
from sg_widgets_qt.widgets.entity_picker import EntityPicker

context = create_sg_context(MockClient())
picker = EntityPicker(entity_types=["Shot"], context=context)
picker.value_changed.connect(lambda ref, row: print(ref))
```

`create_sg_context` takes `ShotgunClient(site_url, script_name, api_key)` for a site. The context is
built once and handed to every widget.

## The core alone

```python
from sg_widgets_core.filter import condition, group, to_api3_hash

active = group("and", [condition("sg_status_list", "is", "ip")])
to_api3_hash(active)  # {'logical_operator': 'and', 'conditions': [['sg_status_list', 'is', 'ip']]}
```

## The showcase

```sh
python -m sg_widgets_qt.showcase
```

One page per widget, with a demo, the props, signals, slots and keyboard tables, and the prose. The
demos run on a generated mock site, so it needs no credentials.

## Where it comes from

A port of [sg-widgets](https://github.com/ksallee/sg-widgets), whose React and Svelte widgets carry
the same names, props and behaviour. What the core claims about the API is measured in
[sg-groundtruth](https://github.com/ksallee/sg-groundtruth), and every claim is cited where it is
relied on.

## Maturity

Alpha. Names, props and signals can still change between 0.x releases. The
[changelog](https://github.com/ksallee/sg-widgets-qt/blob/main/CHANGELOG.md) records what changed
and the [issues](https://github.com/ksallee/sg-widgets-qt/issues) what is open.

## Docs

[Introduction](https://github.com/ksallee/sg-widgets-qt/blob/main/docs/start/introduction.md),
[install](https://github.com/ksallee/sg-widgets-qt/blob/main/docs/start/install.md),
[the core](https://github.com/ksallee/sg-widgets-qt/blob/main/docs/core/index.md) and
[one page per widget](https://github.com/ksallee/sg-widgets-qt/tree/main/docs/widgets).

## Licence

MIT. See [LICENSE](https://github.com/ksallee/sg-widgets-qt/blob/main/LICENSE).
