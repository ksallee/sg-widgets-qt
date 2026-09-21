# Design

## Why a port

The widgets in `~/dev/sg-widgets` encode what the Flow Production Tracking API does, measured by
the sg-groundtruth corpus, behind one set of design rules. Pipeline tools in Maya, Houdini and
Nuke need the same widgets, in the Python and Qt those hosts ship.

## Stack

Python 3.9 as the floor: Maya 2023, Houdini 19.5 and Nuke 14 ship it. `qtpy` so one source runs
on PySide2 5.15, PySide6, PyQt5 and PyQt6. `shotgun_api3` because it is BSD licensed and runs on
every host Python; `fpt-api` is AGPL and stays out. `typing_extensions` on 3.9 and 3.10 for
`Self` and `TypeAlias`.

Dev: `uv`, `pytest`, `pytest-qt`, `pytest-timeout`, `ruff`. PySide6 6.7 is the last release for
3.9. PyQt5 stands in for PySide2 in the second environment because PySide2 ships no arm64 wheel.

## Two packages, one distribution

`sg_widgets_core` has no Qt import, so a farm script or a test can use the filter tree, the
formatters and the client. `sg_widgets_qt` holds the theme, the primitives, the widgets and the
showcase. One wheel, because a DCC install is one `pip install`.

The showcase draws its pages from `docs/`, which is where they are written and where
`tools/export_docs.py` writes them. The wheel copies `docs/widgets`, `docs/core` and `docs/start`
to `sg_widgets_qt/_docs`, so an installed showcase opens the sidebar a checkout opens.
`sg_widgets_qt.showcase.paths` reads the package copy through `importlib.resources` and falls back
to the checkout's `docs/`. It also resolves `.env.local` from the working directory upward, because
nothing above `site-packages` belongs to the person running the showcase.

## Threads

`shotgun_api3.Shotgun` is not thread-safe. `ShotgunClient` keeps one connection per thread. The Qt
layer runs every read on `QThreadPool` and hands the answer back through a signal; a ticket per
query drops an answer a newer query replaced.

## Sync

`sync/manifest.json` is the ledger: per item, the upstream files it ports and their content hash
at the upstream commit last synced. `tools/sync_status.py` diffs it against the checkout;
`/sync` ports what drifted.
