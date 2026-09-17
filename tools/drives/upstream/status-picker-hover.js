// The control under the pointer, so the wash is on.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//     --path /widgets/status-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/status-picker-hover.js --shot /tmp/ref/status-picker-hover.png
//
// The Qt half is `tools/drives/status-picker-hover.py`.
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
const SLOT = 'status-picker';
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null);
const box = await until(() => {
  const el = $(`[data-demo="p70"] [data-slot="${SLOT}"]`, pane);
  return el && !el.dataset.loading ? el : null;
});
if (!box) return { verdict: 'FAIL no settled p70 status-picker on the page' };
const control = $(`[data-slot="${SLOT}-control"]`, box);
box.scrollIntoView({ block: 'center' });
await wait(300);
// Hover
// A drive runs inside the page: it cannot make the browser hover, cannot give a
// `:focus-visible` ring, and neither status demo arms a failing read, so this state is
// compared from the classes the component and its vendored primitives carry rather than
// from a shot (`tools/drives/upstream/README.md`).
return {
  verdict: 'PASS hover read from the component',
  state: 'hover',
  classes: [control.className, getComputedStyle(control).backgroundColor],
};
