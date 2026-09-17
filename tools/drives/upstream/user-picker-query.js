// The list open over `ada`, so the matched runs are bold in the name and in the address.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-picker-query.js --shot out.png
//
// The Qt half is `QA_STATE=query tools/drives/states/user-picker.py`.

function press(el) {
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
    el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  }
  el.click();
}

function typeInto(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
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
const input = $('[data-demo-case="by-address"] [data-slot="entity-picker-input"]', pane);
if (!input) return { verdict: 'FAIL no query input in the by-address case' };
window.scrollTo({ top: input.getBoundingClientRect().top + window.scrollY - 120, behavior: 'instant' });
await wait(300);
press(input);
if (!(await until(() => $('[data-picker="entity"]')))) return { verdict: 'FAIL the list did not open' };
typeInto(input, 'ada');
await wait(700);
const rows = await until(() => {
  const found = $$('[data-picker="entity"] [data-slot="entity-picker-option"]');
  return found.length > 0 ? found : null;
});
await wait(900);
const bold = (row, slot) =>
  [...($(`[data-slot="${slot}"]`, row)?.children ?? [])]
    .filter((span) => span.className.includes('font-semibold'))
    .map((span) => span.textContent)
    .join('');
return {
  verdict: rows ? 'PASS the query narrowed the list and the runs are bold' : 'FAIL no row answered `ada`',
  rows: (rows ?? []).length,
  labels: (rows ?? []).map((row) => $('[data-slot="picker-row-label"]', row)?.textContent.trim()),
  boldLabel: (rows ?? []).map((row) => bold(row, 'picker-row-label')),
  boldSub: (rows ?? []).map((row) => bold(row, 'picker-row-sub-label')),
};
