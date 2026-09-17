"""The live reads run only when they are asked for by name.

`pytest` with no marker expression never reaches the network, whatever
`.env.local` holds.
"""
from __future__ import annotations

from typing import Any

import pytest


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    if "live" in (config.getoption("-m") or ""):
        return
    held_back = pytest.mark.skip(reason="a live read runs only under -m live")
    for item in items:
        item.add_marker(held_back)
