// The list open on the first control, its options standing.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//     --path /widgets/status-multi-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/status-multi-picker-open.js --shot /tmp/ref/status-multi-picker-open.png
//
// The Qt half is `tools/drives/status-multi-picker-open.py`.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
function type(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(read, t = 15000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const SLOT = 'status-multi-picker';
// A closed popup stays in the DOM carrying `data-closed`, so only live rows count.
const live = (rows) => rows.filter((r) => !r.closest('[data-closed]') && r.getClientRects().length > 0);
const options = () => live($$(`[data-slot="${SLOT}-option"]`));
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null);
const box = await until(() => {
  const el = $(`[data-demo="p70"] [data-slot="${SLOT}"]`, pane);
  return el && !el.dataset.loading ? el : null;
});
if (!box) return { verdict: 'FAIL no settled p70 status-multi-picker on the page' };
const control = $(`[data-slot="${SLOT}-control"]`, box);
box.scrollIntoView({ block: 'center' });
await wait(300);
press(control);
const rows = await until(() => (options().length > 0 ? options() : null));
await wait(400);
return { verdict: rows ? 'PASS open' : 'FAIL the list drew no row', state: 'open', rows: rows?.length ?? 0 };
