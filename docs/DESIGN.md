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
pushes to `dev` and `main`. `.github/workflows/release.yml` builds, installs the wheel into a fresh
environment, imports both packages offscreen and uploads to PyPI by trusted publishing when a
GitHub release is published. No token is stored anywhere.

## Two packages, one distribution

`sg_widgets_core` has no Qt import, so a farm script or a test can use the filter tree, the
formatters and the client. `sg_widgets_qt` holds the theme, the primitives, the widgets and the
showcase. One wheel, because a DCC install is one `pip install`.

## Threads

`shotgun_api3.Shotgun` is not thread-safe. `ShotgunClient` keeps one connection per thread. The Qt
layer runs every read on `QThreadPool` and hands the answer back through a signal; a ticket per
query drops an answer a newer query replaced.

## Sync

`sync/manifest.json` is the ledger: per item, the upstream files it ports and their content hash
at the upstream commit last synced. `tools/sync_status.py` diffs it against the checkout;
`/sync` ports what drifted.
