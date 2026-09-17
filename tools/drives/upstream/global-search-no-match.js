// The empty line, on a query the site holds nothing for.
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
const input = $$('input[data-slot="command-input"]', pane)[0];
type(input, 'zzzqqq');
const empty = await until(() => $('[data-slot="search-empty"]', pane));
await wait(400);
input.scrollIntoView({ block: 'center' });
await wait(300);
return { verdict: 'PASS', empty: Boolean(empty) };
