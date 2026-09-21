# sg-widgets-qt

Flow Production Tracking (ShotGrid) widgets for Qt: pickers, editors, tables, trees and search,
for Python 3.9+ on PySide2, PySide6, PyQt5 or PyQt6 through qtpy, reading the site through
shotgun_api3.

A port of [sg-widgets](https://github.com/ksallee/sg-widgets), whose core encodes what the REST
API does as measured by [sg-groundtruth](https://github.com/ksallee/sg-groundtruth). The widgets
here follow the same design rules and the same showcase: one page per widget, a live demo, the
props, signals and keyboard tables, and the docs.

| package | what |
|---|---|
| `sg_widgets_core` | Headless. Field data types and operator vocabularies, the filter tree, status logic, formatters, the client protocol, the shotgun_api3 client and the mock site. No Qt. |
| `sg_widgets_qt` | The theme (tokens, palettes, light and dark, host palette), the primitives, the widgets, and the showcase. |

## Install

    pip install sg-widgets-qt            # brings qtpy and shotgun_api3; your host brings Qt
    pip install "sg-widgets-qt[pyside6]" # outside a DCC

## Run the showcase

    python -m sg_widgets_qt.showcase

The pages ship inside the package, so an installed showcase opens the same sidebar a checkout
does. Demos run on a generated mock site. `.env.local` with `FPT_API_SITE_URL`,
`FPT_API_SCRIPT_NAME` and `FPT_API_API_KEY`, in the working directory or above it, lets the
showcase read a live site instead.

## Develop

    uv venv --python 3.9 .venv && uv pip install -e . --group dev
    uv run pytest
    python tools/sync_status.py     # what changed upstream since the last port

`CLAUDE.md` holds the rules, `docs/porting-conventions.md` how upstream maps here,
`docs/design-rules.md` the design system, `STATUS.md` what is ported.
