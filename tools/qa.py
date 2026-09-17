#!/usr/bin/env python
"""Drive the showcase headless and print only what was asked for.

    .venv/bin/python tools/qa.py --page entity-picker --shot shots/entity-picker-light.png
    .venv/bin/python tools/qa.py --page status-badge --dark --palette nova --drive drive.py
    .venv/bin/python tools/qa.py --page hello --qt5 --shot shots/hello-qt5.png

The port of the upstream `tools/qa.mjs`. The window runs in this process on the offscreen
platform, unless `--headed` asks for a real one. The flags set the view before the first paint;
a drive changes it afterwards through `prefs`.

A drive file defines one function:

    def drive(page, wait, find, prefs) -> dict

`page` is the `WidgetPage` on show, `wait(ms)` spins the event loop, `find(name_or_type)` searches
the page's widget tree by object name or by class, and `prefs` sets the view live. Whatever it
returns is printed as JSON under `result`, beside `console`, which counts what Qt logged. The exit
code is 1 when the drive raised, when Qt logged a critical, or when `verdict` starts with FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QT5_PYTHON = ROOT / ".venv-qt5" / "bin" / "python"

#: How long the driver waits for every stage on a page to report ready.
READY_TIMEOUT_MS = 30000


def parser() -> argparse.ArgumentParser:
    made = argparse.ArgumentParser(prog="tools/qa.py", description=__doc__.splitlines()[0])
    made.add_argument("--page", default="", help="the page to open; the widgets overview by default")
    made.add_argument("--shot", default="", help="write a screenshot here")
    made.add_argument("--viewport", default="1200x900", help="the window size, WIDTHxHEIGHT")
    made.add_argument("--drive", default="", help="a python file defining drive(page, wait, find, prefs)")
    made.add_argument("--timeout", type=int, default=60000, help="milliseconds before the run gives up")
    made.add_argument("--palette", default="", help="the palette to wear")
    made.add_argument("--radius", default="", help="the corner radius to wear")
    made.add_argument("--size", default="", help="the size step the demos wear")
    made.add_argument("--dark", action="store_true", help="the dark theme")
    made.add_argument("--reduced-motion", action="store_true", help="collapse motion to opacity")
    made.add_argument("--live", action="store_true", help="read the test site instead of the mock")
    made.add_argument("--project", type=int, default=None, help="the project the live demos read")
    made.add_argument("--qt5", action="store_true", help="run again on the PyQt5 environment")
    made.add_argument("--headed", action="store_true", help="a real platform instead of offscreen")
    return made


def rerun_on_qt5(argv: list[str]) -> int:
    """Run this driver again on `.venv-qt5`, with the rest of the flags."""
    if not QT5_PYTHON.is_file():
        sys.stderr.write("no .venv-qt5 at %s\n" % QT5_PYTHON)
        return 2
    rest = [flag for flag in argv if flag != "--qt5"]
    env = dict(os.environ)
    env["QT_API"] = "pyqt5"
    return subprocess.call([str(QT5_PYTHON), str(Path(__file__).resolve()), *rest], env=env)


class Console:
    """What Qt logged while the window was up."""

    def __init__(self) -> None:
        self.warnings = 0
        self.criticals = 0
        self.messages: list[str] = []

    def as_json(self) -> dict:
        return {
            "warnings": self.warnings,
            "criticals": self.criticals,
            "messages": self.messages[:40],
        }


def install_handler(console: Console) -> None:
    """Count Qt's warnings and criticals, and keep what they said."""
    from qtpy import QtCore

    def handler(mode: object, _context: object, message: str) -> None:
        name = str(mode).rsplit(".", 1)[-1]
        if "Critical" in name or "Fatal" in name:
            console.criticals += 1
            console.messages.append("critical: " + message)
        elif "Warning" in name:
            console.warnings += 1
            console.messages.append("warning: " + message)

    QtCore.qInstallMessageHandler(handler)


def load_drive(path: str) -> object:
    """The `drive` function of a drive file, or of standard input for `-`."""
    source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    namespace: dict = {"__name__": "sg_qa_drive", "__file__": path}
    exec(compile(source, path if path != "-" else "<stdin>", "exec"), namespace)
    found = namespace.get("drive")
    if not callable(found):
        raise ValueError("the drive file defines no drive(page, wait, find, prefs)")
    return found


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(raw)
    if args.qt5:
        return rerun_on_qt5(raw)

    if not args.headed:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")
    sys.path.insert(0, str(ROOT / "src"))

    width, _, height = args.viewport.partition("x")
    try:
        size = (int(width), int(height))
    except ValueError:
        sys.stderr.write("unreadable viewport %r\n" % args.viewport)
        return 2

    from qtpy import QtCore, QtWidgets

    console = Console()
    install_handler(console)

    from sg_widgets_qt.showcase.prefs import Prefs
    from sg_widgets_qt.showcase.window import ShowcaseWindow

    overrides: dict = {}
    if args.dark:
        overrides["theme"] = "dark"
    if args.palette:
        overrides["palette"] = args.palette
    if args.radius:
        overrides["radius"] = args.radius
    if args.size:
        overrides["size"] = args.size
    if args.reduced_motion:
        overrides["motion"] = "reduced"
    if args.live:
        overrides["source"] = "live"

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    # The driver never writes the developer's own view.
    prefs = Prefs(persist=False, **overrides)
    window = ShowcaseWindow(prefs=prefs, project_id=args.project)
    window.resize(*size)
    window.show()

    def wait(ms: int = 0) -> None:
        """Spin the event loop for `ms`."""
        deadline = time.monotonic() + max(0, ms) / 1000.0
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 10)
        while time.monotonic() < deadline:
            app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 10)
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 10)

    out: dict = {"page": "", "viewport": args.viewport}
    failed = False
    try:
        page = window.open_page(args.page)
        out["page"] = window.current
        wait(50)
        deadline = time.monotonic() + min(args.timeout, READY_TIMEOUT_MS) / 1000.0
        while not page.ready and time.monotonic() < deadline:
            wait(50)
        out["ready"] = page.ready
        wait(50)

        def find(what: object, all: bool = False) -> object:
            """The widgets of the page tree with that object name, or of that class."""
            if isinstance(what, str):
                found = [
                    widget
                    for widget in page.findChildren(QtWidgets.QWidget)
                    if widget.objectName() == what
                ]
                if page.objectName() == what:
                    found.insert(0, page)
            else:
                found = list(page.findChildren(what))  # type: ignore[arg-type]
            return found if all else (found[0] if found else None)

        if args.drive:
            answer = load_drive(args.drive)(page, wait, find, prefs)  # type: ignore[operator]
            out["result"] = answer if isinstance(answer, dict) else {"value": answer}
        else:
            out["result"] = {}

        if args.shot:
            target = Path(args.shot)
            target.parent.mkdir(parents=True, exist_ok=True)
            wait(120)
            window.grab().save(str(target))
            out["shot"] = str(target)
    except Exception as error:
        out["error"] = "%s: %s" % (type(error).__name__, error)
        failed = True

    out["console"] = console.as_json()
    verdict = out.get("result", {}).get("verdict")
    if isinstance(verdict, str) and verdict.startswith("FAIL"):
        failed = True
    if console.criticals:
        failed = True
    window.close()
    sys.stdout.write(json.dumps(out, indent=2, default=str) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
