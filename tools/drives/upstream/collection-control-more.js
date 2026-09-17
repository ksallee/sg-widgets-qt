// The upstream half of `collection-control` in the `more` state, for the Qt half in
// `tools/drives/states/collection-control.py`.
//
//   pnpm qa --start --path /widgets/collection-control/ --framework react \
//     --drive tools/drives/upstream/collection-control-more.js --shot out.png
// The pane, the wait and the press every collection state drive shares. `tools/qa.mjs` runs
// one file as a function body and has no module loader, so the copies are kept in step by hand
// (`_lib.js`).
const notes = [];
const pane = () => $$('[data-sg-demo] [data-pane]').find((p) => p.offsetParent !== null) ?? document;
async function until(read, ms = 15000) {
  const end = Date.now() + ms;
  for (;;) {
    const value = read();
    if (value) return value;
    if (Date.now() > end) return null;
    await wait(50);
  }
}
function press(el) {
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
    el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  }
  el.click();
}
const button = (text, root = pane()) =>
  [...root.querySelectorAll('button')].find((b) => b.textContent.trim() === text);
function frame(section) {
  (section ?? pane()).scrollIntoView({ block: 'start' });
  window.scrollBy(0, -70);
}
const rows = () => [...pane().querySelectorAll('[data-slot="review-queue-row"]')];
const queue = () => pane().querySelector('[data-slot="review-queue"]');
if (!(await until(() => rows().length > 0))) return { verdict: 'FAIL the queue drew no row' };
await wait(900);
press(button('Load more'));
if (!(await until(() => pane().querySelector('[data-slot="review-queue-load-more"]')))) {
  return { verdict: 'FAIL no load-more row', notes };
}
frame();
await wait(500);
return { verdict: 'PASS more', notes };
