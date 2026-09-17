"""The live reads run only when they are asked for by name.

`pytest` with no marker expression never reaches the network, whatever
`.env.local` holds.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

#: This suite. A `conftest` hook is handed every item pytest collected, not only the ones under
#: it, so the ones this file speaks for are the ones inside this directory.
HERE = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    if "live" in (config.getoption("-m") or ""):
        return
    held_back = pytest.mark.skip(reason="a live read runs only under -m live")
    for item in items:
        if HERE in Path(str(item.fspath)).resolve().parents:
            item.add_marker(held_back)
