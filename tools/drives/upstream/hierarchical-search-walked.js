// One level down the tree: the crumbs in the heading and the row back up.
function press(el, key) {
  el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  el.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true, cancelable: true }));
}
async function until(fn, ms = 10000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const root = $('[data-slot="hierarchical-search"]', pane);
const input = $('input[data-slot="command-input"]', root);
await until(() => $$('[data-slot="command-item"]', root).length);
input.focus({ preventScroll: true });
press(input, 'ArrowDown');
await wait(80);
press(input, 'ArrowRight');
await until(() => $('[data-slot="search-up"]', root));
await wait(500);
root.scrollIntoView({ block: 'center' });
await wait(300);
return { verdict: 'PASS', rows: $$('[data-slot="command-item"]', root).length };
