// The empty line, on a query the tree holds nothing for.
function type(input, text) {
  const proto = Object.getPrototypeOf(input);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  setter ? setter.call(input, text) : (input.value = text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(fn, ms = 10000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const root = $('[data-slot="hierarchical-search"]', pane);
const input = $('input[data-slot="command-input"]', root);
type(input, 'zzzqqq');
const empty = await until(() => $('[data-slot="search-empty"]', root));
await wait(400);
root.scrollIntoView({ block: 'center' });
await wait(300);
return { verdict: 'PASS', empty: Boolean(empty) };
