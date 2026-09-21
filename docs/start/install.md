---
title: Install
description: How a host app installs the widgets, and how the showcase runs.
---

One command installs the widgets and the core.

```sh
pip install sg-widgets-qt
```

It brings qtpy and shotgun_api3. It brings no Qt binding, because the host supplies that one.

Maya, Houdini, Nuke and the other DCCs ship a Qt binding and import it before your code runs. qtpy
binds to the binding already imported, so a DCC needs nothing beyond the line above. Installing a
second binding into a DCC's interpreter is what breaks it.

Outside a DCC, name a binding as an extra.

```sh
pip install "sg-widgets-qt[pyside6]"
pip install "sg-widgets-qt[pyqt5]"
```

PySide2 and PyQt6 have no extra of their own. Install either by name beside the package. Where more
than one binding is importable, `QT_API` picks which one qtpy takes.

The showcase runs from the installed package.

```sh
python -m sg_widgets_qt.showcase
```

It holds one page per widget, with a demo, the props, signals, slots and keyboard tables, and the
prose. The pages ship inside the package, so the showcase needs no checkout. The demos run on
`MockClient`, so it needs no site.

The toolbar's source select offers Live when `.env.local` holds `FPT_API_SITE_URL`,
`FPT_API_SCRIPT_NAME` and `FPT_API_API_KEY`. That file is the working directory's, or the first one
above it; `SG_WIDGETS_QT_ENV_FILE` names another. Live mode reads the site those three name and
writes nothing. The file is read for those keys alone, and nothing prints their values.

Work on the package itself starts from a checkout.

```sh
uv venv --python 3.9 .venv && uv pip install -e . --group dev
uv run pytest
python tools/sync_status.py
```

The dev group brings pytest, pytest-qt and PySide6. `sync_status.py` lists what changed in
sg-widgets since the last port.
