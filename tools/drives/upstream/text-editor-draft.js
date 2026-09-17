// The single-line text editor with a typed, uncommitted draft.
function setValue(el, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, text);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
const box = $$('[data-slot="text-editor"]')[0];
const input = box.querySelector('input');
input.focus();
setValue(input, 'typed, not committed');
await wait(200);
return { verdict: 'PASS draft', value: input.value };
