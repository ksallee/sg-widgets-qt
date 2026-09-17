"""The small markdown converter the docs pages are drawn with.

A page is a YAML front matter, prose, and the two directives the docs exporter writes:

    ::demo{name="entity-picker" title="..."}
    ::props{name="entity-picker" kind="events"}

`split_blocks` cuts a page into the runs of prose between those directives, so the page widget can
interleave text with the demo stages and the props tables, which a `QTextBrowser` cannot hold.
`to_html` turns one run into the subset of HTML a `QTextDocument` draws: headings, paragraphs,
fenced code, inline code, links, tables, bullet lists, bold and italic. `stylesheet` dresses it
from the theme.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from ..theme import Theme, with_alpha

__all__ = [
    "Block",
    "front_matter",
    "split_blocks",
    "stylesheet",
    "to_html",
]

_DIRECTIVE = re.compile(r'^::(demo|props|qt-note)(?:\{(.*)\})?\s*$')
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")
_KBD = re.compile(r"&lt;kbd&gt;(.*?)&lt;/kbd&gt;")
_CODE_SPAN = re.compile(r"`([^`]+)`")


@dataclass
class Block:
    """One run of a page: prose, a demo stage or a props table."""

    kind: str
    source: str = ""
    name: str = ""
    title: str = ""
    table: str = "props"
    attrs: dict = field(default_factory=dict)


def front_matter(text: str) -> tuple[dict, str]:
    """The page's `title` and `description`, and the body under them."""
    meta: dict = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return meta, "\n".join(lines[index + 1 :])
        key, _, value = lines[index].partition(":")
        if _:
            meta[key.strip()] = value.strip().strip("'\"")
    return meta, text


def split_blocks(body: str) -> list[Block]:
    """The page as prose runs, demo stages and props tables, in order."""
    blocks: list[Block] = []
    prose: list[str] = []
    fenced = False

    def flush() -> None:
        text = "\n".join(prose).strip("\n")
        prose.clear()
        if text.strip():
            blocks.append(Block("text", source=text))

    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            prose.append(line)
            continue
        match = None if fenced else _DIRECTIVE.match(line.strip())
        if match is None:
            prose.append(line)
            continue
        kind = match.group(1)
        attrs = dict(_ATTR.findall(match.group(2) or ""))
        if kind == "qt-note":
            # The marker the Qt docs pass answers in the prose. It draws nothing.
            continue
        flush()
        if kind == "demo":
            blocks.append(
                Block("demo", name=attrs.get("name", ""), title=attrs.get("title", ""), attrs=attrs)
            )
        else:
            blocks.append(
                Block(
                    "props",
                    name=attrs.get("name", ""),
                    table=attrs.get("kind", "props"),
                    attrs=attrs,
                )
            )
    flush()
    return blocks


# --- inline ----------------------------------------------------------------------------------


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    """One line of prose as HTML: code, links, bold, italic and the `kbd` runs of a table."""
    spans: list[str] = []

    def take(match: "re.Match[str]") -> str:
        spans.append(match.group(1))
        return "\x00%d\x00" % (len(spans) - 1)

    out = _CODE_SPAN.sub(take, text)
    out = _escape(out)
    out = _KBD.sub(lambda m: '<span class="key">%s</span>' % m.group(1), out)
    out = _LINK.sub(lambda m: '<a href="%s">%s</a>' % (m.group(2), m.group(1)), out)
    out = _BOLD.sub(lambda m: "<b>%s</b>" % m.group(1), out)
    out = _ITALIC.sub(lambda m: "<i>%s</i>" % m.group(1), out)
    for index, span in enumerate(spans):
        out = out.replace("\x00%d\x00" % index, '<code>%s</code>' % _escape(span))
    return out


# --- blocks ----------------------------------------------------------------------------------


