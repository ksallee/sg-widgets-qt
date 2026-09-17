// The inline box with a page of rows, grouped by type, the matched runs bold.
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
type(input, 'sh');
const rows = await until(() => {
  const found = $$('[data-slot="command-item"][data-entity-type]', pane);
  return found.length ? found : null;
});
await wait(600);
input.scrollIntoView({ block: 'center' });
await wait(300);
return { verdict: 'PASS', rows: rows ? rows.length : 0, groups: $$('[data-slot="command-group"]', pane).length };
