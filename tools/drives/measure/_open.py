"""Leave the page with its surface open, so the shot beside it carries the popup.

The same `QA_MEASURE_OPEN` kinds `_pickers.py` takes, and nothing measured: `tools/qa.py` grabs
the window and every popup standing over it once the drive returns.

    QA_MEASURE_OPEN=picker .venv/bin/python tools/qa.py --page entity-picker \\
        --drive tools/drives/measure/_open.py --shot shots/entity-picker-open.png
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

#: `qa.py` execs a drive rather than importing it, so its neighbour is loaded by path.
_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("_sg_measure_pickers", _HERE / "_pickers.py")
_PICKERS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PICKERS)


def drive(page, wait, find, prefs) -> dict:
    opened = _PICKERS.open_it(page, wait, find)
    wait(400)
    return {"verdict": f"PASS open ({opened})", "opened": opened}
