"""Every row a demo names is a row the mock holds, under the name the mock gives it."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sg_widgets_qt.showcase.demos import _rows

DEMOS = Path(_rows.__file__).parent

#: The keys an entity value carries, and nothing else. A url or an attachment value names a
#: file rather than a row, and carries more keys than these three.
ROW_KEYS = {"type", "id", "name"}


def demo_files() -> list[str]:
    return sorted(path.name for path in DEMOS.glob("*.py"))


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def _from_call(node: ast.Call) -> tuple:
    """The type, id and name an `EntityRef(...)` call spells out, where all three are literal."""
    name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
    if name != "EntityRef":
        return ()
    given = dict(zip(("type", "id", "name"), node.args))
    given.update({kw.arg: kw.value for kw in node.keywords if kw.arg})
    return tuple(_literal(given[key]) if key in given else None for key in ("type", "id", "name"))


def _from_dict(node: ast.Dict) -> tuple:
    """The same three, where a demo writes the row the way the API sends it."""
    row = _literal(node)
    if not isinstance(row, dict) or set(row) != ROW_KEYS:
        return ()
    return (row["type"], row["id"], row["name"])


def named_rows(source: str) -> list[tuple[str, int, str]]:
    """Every row a demo names, whatever it names it in."""
    found: list[tuple[str, int, str]] = []
    for node in ast.walk(ast.parse(source)):
        row = ()
        if isinstance(node, ast.Call):
            row = _from_call(node)
        elif isinstance(node, ast.Dict):
            row = _from_dict(node)
        if len(row) == 3 and isinstance(row[0], str) and isinstance(row[1], int) and row[2]:
            found.append((row[0], row[1], str(row[2])))
    return found


@pytest.mark.parametrize("file_name", demo_files())
def test_a_demo_names_its_rows_the_way_the_mock_does(file_name: str) -> None:
    source = (DEMOS / file_name).read_text(encoding="utf-8")
    for entity_type, entity_id, shown in named_rows(source):
        assert _rows.label(entity_type, entity_id) == shown, f"{entity_type} {entity_id}"
