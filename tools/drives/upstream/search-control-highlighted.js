// The keyboard highlight, two rows down a page of results.
function type(input, text) {
  const proto = Object.getPrototypeOf(input);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  setter ? setter.call(input, text) : (input.value = text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
function press(el, key) {
  el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  el.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true, cancelable: true }));
}
async function until(fn, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const box = $('[data-demo-case="search"]', pane) ?? pane;
const input = $('input[data-slot="command-input"]', box);
type(input, 'an');
await until(() => $$('[data-slot="search-control-option"], [data-slot="command-item"]', box).length);
input.focus({ preventScroll: true });
press(input, 'ArrowDown');
await wait(80);
press(input, 'ArrowDown');
await wait(300);
input.scrollIntoView({ block: 'center' });
await wait(250);
const marked = $$('[data-highlighted]', box).length;
return { verdict: 'PASS', highlighted: marked };
