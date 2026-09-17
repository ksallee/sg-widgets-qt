// The list open while a read is in flight, so the skeletons are on show.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(20); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null);
await until(() => $$('[data-slot$="-control"]', pane).length > 0, 15000);
await wait(600);
const control = $$('[data-slot$="-control"]', pane).filter((el) => el.getClientRects().length > 0)[0];
control.scrollIntoView({ block: 'start' });
await wait(300);
press(control);
// The skeletons stand only while the first read is out, so the shot is taken at once.
const popup = await until(() => $('[data-picker]'), 4000);
await wait(60);
const skeletons = $$('[data-picker] [data-slot="search-skeleton"], [data-picker] [data-slot$="-loading"]').length;
return { verdict: 'PASS loading', popup: !!popup, skeletons };
