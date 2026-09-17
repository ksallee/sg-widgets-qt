"""Exports the upstream docs pages to Markdown for the Qt showcase.

Converts every `apps/site/src/content/docs/{widgets,core,start}/*.mdx` in ~/dev/sg-widgets
into `docs/<section>/<name>.md` here: the frontmatter keeps its title and description, the
Astro islands become `::demo` and `::props` directives, the install block becomes the Python
import line, and a site link becomes a link to the page beside it.

Prose is copied, never rewritten. A paragraph that speaks of React, Svelte, Base UI, Bits UI,
shadcn or the registry is followed by a `::qt-note` line, which is where the Qt docs pass
writes what differs here.

A page is generated once and then edited. Where a `.md` already exists and the conversion
differs from it, the conversion is written to `<name>.md.new` beside it and named on stdout,
so an edit survives a sync.

    .venv/bin/python tools/export_docs.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SECTIONS = ("widgets", "core", "start")

TAG = re.compile(r"<(Demo|Props)\b([^>]*?)/>")
ATTR = re.compile(r'([A-Za-z][\w-]*)="([^"]*)"')
ASTRO_IMPORT = re.compile(r"^import\s+\w+\s+from\s+'[^']*\.astro';\s*$")
FENCE = re.compile(r"^\s*(```+|~~~+)")
HEADING = re.compile(r"^#{1,6}\s")
LINK = re.compile(r"\]\((/(?:widgets|core|start)(?:/[^)\s]*)?)\)")
REGISTRY_ITEM = re.compile(r"/r/react/([a-z0-9-]+)\.json")
QT_WORDS = re.compile(r"\b(react|svelte|base\s+ui|bits\s+ui|shadcn|registry|registries)\b", re.I)


def upstream_root() -> Path:
    """The sg-widgets checkout: an override, the directory this was run from, or the default."""
    marker = "apps/site/src/content/docs/widgets/index.mdx"
    for candidate in (os.environ.get("SG_WIDGETS"), os.getcwd(), "~/dev/sg-widgets"):
        if not candidate:
            continue
        root = Path(candidate).expanduser()
        if (root / marker).exists():
            return root
    raise SystemExit("No sg-widgets checkout found. Run from it, or set SG_WIDGETS.")


def pascal_case(item: str) -> str:
    return "".join(part.capitalize() for part in item.split("-"))


def snake_case(item: str) -> str:
    return item.replace("-", "_")


def split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    """The frontmatter lines and the body lines."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], lines
    end = lines.index("---", 1)
    return lines[1:end], lines[end + 1 :]


def frontmatter_block(lines: list[str]) -> list[str]:
    """The title and the description, verbatim, as YAML."""
    kept = [line for line in lines if line.startswith(("title:", "description:"))]
    return ["---", *kept, "---", ""]


def directive(match: re.Match[str]) -> str:
    name = match.group(1).lower()
    attrs = ATTR.findall(match.group(2))
    if name == "props" and not any(key == "kind" for key, _ in attrs):
        attrs.append(("kind", "props"))
    body = " ".join(f'{key}="{value}"' for key, value in attrs)
    return f"::{name}{{{body}}}"


def rewrite_links(line: str, section: str) -> str:
    """`/widgets/entity-picker/` becomes the path to that page from this one."""

    def target(match: re.Match[str]) -> str:
        href, _, anchor = match.group(1).partition("#")
        parts = [part for part in href.strip("/").split("/") if part]
        to_section = parts[0]
        page = parts[1] if len(parts) > 1 else "index"
        path = os.path.relpath(f"{to_section}/{page}.md", section)
        return "]({}{})".format(path, "#" + anchor if anchor else "")

    return LINK.sub(target, line)


