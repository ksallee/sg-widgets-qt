// The token field with three chips already in it.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-multi-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-multi-picker-tokens.js --shot out.png
//
// The Qt half is `tools/drives/user-multi-picker-tokens.py`.
// What the user picker state drives share. Concatenated into each drive by hand, since
// qa.mjs runs one file as a function body and has no module loader: keep the copies in step.
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
const summaryBox = (name) => $(`[data-demo-summary="${name}"]`, pane);
const bring = (el, room = 120) => window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - room, behavior: 'instant' });
// The single picker's popup is `entity`, the multi picker's `entity-multi`.
const PICKER = '[data-picker="entity"], [data-picker="entity-multi"]';
const popup = () => $(PICKER);
const options = () => $$('[data-picker="entity"] [data-slot="entity-picker-option"], [data-picker="entity-multi"] [data-slot="entity-picker-option"]');
const text = (row, slot) => $(`[data-slot="${slot}"]`, row)?.textContent.trim() ?? '';
const bold = (row, slot) => [...($(`[data-slot="${slot}"]`, row)?.children ?? [])]
  .filter((span) => span.className.includes('font-semibold')).map((span) => span.textContent).join('');
const readRow = (row) => ({
  label: text(row, 'picker-row-label'),
  sub: text(row, 'picker-row-sub-label'),
  secondary: text(row, 'picker-row-secondary'),
});
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const tokens = () => ({
  background: token('--background'), muted: token('--muted'), ring: token('--ring'),
  destructive: token('--destructive'), accent: token('--accent'), border: token('--input'),
});
const controlIn = (box) => $('[data-slot$="-control"]', box) ?? $('[data-slot="entity-picker"]', box);
const openControl = (box) => {
  const control = controlIn(box);
  const input = $('[data-slot$="-input"]', box);
  // An inline picker opens on its own input; a summary trigger opens on the box or its chevron.
  press(input ?? $('[data-slot$="-trigger"]', control) ?? control);
  return input;
};
const caretOf = (fallback) => ($('[data-picker="entity"] [data-slot$="-input"]') ?? $('[data-picker="entity-multi"] [data-slot$="-input"]')) ?? fallback;
const inertRead = (control) => ({
  opacity: getComputedStyle(control).opacity,
  chevron: Boolean($('[data-slot$="-trigger"]', control)),
  clear: Boolean($('[data-slot$="-clear"]', control)),
  invalid: control.getAttribute('aria-invalid'),
  chips: $$('[data-chip]', control).length,
});

const box = await until(() => caseBox('tokens'), 15000);
if (!box) return { verdict: 'FAIL no token field demo' };
bring(box, 200);
await wait(500);
const chips = $$('[data-chip]', box);
return {
  verdict: chips.length ? 'PASS the chip row stands' : 'FAIL the token field drew no chip',
  chips: chips.length,
  labels: chips.map((chip) => chip.textContent.trim()),
};
