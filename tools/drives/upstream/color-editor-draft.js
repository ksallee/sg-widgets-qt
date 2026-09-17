// A typed hex code, uncommitted: the swatch previews it before it is the value.
function setValue(el, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, text);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
const box = $$('[data-slot="color-editor"]')[0];
const input = box.querySelector('input[type="text"]');
input.focus();
setValue(input, '#00ff00');
await wait(250);
const swatch = box.querySelector('[data-slot="color-editor-swatch"]');
return { verdict: 'PASS draft', swatch: getComputedStyle(swatch).backgroundColor };