def _table(rows: list[str]) -> str:
    cells = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows]
    head = cells[0]
    body = [row for row in cells[2:]] if len(cells) > 2 else []
    out = ['<table class="md" cellspacing="0" cellpadding="0" width="100%">']
    out.append("<tr>" + "".join("<th>%s</th>" % inline(cell) for cell in head) + "</tr>")
    for row in body:
        out.append("<tr>" + "".join("<td>%s</td>" % inline(cell) for cell in row) + "</tr>")
    out.append("</table>")
    return "".join(out)


def to_html(source: str, _theme: Theme | None = None) -> str:
    """One run of prose as the HTML a `QTextDocument` draws. Colours come from `stylesheet`."""
    out: list[str] = []
    lines = source.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            out.append('<pre class="code">%s</pre>' % _escape("\n".join(code)))
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            out.append(
                "<h%d>%s</h%d>" % (min(level, 3), inline(stripped[level:].strip()), min(level, 3))
            )
            index += 1
            continue

        if stripped.startswith("|"):
            rows: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index])
                index += 1
            if len(rows) >= 2:
                out.append(_table(rows))
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip()[:2] in ("- ", "* "):
                item = [lines[index].strip()[2:]]
                index += 1
                while index < len(lines) and lines[index].startswith("  ") and lines[index].strip():
                    item.append(lines[index].strip())
                    index += 1
                items.append(" ".join(item))
            out.append("<ul>" + "".join("<li>%s</li>" % inline(item) for item in items) + "</ul>")
            continue

        if stripped.startswith("> "):
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("> "):
                quote.append(lines[index].strip()[2:])
                index += 1
            out.append('<p class="quote">%s</p>' % inline(" ".join(quote)))
            continue

        paragraph: list[str] = []
        while index < len(lines) and lines[index].strip():
            current = lines[index].strip()
            if current.startswith(("#", "|", "- ", "* ", "> ", "```")):
                break
            paragraph.append(current)
            index += 1
        out.append("<p>%s</p>" % inline(" ".join(paragraph)))
    return "".join(out)


def stylesheet(theme: Theme) -> str:
    """The document stylesheet one theme dresses a page's prose with."""
    code_ground = with_alpha(theme.color("muted"), 1.0).name()
    return _STYLE.format(
        foreground=theme.foreground,
        muted=theme.muted_foreground,
        code_ground=code_ground,
        border=theme.border,
        primary=theme.primary,
        mono=theme.font_mono or "monospace",
        sans=theme.font_sans or "sans-serif",
    )


_STYLE = """
body {{ color: {foreground}; font-family: "{sans}"; font-size: 14px; }}
p {{ color: {foreground}; margin-top: 0px; margin-bottom: 12px; line-height: 150%; }}
p.quote {{ color: {muted}; }}
h1 {{ font-size: 22px; font-weight: 500; margin-top: 8px; margin-bottom: 12px; }}
h2 {{ font-size: 18px; font-weight: 500; margin-top: 16px; margin-bottom: 8px; }}
h3 {{ font-size: 15px; font-weight: 500; margin-top: 12px; margin-bottom: 8px; }}
a {{ color: {primary}; text-decoration: none; }}
ul {{ margin-top: 0px; margin-bottom: 12px; }}
li {{ margin-bottom: 4px; line-height: 150%; }}
code {{ font-family: "{mono}"; font-size: 12px; background-color: {code_ground}; color: {foreground}; }}
span.key {{ font-family: "{mono}"; font-size: 12px; background-color: {code_ground}; color: {foreground}; }}
pre.code {{ font-family: "{mono}"; font-size: 12px; background-color: {code_ground};
  color: {foreground}; padding: 12px; margin-top: 0px; margin-bottom: 12px; }}
table.md {{ border-color: {border}; margin-bottom: 12px; }}
th {{ color: {muted}; font-size: 12px; font-weight: 500; padding: 8px 12px;
  border-bottom: 1px solid {border}; text-align: left; }}
td {{ color: {foreground}; font-size: 13px; padding: 8px 12px; border-bottom: 1px solid {border}; }}
"""
