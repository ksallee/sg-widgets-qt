#!/usr/bin/env python
"""Compose one upstream measure drive per page, and say how to run it.

`~/dev/sg-widgets/tools/qa.mjs` runs a drive file as one async function body with no module
loader, so each page's drive is `_head.js` + its own `openIt`/`closeIt` + `_tail.js` + `_run.js`
concatenated here rather than imported. One run answers four states — the pane at rest and with
the widget open, in light and in dark — which `tools/measure_split.py` writes out as
`tools/drives/upstream/measure/<page>-<state>.json`.

    python tools/drives/upstream/measure/_build.py
    cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:<port> \
        --path /widgets/entity-picker/ --framework react \
        --drive ~/dev/sg-widgets-qt/tools/drives/upstream/measure/entity-picker.js
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

#: A picker: press the first control that is neither loading nor inert, and wait for its rows.
PICKER = """
async function openIt() {
  const box = await until(() => $$('[data-slot$="-control"]', pane).find((el) =>
    el.getClientRects().length > 0 && !el.closest('[data-loading="true"]') &&
    el.getAttribute('aria-disabled') !== 'true' && !el.querySelector('[disabled]')), 15000);
  if (!box) return;
  box.scrollIntoView({ block: 'center' });
  await wait(400);
  press($('[data-slot$="-input"]', box) ?? box);
  await until(anyPopup, 8000);
  await until(() => $$('[data-slot$="-option"],[role="option"]').filter((el) => el.getClientRects().length).length, 8000);
}
async function closeIt() {
  document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await wait(200);
}
"""


def trigger(selector: str) -> str:
    """Press the one thing on the page that opens a surface, and wait for it."""
    return """
async function openIt() {
  const el = await until(() => $$('{selector}', pane).find((e) => e.getClientRects().length > 0), 15000);
  if (!el) return;
  el.scrollIntoView({ block: 'center' });
  await wait(400);
  press(el);
  await until(() => anyPopup() ?? $('[role="dialog"]'), 8000);
  await wait(400);
}
async function closeIt() {
  document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await wait(250);
}
""".replace("{selector}", selector)


#: A page with no surface to open: the second measurement is the page again, settled.
STILL = """
async function openIt() { await wait(200); }
async function closeIt() { await wait(50); }
"""

PAGES: dict[str, str] = {
    "entity-picker": PICKER,
    "entity-multi-picker": PICKER,
    "user-picker": PICKER,
    "user-multi-picker": PICKER,
    "project-picker": PICKER,
    "project-multi-picker": PICKER,
    "status-picker": PICKER,
    "status-multi-picker": PICKER,
    "list-picker": PICKER,
    "list-multi-picker": PICKER,
    "entity-type-picker": PICKER,
    "entity-type-multi-picker": PICKER,
    "field-picker": trigger('[data-slot="field-picker-trigger"]'),
    "column-picker": trigger('[data-slot="field-picker-trigger"]'),
    "field-editor": trigger('[data-slot="field-editor-display"]'),
    "filter-editor": trigger('[data-slot="filter-field"] [data-slot="field-picker-trigger"]'),
    "filter-dialog": trigger('[data-slot="filter-launch"]'),
    "filter-bar": trigger('[data-slot="filter-pill-trigger"]'),
    "sort-picker": trigger('[data-slot="sort-trigger"]'),
    "entity-table": trigger('[data-slot="sort-trigger"]'),
    "entity-grid": STILL,
    "grouped-list": STILL,
    "entity-tree": trigger('[data-slot="entity-tree-chevron"]'),
}



#: The three search pages are measured state by state rather than open/shut, so each one has a
#: body of its own that leaves the page in the state its name says and measures it there. The
#: Qt twin is `tools/drives/measure/<page>-<state>.py`.
SEARCH = "const input = () => $$('input[data-slot=\"command-input\"]', pane)[0];"

STATES: dict[str, str] = {
    "global-search-rest": """
await until(() => $('[data-slot="global-search-trigger"]', pane), 15000);
await wait(700);
return { verdict: 'PASS', states: { rest: measureAll('rest') } };
""",
    "global-search-open-empty": """
const trigger = await until(() => $('[data-slot="global-search-trigger"]', pane), 15000);
press(trigger);
await until(() => $('[data-slot="dialog-content"]'), 8000);
await until(() => $$('[data-slot="command-item"]').length, 8000);
await wait(700);
return { verdict: 'PASS', states: { 'open-empty': measureAll('open-empty') } };
""",
    "global-search-open-query": """
