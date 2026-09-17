// The list open on the first user picker of the page: an avatar, a name, the address under it.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-picker-open.js --shot out.png
//
// The Qt half is `QA_STATE=open tools/drives/states/user-picker.py`.

function press(el) {
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
    el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  }
  el.click();
}

async function until(read, timeoutMs = 8000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = read();
    if (value) return value;
    if (Date.now() > deadline) return null;
    await wait(100);
  }
}

const pane = $('[data-pane="react"]') ?? document;
const input = $('[data-demo-case="single"] [data-slot="entity-picker-input"]', pane);
if (!input) return { verdict: 'FAIL no query input in the single case' };
window.scrollTo({ top: input.getBoundingClientRect().top + window.scrollY - 120, behavior: 'instant' });
await wait(300);
press(input);
const box = await until(() => $('[data-picker="entity"]'));
if (!box) return { verdict: 'FAIL the list did not open' };
const rows = await until(() => {
  const found = $$('[data-picker="entity"] [data-slot="entity-picker-option"]');
  return found.length > 0 ? found : null;
});
await wait(900);
const at = box.getBoundingClientRect();
const anchor = input.closest('[data-slot="entity-picker"]')?.getBoundingClientRect() ?? input.getBoundingClientRect();
return {
  verdict: rows ? 'PASS the list is open over the people' : 'FAIL no row was drawn',
  rows: (rows ?? []).length,
  labels: (rows ?? []).slice(0, 3).map((row) => $('[data-slot="picker-row-label"]', row)?.textContent.trim()),
  subs: (rows ?? []).slice(0, 3).map((row) => $('[data-slot="picker-row-sub-label"]', row)?.textContent.trim()),
  secondary: (rows ?? []).slice(0, 3).map((row) => $('[data-slot="picker-row-secondary"]', row)?.textContent.trim()),
  box: { w: Math.round(at.width), below: at.top >= anchor.bottom - 2 },
  anchor: { w: Math.round(anchor.width) },
};
