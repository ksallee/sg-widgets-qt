// The list open after the demo armed the mock's next call to fail: the error line.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null);
await until(() => $$('[data-slot$="-control"]', pane).length > 0, 15000);
await wait(600);
const box = $('[data-demo="error"]', pane) ?? $('[data-demo-case="error"]', pane);
if (!box) return { verdict: 'FAIL no error demo' };
box.scrollIntoView({ block: 'start' });
await wait(300);
const arm = [...box.querySelectorAll('button')].find((b) => /arm/i.test(b.textContent));
if (!arm) return { verdict: 'FAIL no arming button' };
arm.click();
await wait(150);
press($('[data-slot$="-control"]', box));
await until(() => $('[data-picker] [data-slot$="-error"]'), 8000);
await wait(600);
return { verdict: 'PASS error', line: $('[data-picker] [data-slot$="-error"]')?.textContent.trim() ?? '' };
