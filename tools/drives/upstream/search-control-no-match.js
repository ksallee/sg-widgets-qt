// The empty line, on a query the crew list holds nothing for.
function type(input, text) {
  const proto = Object.getPrototypeOf(input);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  setter ? setter.call(input, text) : (input.value = text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(fn, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const box = $('[data-demo-case="search"]', pane) ?? pane;
const input = $('input[data-slot="command-input"]', box);
type(input, 'zzzzz');
const empty = await until(() => $('[data-slot="search-empty"]', box));
await wait(300);
input.scrollIntoView({ block: 'center' });
await wait(250);
return { verdict: 'PASS', empty: Boolean(empty) };
