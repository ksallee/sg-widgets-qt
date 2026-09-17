// entity-type-picker: the `focus` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-picker-focus.js --shot /tmp/ref/entity-type-picker-focus.png
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
// The control holding a keyboard focus ring. A drive inside the page cannot make the browser
// paint `:focus-visible`, so the drive focuses what Tab would reach — the token field's input, or
// a summary control's trigger — and reports the rule that paints the ring around the box.
const box = $('[data-slot="entity-type-picker-control"]', control.closest('[data-slot="entity-type-picker"]')) ?? control;
// Base UI hoists the trigger beside the box rather than inside it, so it is looked for on the root.
const root = control.closest('[data-slot="entity-type-picker"]') ?? pane;
const target = caret() ?? $('[data-slot="entity-type-picker-trigger"]', root);
if (!target) return { verdict: 'FAIL nothing in the control takes the caret' };
target.focus({ preventScroll: true });
await wait(300);
const ring = /has-\[:focus-visible\]:ring-2/.test(box.className);
return {
  verdict: ring ? 'PASS focus' : 'FAIL the control paints no focus ring',
  ring,
  focused: document.activeElement?.dataset?.slot ?? '',
};
