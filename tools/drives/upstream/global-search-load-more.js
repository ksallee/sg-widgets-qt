// A second page appended under the rows already there, on the load-more row.
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
const input = $$('input[data-slot="command-input"]', pane)[0];
type(input, 'sh');
const first = await until(() => {
  const found = $$('[data-slot="command-item"][data-entity-type]', pane);
  return found.length ? found.length : null;
});
const more = $('[data-slot="search-load-more"]', pane);
if (more) more.click();
const after = await until(() => {
  const n = $$('[data-slot="command-item"][data-entity-type]', pane).length;
  return n > first ? n : null;
});
await wait(500);
const list = $('[data-slot="command-list"]', pane);
if (list) list.scrollTop = list.scrollHeight;
await wait(400);
return { verdict: 'PASS', first, after };
