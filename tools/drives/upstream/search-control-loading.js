// The skeletons, caught while the first read is in flight.
function type(input, text) {
  const proto = Object.getPrototypeOf(input);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  setter ? setter.call(input, text) : (input.value = text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
const pane = $('[data-pane="react"]') ?? document.body;
const box = $('[data-demo-case="search"]', pane) ?? pane;
const input = $('input[data-slot="command-input"]', box);
input.scrollIntoView({ block: 'center' });
type(input, 'an');
await wait(320);
return { verdict: 'PASS', loading: Boolean($('[data-slot="search-loading"]', box)) };
