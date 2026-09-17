// The upstream half of `grouped-list` in the `compact` state, for the Qt half in
// `tools/drives/states/grouped-list.py`.
//
//   pnpm qa --start --path /widgets/grouped-list/ --framework react \
//     --drive tools/drives/upstream/grouped-list-compact.js --shot out.png
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
const box = (name) => pane().querySelector(`[data-demo-case="${name}"]`);
const lists = (name) => box(name)?.querySelector('[data-slot="grouped-list"]');
const groups = (name) => [...(lists(name)?.querySelectorAll('[data-slot="grouped-list-group"]') ?? [])];
const rows = (name) => [...(lists(name)?.querySelectorAll('[data-slot="grouped-list-row"]') ?? [])];
if (!(await until(() => groups('pages').length > 1))) return { verdict: 'FAIL the list drew no group' };
await wait(900);
frame(box('pages'));
const tall = rows('pages')[0].getBoundingClientRect().height;
press(button('Compact', box('pages')));
await wait(500);
const short = rows('pages')[0].getBoundingClientRect().height;
notes.push(`row height ${Math.round(tall)} -> ${Math.round(short)}`);
if (!(short < tall)) return { verdict: 'FAIL compact did not halve the padding', notes };
await wait(300);
return { verdict: 'PASS compact', notes };
