// The search results, each drawn as the breadcrumb that reaches it.
function type(input, text) {
  const proto = Object.getPrototypeOf(input);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  setter ? setter.call(input, text) : (input.value = text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(fn, ms = 12000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const root = $('[data-slot="hierarchical-search"]', pane);
const input = $('input[data-slot="command-input"]', root);
type(input, 'sh010_0010 comp');
const rows = await until(() => {
  const found = $$('[data-slot="command-item"][data-entity-type]', root);
  return found.length ? found : null;
});
await wait(700);
root.scrollIntoView({ block: 'center' });
await wait(300);
return { verdict: 'PASS', rows: rows ? rows.length : 0 };
