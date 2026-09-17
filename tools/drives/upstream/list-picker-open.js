// The list open on the display-values demo, so every row is a plain label with its code.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//     --path /widgets/list-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/list-picker-open.js --shot /tmp/ref/open.png
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null) ?? document.body;
const box = await until(() => $('[data-demo="labels"]', pane), 15000);
if (!box) return { verdict: 'FAIL no labels demo' };
box.scrollIntoView({ block: 'center' });
await wait(400);
const slot = $('[data-slot$="-control"]', box).dataset.slot.replace(/-control$/, '');
press($('[data-slot$="-control"]', box));
const listed = await until(() => {
  const found = $$(`[data-slot="${slot}-option"]`).filter((el) => el.getClientRects().length > 0);
  return found.length ? found : null;
});
if (!listed) return { verdict: 'FAIL the list did not open' };
await wait(600);
const rows = listed.map((el) => ({
  label: $('[data-slot="picker-row-label"], [data-slot$="-label"]', el)?.textContent.trim() ?? el.textContent.trim(),
  option: el.dataset.option,
  checked: el.dataset.checked === 'true',
}));
return {
  verdict: 'PASS open with rows',
  slot,
  rows: rows.length,
  listed: rows,
  // The set is fixed, so a picker that is not searchable keeps no search row.
  search_row: Boolean($(`[data-picker] input[data-slot="${slot}-input"]`)),
  thumbnails: $$('[data-picker] [data-slot$="-thumbnail"], [data-picker] img').length,
};
