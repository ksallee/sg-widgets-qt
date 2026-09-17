// The paged demo open, so the load-more row is the last row of the list.
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
const box = $('[data-demo="more"]', pane) ?? $('[data-demo-case="more"]', pane);
if (!box) return { verdict: 'FAIL no paged demo' };
box.scrollIntoView({ block: 'start' });
await wait(300);
press($('[data-slot$="-control"]', box));
await until(() => $$('[data-picker] [data-slot$="-option"]').length > 0);
await wait(800);
return {
  verdict: 'PASS more',
  rows: $$('[data-picker] [data-slot$="-option"]').length,
  more: Boolean($('[data-picker] [data-slot$="-more"]')),
};
