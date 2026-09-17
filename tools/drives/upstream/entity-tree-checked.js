// The upstream half of `entity-tree` in the `checked` state, for the Qt half in
// `tools/drives/states/entity-tree.py`.
//
//   pnpm qa --start --path /widgets/entity-tree/ --framework react \
//     --drive tools/drives/upstream/entity-tree-checked.js --shot out.png
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
const branch = items().find((n) => /\/Sequence\/\d+$/.test(n.dataset.path));
if (!branch) return { verdict: 'FAIL the seeded tree drew no sequence', notes };
// The box is `pointer-events-none`, so Space on the row is the gesture that checks it.
branch.focus();
await wait(150);
branch.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true }));
// Space checks the branch and spreads down; a branch whose level is only part read
// settles at `mixed` until the rest of it arrives.
if (!(await until(() => ['true', 'mixed'].includes(branch.getAttribute('aria-checked'))))) {
  return { verdict: `FAIL the branch reads ${branch.getAttribute('aria-checked')}`, notes };
}
notes.push(`checking the branch left it ${branch.getAttribute('aria-checked')}`);
const leaf = items().find((n) => n.dataset.path.startsWith(branch.dataset.path + '/id/'));
leaf.focus();
leaf.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true }));
if (!(await until(() => branch.getAttribute('aria-checked') === 'mixed'))) {
  return { verdict: `FAIL the branch reads ${branch.getAttribute('aria-checked')}, expected mixed`, notes };
}
notes.push(`the demo reports ${pane().querySelector('[data-testid="checked-count"]')?.textContent.trim()}`);
await wait(500);
return { verdict: 'PASS checked', notes };
