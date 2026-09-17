// A frame range that runs backwards, refused: the error line stands and nothing is committed.
function setValue(el, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, text);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
const box = $('[data-demo-case="cut"]');
const input = box.querySelector('input');
input.focus();
setValue(input, '1200-1001');
await wait(120);
input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
await wait(300);
box.scrollIntoView({ block: 'center' });
await wait(200);
return {
  verdict: 'PASS error',
  message: box.querySelector('[data-slot="field-editor-error"]')?.textContent.trim() ?? '',
};
