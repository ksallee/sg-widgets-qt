// The list open over a query nothing answers, so the empty line stands alone.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-picker-empty.js --shot out.png
//
// The Qt half is `QA_STATE=empty tools/drives/states/user-picker.py`.

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
const input = $('[data-demo-case="single"] [data-slot="entity-picker-input"]', pane);
if (!input) return { verdict: 'FAIL no query input in the single case' };
window.scrollTo({ top: input.getBoundingClientRect().top + window.scrollY - 120, behavior: 'instant' });
await wait(300);
press(input);
if (!(await until(() => $('[data-picker="entity"]')))) return { verdict: 'FAIL the list did not open' };
typeInto(input, 'zzzqqq');
const line = await until(() => $('[data-picker="entity"] [data-slot="entity-picker-empty"]'));
await wait(600);
return {
  verdict: line ? 'PASS the empty line stands' : 'FAIL nothing was drawn for an empty answer',
  said: line?.textContent.trim() ?? '',
  rows: $$('[data-picker="entity"] [data-slot="entity-picker-option"]').length,
};
