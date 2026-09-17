// The upstream half of `entity-tree` in the `expanded` state, for the Qt half in
// `tools/drives/states/entity-tree.py`.
//
//   pnpm qa --start --path /widgets/entity-tree/ --framework react \
//     --drive tools/drives/upstream/entity-tree-expanded.js --shot out.png
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
at('/Shot/sg_sequence/Sequence/100')?.click();
await wait(400);
at('/Shot')?.click();
await until(() => items().length <= 3);
at('/Shot')?.click();
if (!(await until(() => items().some((n) => n.dataset.path.includes('/Sequence/'))))) {
  return { verdict: 'FAIL opening the Shots folder read no sequence', notes };
}
const branch = items().find((n) => /\/Sequence\/\d+$/.test(n.dataset.path));
branch.click();
if (!(await until(() => items().some((n) => n.dataset.path.startsWith(branch.dataset.path + '/id/'))))) {
  return { verdict: 'FAIL the second level read no shot', notes };
}
await wait(500);
return { verdict: 'PASS expanded', notes: [`${items().length} nodes over two levels`] };
