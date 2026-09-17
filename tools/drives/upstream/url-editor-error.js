// A url with a raw space, refused: the error line stands and the control reads invalid.
function setValue(el, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, text);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
const box = $$('[data-slot="url-editor"]')[0];
const url = box.querySelector('[data-slot="url-editor-url"]');
url.focus();
setValue(url, 'https://example.com/a b.mov');
await wait(120);
url.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
await wait(300);
return {
  verdict: 'PASS error',
  message: box.querySelector('[data-slot="field-editor-error"]')?.textContent.trim() ?? '',
  invalid: url.getAttribute('aria-invalid'),
};
