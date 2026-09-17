// The skeletons in the inline box, caught while the first read is in flight.
function type(input, text) {
  const proto = Object.getPrototypeOf(input);
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  setter ? setter.call(input, text) : (input.value = text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
const pane = $('[data-pane="react"]') ?? document.body;
const input = $$('input[data-slot="command-input"]', pane)[0];
input.scrollIntoView({ block: 'center' });
type(input, 'sh');
await wait(280);
return { verdict: 'PASS', loading: Boolean($('[data-slot="search-loading"]', pane)) };
