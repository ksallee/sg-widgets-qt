"""The showcase, as a command.

    python -m sg_widgets_qt.showcase
    python -m sg_widgets_qt.showcase --page entity-picker --dark --palette nova
    python -m sg_widgets_qt.showcase --live --project 70

The flags set the view for this run and are the same names `tools/qa.py` takes. What the toolbar
changes afterwards is kept in `QSettings` for the next run.
"""
from __future__ import annotations

import argparse
import sys

__all__ = ["main", "parser"]

#: What a run with no Qt binding says, in place of the traceback qtpy raises out of the first
#: import of QtWidgets.
NO_BINDING = (
    'No Qt binding is importable: install one with pip install "sg-widgets-qt[pyside6]" '
    'or pip install "sg-widgets-qt[pyqt5]".'
)


def parser() -> argparse.ArgumentParser:
    """The command line."""
    from ..theme import PALETTES, RADII

    made = argparse.ArgumentParser(
        prog="python -m sg_widgets_qt.showcase",
        description="The widget showcase: one page per widget, with a live demo.",
    )
    made.add_argument("--page", default="", help="the page to open; the widgets overview by default")
    made.add_argument("--dark", action="store_true", help="open in the dark theme")
    made.add_argument("--palette", choices=list(PALETTES), help="the palette to wear")
    made.add_argument("--radius", choices=list(RADII), help="the corner radius to wear")
    made.add_argument("--reduced-motion", action="store_true", help="collapse motion to opacity")
    made.add_argument("--size", choices=("sm", "md", "lg"), help="the size step the demos wear")
    made.add_argument("--live", action="store_true", help="read the test site instead of the mock")
    made.add_argument("--project", type=int, default=None, help="the project the live demos read")
    return made


def overrides(args: argparse.Namespace) -> dict:
    """The flags, as the pref keys they set."""
    out: dict = {}
    if args.dark:
        out["theme"] = "dark"
    if args.palette:
        out["palette"] = args.palette
    if args.radius:
        out["radius"] = args.radius
    if args.reduced_motion:
        out["motion"] = "reduced"
    if getattr(args, "size", None):
        out["size"] = args.size
    if args.live:
        out["source"] = "live"
    return out


def main(argv: list[str] | None = None) -> int:
    """Open the showcase and run it, or say which extra to install and stop."""
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except Exception as exc:
        # qtpy raises this before its own exception class can be imported, so the name is the
        # only handle on it.
        if type(exc).__name__ != "QtBindingsNotFoundError":
            raise
        print(NO_BINDING, file=sys.stderr)
        return 1


def run(argv: list[str]) -> int:
    """Open the showcase on a binding qtpy found."""
    args = parser().parse_args(argv)
    from qtpy import QtWidgets

    from .prefs import Prefs
    from .window import ShowcaseWindow

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv[:1])
    prefs = Prefs(**overrides(args))
    window = ShowcaseWindow(prefs=prefs, project_id=args.project)
    window.resize(1200, 900)
    if args.page:
        window.open_page(args.page)
    window.show()
    return int(app.exec_())


if __name__ == "__main__":
    raise SystemExit(main())
