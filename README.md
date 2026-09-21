# sg-widgets-qt

Flow Production Tracking (formerly ShotGrid) widgets for Qt: pickers, editors, tables, trees, grids
and search. For pipeline developers writing tools inside Maya, Houdini, Nuke, RV or a standalone
app.

![An entity table grouped by status, with status badges and thumbnails](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/entity-table-light.png)

## Install

```sh
pip install "sg-widgets-qt[pyside6]"
uv add "sg-widgets-qt[pyside6]"
```

Python 3.9 and up. `[pyqt5]` is the other extra; PyQt6 and PySide2 carry no extra and install by
name beside the package. PySide2 has no Apple Silicon wheel, so on an M-series Mac name one of the
other three.

Inside a DCC, install `sg-widgets-qt` on its own. Maya, Houdini, Nuke and RV import their own Qt
binding before your code runs, and a second binding in that interpreter breaks it. The package
brings `shotgun_api3` and `qtpy` and, without an extra, no binding at all.

Every Qt import here goes through [qtpy](https://github.com/spyder-ide/qtpy), so one widget runs on
PySide2, PySide6, PyQt5 and PyQt6, and on whichever of them the host imported first. Where more than
one is importable, `QT_API` picks.

## The showcase

```sh
sg-widgets-showcase
python -m sg_widgets_qt.showcase
```

Either line opens the same window: one page per widget, with a live demo, the props, signals, slots
and keyboard tables, and the docs prose. The pages ship inside the package, so it needs no checkout.
The demos run on the mock, so it needs no site; its toolbar offers Live where the three values below
are set.

## A first widget

The mock site is generated in process, so this block runs on a fresh install with no credentials and
no network.

```python
import os

from qtpy.QtWidgets import QApplication

from sg_widgets_core import MockClient, create_sg_context
from sg_widgets_qt.widgets.entity_picker import EntityPicker

app = QApplication([])
context = create_sg_context(MockClient())
picker = EntityPicker(entity_types=["Shot"], context=context)
picker.value_changed.connect(lambda ref, row: print(ref))
picker.show()
if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
    app.exec()
```

The context is built once and handed to every widget. Swapping the mock for a site is the client
line alone. `ShotgunClient.from_env()` needs three environment values: `FPT_API_SITE_URL`,
`FPT_API_SCRIPT_NAME` and `FPT_API_API_KEY`.

```python
# Needs a site: FPT_API_SITE_URL, FPT_API_SCRIPT_NAME and FPT_API_API_KEY.
from sg_widgets_core import ShotgunClient, create_sg_context
from sg_widgets_qt.widgets.entity_picker import EntityPicker

context = create_sg_context(ShotgunClient.from_env())
picker = EntityPicker(entity_types=["Shot"], context=context)
```

## The widgets

| | |
|---|---|
| ![An entity multi picker open on its results](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/entity-multi-picker-light.png) | A picker searches the site, holds what was ticked as chips, and emits references. |
| ![A filter editor holding one status condition](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/filter-editor-light.png) | The filter editor builds a condition tree and serialises it for the API. |
| ![A status picker open on the statuses of one project](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/status-picker-light.png) | Statuses carry the site's own names, codes, colours and icons, per project. |
| ![Global search, its results grouped by entity type](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/global-search-light.png) | Global search reads across entity types and marks what matched. |
| ![An entity grid of thumbnails](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/entity-grid-light.png) | A table, a grid and a tree page a set, sort it, group it and edit a cell. |
| ![The entity table in the dark theme](https://raw.githubusercontent.com/ksallee/sg-widgets-qt/main/docs/screenshots/entity-table-dark.png) | Every widget wears a light and a dark theme, or the host application's palette. |

Every shot above reads a live site. [One page per
widget](https://github.com/ksallee/sg-widgets-qt/tree/main/docs/widgets) says what each one takes
and emits, beside
[the introduction](https://github.com/ksallee/sg-widgets-qt/blob/main/docs/start/introduction.md),
[install](https://github.com/ksallee/sg-widgets-qt/blob/main/docs/start/install.md) and
[the core](https://github.com/ksallee/sg-widgets-qt/blob/main/docs/core/index.md).

## How it relates to sg-widgets

This is a port of [sg-widgets](https://github.com/ksallee/sg-widgets), whose React and Svelte
widgets carry the same names, props and behaviour, and whose
[documentation site](https://sg-widgets.vercel.app) is the reference for what a widget does; the
pages here say where Qt or Python forced a difference. The framework-neutral half comes with it as
`sg_widgets_core`, which holds the field data types, the operator vocabularies, the filter tree,
status logic, the formatters, the parsers, the client protocol and a generated mock site, and
imports no Qt, so it runs in a farm job as well as in a window. What either repo claims about the
API is measured in [sg-groundtruth](https://github.com/ksallee/sg-groundtruth) and cited where it
is relied on.

## Status

Alpha. 45 widgets, 30 core modules and 51 documentation pages are complete, on Python 3.9 through
3.13 and on Qt 5.15 and Qt 6. Both packages carry `py.typed`. Names, props and signals can still
change between 0.x releases, and the
[changelog](https://github.com/ksallee/sg-widgets-qt/blob/main/CHANGELOG.md) records what changed.
Ask for a widget, report a defect or say what reads wrong in the
[issues](https://github.com/ksallee/sg-widgets-qt/issues).

## Licence

MIT. See [LICENSE](https://github.com/ksallee/sg-widgets-qt/blob/main/LICENSE).
