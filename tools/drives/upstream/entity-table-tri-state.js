// The upstream half of `entity-table` in the `tri-state` state, for the Qt half in
// `tools/drives/states/entity-table.py`.
//
//   pnpm qa --start --path /widgets/entity-table/ --framework react \
//     --drive tools/drives/upstream/entity-table-tri-state.js --shot out.png
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
const table = () => pane().querySelector('[data-slot="entity-table"]');
const bodyRows = () => [...pane().querySelectorAll('[data-slot="entity-table"] tbody tr[data-row-key]')];
const groupRows = () => [...pane().querySelectorAll('[data-slot="entity-table-group"]')];
const range = () => pane().querySelector('[data-slot="entity-table-range"]')?.textContent.trim() ?? '';
const boxes = () => [...pane().querySelectorAll('[data-slot="entity-table"] tbody [data-slot="checkbox"]')];
if (!(await until(() => bodyRows().length > 0))) return { verdict: 'FAIL the table drew no row' };
await until(() => range().startsWith('1 to 25'));
await wait(900);
const head = pane().querySelector('[data-slot="entity-table"] thead [data-slot="checkbox"]');
await settleCheck(head, () => head.getAttribute('data-state') === 'checked' || head.getAttribute('aria-checked') === 'true');
await settleCheck(boxes()[0], () => head.getAttribute('data-state') === 'mixed' || head.getAttribute('aria-checked') === 'mixed');
await wait(400);
const state = head.getAttribute('data-state') ?? head.getAttribute('aria-checked');
notes.push(`the head reads ${state}`);
frame();
await wait(300);
return { verdict: 'PASS tri-state', notes };
