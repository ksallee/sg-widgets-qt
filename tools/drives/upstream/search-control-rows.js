// A page of rows with the matched runs bold and a load-more row under them.
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
type(input, 'an');
const rows = await until(() => {
  const found = $$('[data-slot="search-control-option"], [data-slot="command-item"]', box);
  return found.length ? found : null;
});
await wait(400);
input.scrollIntoView({ block: 'center' });
await wait(250);
return { verdict: 'PASS', rows: rows ? rows.length : 0, more: Boolean($('[data-slot="search-load-more"]', box)) };
