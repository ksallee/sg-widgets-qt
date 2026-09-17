// entity-type-multi-picker: the `overflow` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-multi-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-multi-picker-overflow.js --shot /tmp/ref/entity-type-multi-picker-overflow.png
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
// The narrow ellipsis control: whole chips, then `+n`, on one line.
const box = $('[data-demo-summary="ellipsis-narrow"]', pane);
if (!box) return { verdict: 'FAIL no narrow ellipsis demo' };
box.scrollIntoView({ block: 'center' });
await wait(400);
const shown = $$('[data-chip]:not([hidden])', box).length;
const hidden = $$('[data-chip][hidden]', box).length;
const pill = $('[data-slot="entity-type-picker-overflow"]', box)?.textContent.trim() ?? '';
const height = Math.round($('[data-slot="entity-type-picker-control"]', box)?.getBoundingClientRect().height ?? 0);
const bad = [];
if (!shown) bad.push('the narrow control drew no chip');
if (pill !== (hidden ? `+${hidden}` : '')) bad.push(`the pill reads "${pill}" for ${hidden} hidden`);
if (height > 40) bad.push(`the control is ${height}px tall, wanted one line`);
return { verdict: bad.length ? 'FAIL ' + bad.join('; ') : 'PASS overflow', shown, hidden, pill, h: height };
