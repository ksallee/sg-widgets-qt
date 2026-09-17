// entity-type-multi-picker: the `sizes` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-multi-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-multi-picker-sizes.js --shot /tmp/ref/entity-type-multi-picker-sizes.png
// entity-type-picker: the `open` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-picker-open.js --shot /tmp/ref/entity-type-picker-open.png
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
function type(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null) ?? document.body;
// Two popups, one per picker: a descendant selector has to be written out for each, since a
// comma in a selector list binds looser than the descendant combinator.
const POPUPS = ['[data-picker="entity-type"]', '[data-picker="entity-type-multi"]'];
const POPUP = POPUPS.join(',');
const OPTION = '[data-slot="entity-type-picker-option"]';
const popup = () => $(POPUP);
const inPopup = (sel) => $$(POPUPS.map((p) => `${p} ${sel}`).join(','));
const rows = () => inPopup(OPTION);
const controls = () => $$('[data-slot="entity-type-picker-control"]', pane).filter((el) => el.getClientRects().length > 0);
await until(() => controls().length > 0, 15000);
await wait(600);
const control = controls().find((el) => el.dataset.disabled === undefined && el.dataset.readonly === undefined) ?? controls()[0];
control.scrollIntoView({ block: 'center' });
await wait(300);
const caret = () => $('[data-slot="entity-type-picker-input"]', control) ?? inPopup('[data-slot="entity-type-picker-input"]')[0] ?? null;
// Rule 3's ladder: a control is 28, 32 or 36 high, whatever it holds. A wrapped token field
// stands on as many lines as its chips need, so it is left out of the reading.
const LADDER = { sm: 28, md: 32, lg: 36 };
const seen = {};
for (const el of $$('[data-slot="entity-type-picker-control"]', pane)) {
  const root = el.closest('[data-slot="entity-type-picker"]');
  const step = root?.dataset?.size ?? 'md';
  const h = Math.round(el.getBoundingClientRect().height);
  if (h > 40) continue;
  (seen[step] ??= new Set()).add(h);
}
const bad = [];
const heights = {};
for (const [step, held] of Object.entries(seen)) {
  heights[step] = [...held].sort((a, b) => a - b);
  const off = heights[step].filter((h) => h !== LADDER[step]);
  if (off.length) bad.push(`a ${step} control stands ${off}px tall, wanted ${LADDER[step]}`);
}
$('[data-demo="single"],[data-demo="multi"]', pane)?.scrollIntoView({ block: 'start' });
await wait(300);
return { verdict: bad.length ? 'FAIL ' + bad.join('; ') : 'PASS sizes', heights };
