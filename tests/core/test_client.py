"""Port of `packages/core/test/client.test.ts`.

The tests that drive `RestClient` upstream are in `test_shotgun_client.py`: the
REST implementation is not ported, and the `shotgun_api3` adapter carries those
behaviours.
"""
from __future__ import annotations

from typing import Any

from sg_widgets_core.client import normalize_hierarchy_node


class TestNormalizeHierarchyNode:
    def test_keeps_one_child_when_expand_repeats_the_no_sequence_bucket_after_every_group(self) -> None:
        bucket = {
            "path": "/Project/91/Shot/sg_sequence/Sequence/__none__",
            "label": "Shots with no Sequence",
            "has_children": True,
            "ref": {"kind": "entity_type", "value": "Shot"},
        }

        def seq(id: int) -> dict[str, Any]:
            return {
                "path": f"/Project/91/Shot/sg_sequence/Sequence/{id}",
                "label": str(id),
                "has_children": True,
                "ref": {"kind": "entity", "value": {"type": "Sequence", "id": id}},
            }

        node = normalize_hierarchy_node(
            {
                "path": "/Project/91/Shot",
                "label": "Shots",
                "has_children": True,
                "ref": {"kind": "entity_type", "value": "Shot"},
                "children": [seq(41), bucket, seq(307), bucket, seq(1362), bucket],
            },
            "/Project/91/Shot",
        )
        assert [c.path for c in node.children] == [
            "/Project/91/Shot/sg_sequence/Sequence/41",
            "/Project/91/Shot/sg_sequence/Sequence/__none__",
            "/Project/91/Shot/sg_sequence/Sequence/307",
            "/Project/91/Shot/sg_sequence/Sequence/1362",
        ]
