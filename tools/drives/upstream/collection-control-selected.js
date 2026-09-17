// The upstream half of `collection-control` in the `selected` state, for the Qt half in
// `tools/drives/states/collection-control.py`.
//
//   pnpm qa --start --path /widgets/collection-control/ --framework react \
//     --drive tools/drives/upstream/collection-control-selected.js --shot out.png
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

/** Base UI settles a checkbox on click, Bits UI on pointerup: try one, then the other. */
async function settleCheck(el, landed) {
  el.click();
  if (await until(landed, 1500)) return true;
  press(el);
  return Boolean(await until(landed, 1500));
}
function frame(section) {
  (section ?? pane()).scrollIntoView({ block: 'start' });
  window.scrollBy(0, -70);
}
const rows = () => [...pane().querySelectorAll('[data-slot="review-queue-row"]')];
const queue = () => pane().querySelector('[data-slot="review-queue"]');
if (!(await until(() => rows().length > 0))) return { verdict: 'FAIL the queue drew no row' };
await wait(900);
frame();
const head = pane().querySelector('[data-slot="review-queue-head"] [data-slot="checkbox"]');
if (!head) return { verdict: 'FAIL the queue has no head box', notes };
await settleCheck(head, () => {
  const line = pane().querySelector('[data-demo="selection"]')?.textContent.trim();
  return line && !line.startsWith('0 ');
});
const count = await until(() => {
  const line = pane().querySelector('[data-demo="selection"]')?.textContent.trim();
  return line && !line.startsWith('0 ') ? line : null;
});
if (!count) return { verdict: 'FAIL nothing was taken', notes };
await wait(400);
return { verdict: 'PASS selected', notes: [`selection reads ${count}`] };