const trigger = await until(() => $('[data-slot="global-search-trigger"]', pane), 15000);
press(trigger);
const popup = await until(() => $('[data-slot="dialog-content"]'), 8000);
typeInto($('input[data-slot="command-input"]', popup), 'sh');
await until(() => $$('[data-slot="command-item"][data-entity-type]', popup).length, 12000);
await wait(700);
return { verdict: 'PASS', states: { 'open-query': measureAll('open-query') } };
""",
    "global-search-loading": """
const box = await until(() => $$('input[data-slot="command-input"]', pane)[0], 15000);
typeInto(box, 'sh');
await until(() => $('[data-slot="search-loading"]', pane), 4000);
return { verdict: 'PASS', states: { loading: measureAll('loading') } };
""",
    "global-search-rows": """
const box = await until(() => $$('input[data-slot="command-input"]', pane)[0], 15000);
typeInto(box, 'sh');
await until(() => $$('[data-slot="command-item"][data-entity-type]', pane).length, 12000);
await wait(700);
return { verdict: 'PASS', states: { rows: measureAll('rows') } };
""",
    "global-search-no-match": """
const box = await until(() => $$('input[data-slot="command-input"]', pane)[0], 15000);
typeInto(box, 'zzzqqq');
await until(() => $('[data-slot="search-empty"]', pane), 12000);
await wait(500);
return { verdict: 'PASS', states: { 'no-match': measureAll('no-match') } };
""",
    "global-search-sizes": """
await until(() => $('[data-demo="size-lg"]', pane), 15000);
await wait(700);
return { verdict: 'PASS', states: { sizes: measureAll('sizes') } };
""",
    "hierarchical-search-rest": """
await until(() => $$('[data-slot="command-item"]', pane).length, 15000);
await wait(700);
return { verdict: 'PASS', states: { rest: measureAll('rest') } };
""",
    "hierarchical-search-rows": """
const box = await until(() => $$('input[data-slot="command-input"]', pane)[0], 15000);
typeInto(box, 'sh010_0010 comp');
await until(() => $$('[data-slot="command-item"]', pane).length, 12000);
await wait(700);
return { verdict: 'PASS', states: { rows: measureAll('rows') } };
""",
    "hierarchical-search-no-match": """
const box = await until(() => $$('input[data-slot="command-input"]', pane)[0], 15000);
typeInto(box, 'zzzqqq');
await until(() => $('[data-slot="search-empty"]', pane), 12000);
await wait(500);
return { verdict: 'PASS', states: { 'no-match': measureAll('no-match') } };
""",
    "context-selector-rest": """
await until(() => $('[data-slot="context-selector-trigger"]', pane), 15000);
await wait(700);
return { verdict: 'PASS', states: { rest: measureAll('rest') } };
""",
    "context-selector-open": """
const trigger = await until(() => $('[data-slot="context-selector-trigger"]', pane), 15000);
trigger.scrollIntoView({ block: 'center' });
await wait(300);
press(trigger);
const popup = await until(() => $('[data-slot="popover-content"]'), 8000);
await until(() => $$('[data-slot="context-my-tasks"] button[data-entity-type="Task"]', popup).length, 12000);
await wait(700);
return { verdict: 'PASS', states: { open: measureAll('open') } };
""",
    "context-selector-sizes": """
await until(() => $('[data-demo="size-lg"]', pane) ?? $('[data-slot="context-selector-trigger"]', pane), 15000);
await wait(700);
return { verdict: 'PASS', states: { sizes: measureAll('sizes') } };
""",
}


def main() -> None:
    head = (HERE / "_head.js").read_text(encoding="utf-8")
    tail = (HERE / "_tail.js").read_text(encoding="utf-8")
    run = (HERE / "_run.js").read_text(encoding="utf-8")
    for page, body in PAGES.items():
        note = f"// Measured: {page}. Built by `_build.py`; edit the parts, not this file.\n"
        (HERE / f"{page}.js").write_text(note + head + body + tail + run, encoding="utf-8")
    for name, body in STATES.items():
        note = f"// Measured: {name}. Built by `_build.py`; edit the parts, not this file.\n"
        (HERE / f"{name}.js").write_text(note + head + tail + body, encoding="utf-8")
    print(f"wrote {len(PAGES) + len(STATES)} drives to {HERE}")


if __name__ == "__main__":
    main()
