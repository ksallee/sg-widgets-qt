// The upstream half of `entity-grid` in the `paged` state, for the Qt half in
// `tools/drives/states/entity-grid.py`.
//
//   pnpm qa --start --path /widgets/entity-grid/ --framework react \
//     --drive tools/drives/upstream/entity-grid-paged.js --shot out.png
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
const section = (id) => pane().querySelector(`[data-testid="${id}"]`);
const tiles = (id) => [...(section(id)?.querySelectorAll('[data-slot="entity-card"][data-variant="tile"]') ?? [])];
if (!(await until(() => tiles('grid-sizes').length > 0))) return { verdict: 'FAIL the grid drew no tile' };
await wait(1200);
frame(section('grid-sizes'));
const before = tiles('grid-sizes').length;
const scroller = section('grid-sizes').querySelector('[data-slot="entity-grid-scroll"]');
for (let i = 0; i < 40 && tiles('grid-sizes').length === before; i += 1) {
  scroller.scrollTop = scroller.scrollHeight;
  await wait(250);
}
if (tiles('grid-sizes').length <= before) return { verdict: `FAIL the scroller stopped at ${before} tiles`, notes };
scroller.scrollTop = 0;
await wait(600);
return { verdict: 'PASS paged', notes: [`${before} -> ${tiles('grid-sizes').length} tiles`] };
