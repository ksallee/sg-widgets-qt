// entity-type-picker: the `no-match` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-picker-no-match.js --shot /tmp/ref/entity-type-picker-no-match.png
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
const POPUP = '[data-picker="entity-type"],[data-picker="entity-type-multi"]';
const OPTION = '[data-slot="entity-type-picker-option"]';
const popup = () => $(POPUP);
const rows = () => $$(`${POPUP} ${OPTION}`);
const controls = () => $$('[data-slot="entity-type-picker-control"]', pane).filter((el) => el.getClientRects().length > 0);
await until(() => controls().length > 0, 15000);
await wait(600);
const control = controls().find((el) => el.dataset.disabled === undefined && el.dataset.readonly === undefined) ?? controls()[0];
control.scrollIntoView({ block: 'center' });
await wait(300);
const caret = () => $('[data-slot="entity-type-picker-input"]', control) ?? $(`${POPUP} [data-slot="entity-type-picker-input"]`);
// The list open over a query nothing answers, so the empty line stands alone.
press(control);
if (!(await until(popup))) return { verdict: 'FAIL a press on the field opened no list' };
await until(() => (rows().length ? rows() : null));
const input = caret();
input.focus({ preventScroll: true });
type(input, 'zzzqqq');
const line = await until(() => $(`${POPUP} [data-slot="entity-type-picker-empty"]`), 8000);
await wait(600);
return { verdict: line ? 'PASS no-match' : 'FAIL the query matched something', rows: rows().length, line: line?.textContent.trim() ?? '' };
