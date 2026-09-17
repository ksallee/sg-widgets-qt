// The upstream half of `entity-tree` in the `rest` state, for the Qt half in
// `tools/drives/states/entity-tree.py`.
//
//   pnpm qa --start --path /widgets/entity-tree/ --framework react \
//     --drive tools/drives/upstream/entity-tree-rest.js --shot out.png
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
const tree = () => pane().querySelectorAll('[data-slot="entity-tree"]')[0];
const items = () => [...(tree()?.querySelectorAll('[role="treeitem"]') ?? [])];
const at = (ending) => items().find((n) => n.dataset.path.endsWith(ending));
const labelOf = (n) => n?.querySelector('[data-slot="entity-tree-label"]')?.textContent.trim();
const SEED = '/Shot/sg_sequence/Sequence/100/id/862';
if (!(await until(() => items().length > 0))) return { verdict: 'FAIL the tree drew no node' };
if (!(await until(() => at(SEED)))) return { verdict: 'FAIL seedPath did not open the tree' };
await wait(900);
frame();
const seeded = at(SEED);
notes.push(`seedPath opened ${items().length} nodes down to "${labelOf(seeded)}" at level ${seeded.getAttribute('aria-level')}`);
if (seeded.getAttribute('aria-level') !== '4') return { verdict: 'FAIL the shot is not at level 4', notes };
await wait(400);
return { verdict: 'PASS rest', notes };
