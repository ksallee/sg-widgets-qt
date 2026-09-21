# Design

## Why a port

The widgets in `~/dev/sg-widgets` encode what the Flow Production Tracking API does, measured by
the sg-groundtruth corpus, behind one set of design rules. Pipeline tools in Maya, Houdini and
Nuke need the same widgets, in the Python and Qt those hosts ship.

## Stack

Python 3.9 as the floor: Maya 2023, Houdini 19.5 and Nuke 14 ship it. `qtpy` so one source runs
on PySide2 5.15, PySide6, PyQt5 and PyQt6. `shotgun_api3` because it is BSD licensed and runs on
every host Python; `fpt-api` is AGPL and stays out. Those two are the whole runtime: annotations
are strings under `from __future__ import annotations`, so nothing here needs `typing_extensions`.

Dev: `uv`, `pytest`, `pytest-qt`, `pytest-timeout`, `ruff`. PySide6 6.7 is the last release for
3.9. PyQt5 stands in for PySide2 in the second environment because PySide2 ships no arm64 wheel.
`pytest-timeout` carries the two-minute per-test timeout in `pyproject.toml`: a widget waiting on
a signal that never comes fails rather than hanging a run.

## Publishing

`py.typed` in both packages, so a consumer's type checker reads the annotations. The wheel carries
the two packages, the icons and the fonts. The sdist carries what builds and checks that wheel and
nothing else: the screenshots under `shots/` and the qa drives under `tools/drives/` are most of
the tree and none of them is needed to build.

`.github/workflows/gates.yml` runs ruff and the suite on both bindings on every pull request and on
pushes to `dev` and `main`. It asks fontconfig for grayscale antialiasing first: where
fontconfig asks for subpixel rendering, a widget painting itself and the delegate painting the same
value rasterise one string two ways, and the face parity test reads that as drift. A Linux checkout
wants the same setting. `.github/workflows/release.yml` builds, installs the wheel into a fresh
environment, imports both packages offscreen and uploads to PyPI by trusted publishing when a
GitHub release is published. No token is stored anywhere.

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

Three pools, each four threads, so work of one kind never waits out work of another. Each stays
small because a site rate limits, and none of them is `QThreadPool.globalInstance()`, so a host
application's own work is untouched.

| pool | carries |
|---|---|
| `workers.default_pool()` | Schema reads, facet counts, field writes, the demos. |
| `entity_picker.search_pool()` | What a picker or a search types into. |
| `images.image_pool()` | Thumbnails, avatars and the status sprite. |

A page of rows asks for more pictures than any pool has threads, so the pictures read in a lane
of their own: a field write submitted behind a table of thumbnails still lands at once.

## Sync

`sync/manifest.json` is the ledger: per item, the upstream files it ports and their content hash
at the upstream commit last synced. `tools/sync_status.py` diffs it against the checkout;
`/sync` ports what drifted.