def install_block(lines: list[str], start: int, item: str) -> tuple[list[str], int] | None:
    """The Python import in place of the registry commands, and the line after them."""
    fence = FENCE.match(lines[start])
    if not fence:
        return None
    end = start + 1
    while end < len(lines) and not FENCE.match(lines[end]):
        end += 1
    body = lines[start + 1 : end]
    if not any(line.startswith("pnpm dlx shadcn") for line in body):
        return None
    for line in body:
        found = REGISTRY_ITEM.search(line)
        if found:
            item = found.group(1)
            break
    block = [
        "```python",
        f"from sg_widgets_qt.widgets.{snake_case(item)} import {pascal_case(item)}",
        "```",
    ]
    return block, end + 1


def convert_body(lines: list[str], section: str, item: str) -> list[str]:
    out: list[str] = []
    fence: str | None = None
    in_install = False
    index = 0
    while index < len(lines):
        line = lines[index]
        opener = FENCE.match(line)
        if fence is not None:
            out.append(line)
            if opener and line.strip().startswith(fence):
                fence = None
            index += 1
            continue
        if HEADING.match(line):
            in_install = line.strip().lower() == "## install"
        if in_install and opener:
            replaced = install_block(lines, index, item)
            if replaced:
                block, index = replaced
                out.extend(block)
                continue
        if opener:
            fence = opener.group(1)
            out.append(line)
            index += 1
            continue
        if ASTRO_IMPORT.match(line):
            index += 1
            continue
        line = TAG.sub(directive, line)
        out.append(rewrite_links(line, section))
        index += 1
    return out


def collapse_blanks(lines: list[str]) -> list[str]:
    """One blank line between blocks, and none where the dropped imports stood."""
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        opener = FENCE.match(line)
        if fence is not None:
            out.append(line)
            if opener and line.strip().startswith(fence):
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            out.append(line)
            continue
        if not line.strip() and (not out or not out[-1].strip()):
            continue
        out.append(line)
    return out


def add_qt_notes(lines: list[str]) -> list[str]:
    """Follows every block that speaks of the web frameworks with a `::qt-note` line."""
    out: list[str] = []
    block: list[str] = []
    fenced: list[bool] = []
    fence: str | None = None

    def flush() -> None:
        if not block:
            return
        prose = "\n".join(line for line, inside in zip(block, fenced) if not inside)
        out.extend(block)
        if QT_WORDS.search(prose):
            out.append("::qt-note")
        block.clear()
        fenced.clear()

    for line in lines:
        opener = FENCE.match(line)
        if fence is None and opener:
            fence = opener.group(1)
            block.append(line)
            fenced.append(True)
            continue
        if fence is not None:
            block.append(line)
            fenced.append(True)
            if opener and line.strip().startswith(fence):
                fence = None
            continue
        if not line.strip():
            flush()
            out.append(line)
            continue
        block.append(line)
        fenced.append(False)
    flush()
    return out


def convert(path: Path, section: str) -> str:
    front, body = split_frontmatter(path.read_text(encoding="utf-8"))
    item = path.stem
    lines = frontmatter_block(front) + add_qt_notes(collapse_blanks(convert_body(body, section, item)))
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def write(target: Path, text: str) -> str | None:
    """Writes the page, or writes `<name>.md.new` where the page is already there and differs."""
    pending = target.with_suffix(".md.new")
    if not target.exists():
        target.write_text(text, encoding="utf-8")
        if pending.exists():
            pending.unlink()
        return None
    if target.read_text(encoding="utf-8") == text:
        if pending.exists():
            pending.unlink()
        return None
    pending.write_text(text, encoding="utf-8")
    return str(pending.relative_to(REPO))


def main() -> int:
    root = upstream_root()
    source = root / "apps/site/src/content/docs"
    written = 0
    pending: list[str] = []
    for section in SECTIONS:
        out_dir = REPO / "docs" / section
        out_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted((source / section).glob("*.mdx")):
            name = write(out_dir / (path.stem + ".md"), convert(path, section))
            written += 1
            if name:
                pending.append(name)
    print("{} pages -> docs/{{{}}}/*.md".format(written, ",".join(SECTIONS)))
    if pending:
        print(f"{len(pending)} differ from the page on disk:")
        for name in pending:
            print("  " + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
