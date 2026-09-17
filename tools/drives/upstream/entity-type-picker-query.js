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
// The list open over `ver`, so the matched runs are bold.
press(control);
if (!(await until(popup))) return { verdict: 'FAIL a press on the field opened no list' };
await until(() => (rows().length ? rows() : null));
// The whole vocabulary is one read, so the list settles in one frame; the drive still lets the
// row count stand still before it measures what the query took away.
let all = [];
for (let i = 0; i < 20; i++) {
  const found = rows();
  if (found.length && found.length === all.length) break;
  all = found;
  await wait(100);
}
const input = caret();
input.focus({ preventScroll: true });
type(input, 'ver');
const narrowed = await until(() => { const f = rows(); return f.length && f.length < all.length ? f : null; });
await wait(600);
const codes = (narrowed ?? []).map((r) => r.dataset.entityType);
const bold = inPopup('.font-semibold').length;
const bad = [];
if (!narrowed) bad.push(`"ver" narrowed nothing out of ${all.length} types`);
if (!codes.includes('Version')) bad.push('"ver" did not offer Version');
return { verdict: bad.length ? 'FAIL ' + bad.join('; ') : 'PASS query', rows: codes.length, of: all.length, bold, codes };
