// The list open over a query the site answers nothing for: the empty line.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
function type(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null);
await until(() => $$('[data-slot$="-control"]', pane).length > 0, 15000);
await wait(600);
const control = $$('[data-slot$="-control"]', pane).filter((el) => el.getClientRects().length > 0)[0];
control.scrollIntoView({ block: 'start' });
await wait(300);
press(control);
await until(() => $('[data-picker]'));
const input = $('[data-slot$="-input"]', control) ?? $('[data-picker] [data-slot$="-input"]');
input.focus({ preventScroll: true });
type(input, 'zzzqqq');
await until(() => $('[data-picker] [data-slot$="-empty"]'), 8000);
await wait(600);
return { verdict: 'PASS empty', line: $('[data-picker] [data-slot$="-empty"]')?.textContent.trim() ?? '' };
