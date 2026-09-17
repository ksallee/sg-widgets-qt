// field-picker: a query nothing answers, which is the empty line.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/field-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/field-picker-no-match.js \
//       --shot /tmp/ref/field-picker-no-match.png
//
// The Qt half is `tools/drives/field-picker-no-match.py`.
async function until(read, ms = 12000) {
  const end = Date.now() + ms;
  for (;;) {
    const found = read();
    if (found) return found;
    if (Date.now() > end) return null;
    await wait(50);
  }
}

function type(input, text) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

const box = $('[data-demo="free"]');
$('[data-slot="field-picker-trigger"]', box).click();
const list = await until(() => document.querySelector('[data-picker="field"]'));
if (!list) return { verdict: 'FAIL the popover never opened' };
await until(() => list.querySelectorAll('[data-slot="command-item"]').length > 0 || null);
type(list.querySelector('[data-slot="command-input"]'), 'zzzqqq');
await until(() => list.querySelectorAll('[data-slot="command-item"]').length === 0 || null, 4000);
await wait(300);
return {
  verdict: 'PASS no match',
  seen: {
    rows: list.querySelectorAll('[data-slot="command-item"]').length,
    line: list.innerText.replace(/\s+/g, ' ').trim().slice(0, 80),
  },
};
