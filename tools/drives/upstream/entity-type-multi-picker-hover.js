// entity-type-multi-picker: the `hover` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-multi-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-multi-picker-hover.js --shot /tmp/ref/entity-type-multi-picker-hover.png
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
// The control under the pointer. A drive inside the page cannot make the browser hover, so the
// wash is read off the class string the component carries, which is `hover:bg-muted/30`.
const classes = control.className;
const wash = /hover:bg-muted\/30/.test(classes);
control.setAttribute('data-hover', '');
await wait(300);
return { verdict: wash ? 'PASS hover' : 'FAIL the control carries no hover wash', wash, classes };
