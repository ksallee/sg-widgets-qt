"""Adds a Python type beside every TypeScript type in the exported props tables.

A second pass over `docs/widgets/*.props.json`. Every prop row keeps its `type` and gains a
`py_type` next to it, translated mechanically: `string` is `str`, `X[]` is `list[X]`,
`X | null` is `Optional[X]`, a literal union is `Literal[...]`, a function is `Callable[...]`,
and the names the widgets share (`EntityRef`, `SgContext`, `FilterGroup`, `WireGroup`,
`CollectionColumn`, `PickerRow`) stay as they are. `number` is `int` where the meaning counts
something, `float` where it is a fraction, and `int | float` otherwise.

    .venv/bin/python tools/props_types.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WIDGETS = REPO / "docs" / "widgets"

PRIMITIVES = {
    "string": "str",
    "boolean": "bool",
    "unknown": "Any",
    "any": "Any",
    "void": "None",
    "never": "None",
    "null": "None",
    "undefined": "None",
    "object": "dict[str, Any]",
    "Error": "Exception",
    "Date": "str",
}

#: What an untyped callback parameter is called, where the name says its type.
PARAMS = {"row": "PickerRow", "query": "str", "open": "bool"}

FLOAT_MEANING = re.compile(r"\b(fraction|fractions|ratio|percent|percentage|opacity)\b", re.I)
INT_MEANING = re.compile(
    r"\b(rows?|chips?|levels?|hops?|decimals?|recents?|columns?|index|indices"
    r"|ids?|milliseconds|pixels?|px|how many|page sizes?)\b",
    re.I,
)
INT_SUFFIX = (
    "_ms",
    "_id",
    "_ids",
    "_depth",
    "_length",
    "_size",
    "_sizes",
    "_limit",
    "_lines",
    "_count",
    "_counts",
    "_index",
    "_values",
)
INT_NAMES = {"rows", "lines", "index", "count", "size", "precision", "page"}

PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">"}


def split_top(text: str, separator: str) -> list[str]:
    """Splits on a separator that is not inside brackets or quotes."""
    parts: list[str] = []
    depth = 0
    quote = ""
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char in PAIRS:
            depth += 1
        elif char in ")]}>":
            # The `>` of an arrow closes nothing.
            if not (char == ">" and index and text[index - 1] == "="):
                depth -= 1
        elif depth == 0 and text.startswith(separator, index):
            parts.append(text[start:index])
            index += len(separator)
            start = index
            continue
        index += 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def is_wrapped(text: str, opener: str) -> bool:
    """True where the whole expression sits inside one pair of brackets."""
    closer = PAIRS[opener]
    if not text.startswith(opener) or not text.endswith(closer):
        return False
    depth = 0
    for index, char in enumerate(text):
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index == len(text) - 1
    return False


def number_type(name: str, meaning: str) -> str:
    if FLOAT_MEANING.search(meaning):
        return "float"
    if name.endswith(INT_SUFFIX) or name in INT_NAMES or INT_MEANING.search(meaning):
        return "int"
    return "int | float"


def function_type(text: str, name: str, meaning: str) -> str | None:
    parts = split_top(text, "=>")
    if len(parts) < 2:
        return None
    params, returns = parts[0], "=>".join(parts[1:])
    if not is_wrapped(params, "("):
        return None
    arguments = []
    for param in split_top(params[1:-1], ","):
        param = param.lstrip(".").strip()
        label, sep, typed = param.partition(":")
        if sep:
            arguments.append(translate(typed, name, meaning))
        else:
            arguments.append(PARAMS.get(label.strip().rstrip("?"), "Any"))
    return "Callable[[{}], {}]".format(", ".join(arguments), translate(returns, name, meaning))


def object_type(text: str, name: str, meaning: str) -> str:
    """An inline object is a dict: its value type where the fields agree, `Any` otherwise."""
    values = set()
    for field in split_top(text[1:-1], ";"):
        for entry in split_top(field, ","):
            _, sep, typed = entry.partition(":")
            values.add(translate(typed, name, meaning) if sep else "Any")
    return "dict[str, {}]".format(values.pop() if len(values) == 1 else "Any")


def generic_type(text: str, name: str, meaning: str) -> str | None:
    match = re.match(r"^([A-Za-z_][\w.]*)<(.*)>$", text, re.S)
    if not match:
        return None
    head, inside = match.group(1), match.group(2)
    arguments = [translate(part, name, meaning) for part in split_top(inside, ",")]
    if head == "Record":
        return "dict[{}]".format(", ".join(arguments))
    if head == "Promise":
        # Core is synchronous here, so a promise is what it answers.
        return arguments[0] if arguments else "Any"
    if head in ("Array", "ReadonlyArray"):
        return "list[{}]".format(arguments[0] if arguments else "Any")
    return "{}[{}]".format(head, ", ".join(arguments))


def union_type(members: list[str], name: str, meaning: str) -> str:
    literals = [member for member in members if re.fullmatch(r"'[^']*'", member)]
    if len(literals) == len(members):
        return "Literal[{}]".format(", ".join(literals))
    rest = [member for member in members if member not in ("null", "undefined")]
    translated = " | ".join(translate(member, name, meaning) for member in rest)
    if len(rest) < len(members):
        return f"Optional[{translated}]" if translated else "None"
    return translated


def translate(text: str, name: str, meaning: str) -> str:
    text = text.strip()
    if not text:
        return "Any"
    # An arrow binds looser than a union, so a return type is read before a `|` is.
    function = function_type(text, name, meaning)
    if function:
        return function
    members = split_top(text, "|")
    if len(members) > 1:
        return union_type(members, name, meaning)
    if is_wrapped(text, "("):
        return translate(text[1:-1], name, meaning)
    if text.endswith("[]"):
        return f"list[{translate(text[:-2], name, meaning)}]"
    if is_wrapped(text, "["):
        return "tuple[{}]".format(
            ", ".join(translate(part, name, meaning) for part in split_top(text[1:-1], ","))
        )
    if is_wrapped(text, "{"):
        return object_type(text, name, meaning)
    generic = generic_type(text, name, meaning)
    if generic:
        return generic
    if re.fullmatch(r"'[^']*'", text):
        return f"Literal[{text}]"
    if text in ("true", "false"):
        return f"Literal[{text.capitalize()}]"
    if text == "number":
        return number_type(name, meaning)
    if text in PRIMITIVES:
        return PRIMITIVES[text]
    if re.fullmatch(r"[A-Z][\w.]*", text):
        return text
    return "Any"


def py_type(ts_type: str, name: str, meaning: str) -> str:
    """The Python type for one `type` cell, backtick-wrapped as the cell is."""
    parts: list[tuple[bool, str]] = []
    for chunk in re.split(r"(`[^`]*`)", ts_type):
        if chunk.startswith("`") and chunk.endswith("`") and len(chunk) > 1:
            parts.append((True, translate(chunk[1:-1], name, meaning)))
        elif chunk:
            parts.append((False, chunk))
    if not any(quoted for quoted, _ in parts):
        return ts_type
    return "".join(f"`{body}`" if quoted else body for quoted, body in parts)


def main() -> int:
    files = sorted(WIDGETS.glob("*.props.json"))
    if not files:
        raise SystemExit("No props tables in docs/widgets. Run tools/export_props.mjs first.")
    rows = 0
    for path in files:
        table = json.loads(path.read_text(encoding="utf-8"))
        for row in table.get("props") or []:
            if "type" not in row:
                continue
            meaning = row.get("meaning") or ""
            typed = py_type(row["type"], row["name"], meaning)
            keys = [key for key in row if key != "py_type"]
            values = {key: row[key] for key in keys}
            row.clear()
            for key in keys:
                row[key] = values[key]
                if key == "type":
                    row["py_type"] = typed
            rows += 1
        path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{rows} rows in {len(files)} tables carry a py_type")
    return 0


if __name__ == "__main__":
    sys.exit(main())
