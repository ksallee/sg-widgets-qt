"""The rows the demos name, read from the fixtures rather than written out.

The mock builds its rows from a seed, so a name typed into a demo goes stale the moment the
fixtures move under it. A demo names a row by type and id and takes the label from here.

    PRESET = ref("Asset", 1226)
"""
from __future__ import annotations

from typing import Any

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.filter import EntityRef, condition, group, to_api3_hash
from sg_widgets_core.mock import IDENTITY_FIELD, MOCK_NOW, MockClient

from ..context import MOCK_SEED

__all__ = ["label", "ref", "refs", "value"]

#: What labels a type whose identity field the mock does not name.
FALLBACK_FIELD = "name"

_CLIENT: Any = None
_LABELS: dict[str, dict[int, str]] = {}


def _fixtures() -> MockClient:
    """The same fixtures the demo context answers from, without its latency or its counting."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = MockClient(seed=MOCK_SEED, now=MOCK_NOW)
    return _CLIENT


def label(entity_type: str, id: int) -> str:
    """What the fixtures call that row, or an empty string where they hold no such row."""
    known = _LABELS.setdefault(entity_type, {})
    if id not in known:
        field = IDENTITY_FIELD.get(entity_type, FALLBACK_FIELD)
        found = _fixtures().search(
            entity_type,
            SearchOptions(
                fields=[field],
                filters=to_api3_hash(group("and", [condition("id", "is", id)])),
            ),
        )
        known[id] = str(found.data[0].values.get(field) or "") if found.data else ""
    return known[id]


def ref(entity_type: str, id: int) -> EntityRef:
    """The reference a demo shows for that row."""
    return EntityRef(type=entity_type, id=id, name=label(entity_type, id))


def refs(entity_type: str, *ids: int) -> list[EntityRef]:
    """Several references of one type, in the order the ids were given."""
    return [ref(entity_type, id) for id in ids]


def value(entity_type: str, id: int) -> dict[str, Any]:
    """The row in the shape the API sends it, for a field value."""
    return {"type": entity_type, "id": id, "name": label(entity_type, id)}
