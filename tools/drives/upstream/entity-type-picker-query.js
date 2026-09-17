// entity-type-picker: the `query` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-picker-query.js --shot /tmp/ref/entity-type-picker-query.png
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
// The list open over `ver`, so the matched runs are bold.
press(control);
if (!(await until(popup))) return { verdict: 'FAIL a press on the field opened no list' };
const all = (await until(() => (rows().length ? rows() : null))) ?? [];
const input = caret();
input.focus({ preventScroll: true });
type(input, 'ver');
const narrowed = await until(() => { const f = rows(); return f.length && f.length < all.length ? f : null; });
await wait(600);
const codes = (narrowed ?? []).map((r) => r.dataset.entityType);
const bold = $$(`${POPUP} .font-semibold`).length;
const bad = [];
if (!narrowed) bad.push(`"ver" narrowed nothing out of ${all.length} types`);
if (!codes.includes('Version')) bad.push('"ver" did not offer Version');
return { verdict: bad.length ? 'FAIL ' + bad.join('; ') : 'PASS query', rows: codes.length, of: all.length, bold, codes };
