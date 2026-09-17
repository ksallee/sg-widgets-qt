// Measured: context-selector-open. Built by `_build.py`; edit the parts, not this file.
// What every upstream measure drive shares: the pane, a press, a wait-until, and the demo cases.
// Concatenated by `_build.py`; keep the copy there in step.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
function typeInto(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(read, t = 8000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? $$('[data-pane]').find((p) => p.offsetParent !== null) ?? document;
const caseBox = (name) => $(`[data-demo-case="${name}"]`, pane);
const anyCase = (...names) => names.map(caseBox).find(Boolean) ?? pane;
const controlIn = (box) => $('[data-slot$="-control"]', box) ?? $('[data-slot$="-trigger"]', box) ?? box;
const openControl = (box) => {
  const control = controlIn(box);
  const input = $('[data-slot$="-input"]', box);
  press(input ?? $('[data-slot$="-trigger"]', control) ?? control);
  return input;
};
const anyPopup = () => $('[data-picker]') ?? $('[role="listbox"]') ?? $('[data-slot$="-content"]');
// The measuring tail every upstream measure drive ends with. Concatenated by
// `tools/drives/upstream/measure/_build.py`, since qa.mjs runs one file as a function body and
// has no module loader: keep the copy in `_build.py` in step with this file.
//
// It walks the react pane and every popup the widget portals to `body`, and returns, for each
// element carrying a `data-slot`, each row and each cell, its rect, its painted styles and its
// text. `tools/measure_diff.py` reads the answer against the Qt one.
const MEASURE_PROPS = [
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'column-gap', 'row-gap', 'font-size', 'font-weight', 'line-height',
  'color', 'background-color', 'border-top-color', 'border-top-width',
  'border-bottom-width', 'border-left-width', 'border-right-width',
  'border-top-left-radius', 'opacity',
];
function measureOne(el, where) {
  const r = el.getBoundingClientRect();
  const s = getComputedStyle(el);
  const out = {
    slot: el.getAttribute('data-slot') || '',
    role: el.getAttribute('role') || '',
    tag: el.tagName.toLowerCase(),
    where,
    x: +r.x.toFixed(2), y: +r.y.toFixed(2),
    w: +r.width.toFixed(2), h: +r.height.toFixed(2),
    text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 48),
  };
  for (const p of MEASURE_PROPS) out[p] = s.getPropertyValue(p).trim();
  return out;
}
function measureRoot(root, where) {
  const seen = [];
  const wanted = '[data-slot],[data-chip],[role="option"],[role="row"],[role="listbox"],th,td,tr';
  if (root.matches && root.matches(wanted)) seen.push(measureOne(root, where));
  for (const el of root.querySelectorAll(wanted)) seen.push(measureOne(el, where));
  return seen;
}
function measureAll(caseName) {
  const out = [];
  const panes = pane === document ? [document.body] : [pane];
  for (const p of panes) out.push(...measureRoot(p, 'pane'));
  const popups = new Set();
  for (const sel of ['[data-picker]', '[role="listbox"]', '[data-slot^="picker"]', '[role="dialog"]'])
    for (const el of document.body.querySelectorAll(':scope > * ' + sel + ', :scope > ' + sel)) {
      if (pane !== document && pane.contains(el)) continue;
      let top = el;
      while (top.parentElement && top.parentElement !== document.body) top = top.parentElement;
      popups.add(top);
    }
  for (const top of popups) out.push(...measureRoot(top, 'popup'));
  const root = getComputedStyle(document.documentElement);
  const names = ['--background', '--foreground', '--muted', '--muted-foreground', '--accent',
    '--accent-foreground', '--popover', '--popover-foreground', '--border', '--input', '--ring',
    '--destructive', '--secondary', '--secondary-foreground', '--radius'];
  const tokens = {};
  for (const n of names) tokens[n] = root.getPropertyValue(n).trim();
  return { case: caseName, tokens, elements: out };
}

const trigger = await until(() => $('[data-slot="context-selector-trigger"]', pane), 15000);
trigger.scrollIntoView({ block: 'center' });
await wait(300);
press(trigger);
const popup = await until(() => $('[data-slot="popover-content"]'), 8000);
await until(() => $$('[data-slot="context-my-tasks"] button[data-entity-type="Task"]', popup).length, 12000);
await wait(700);
return { verdict: 'PASS', states: { open: measureAll('open') } };
