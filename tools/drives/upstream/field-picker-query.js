// field-picker: a query in the search box, with the matched runs in the rows.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/field-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/field-picker-query.js \
//       --shot /tmp/ref/field-picker-query.png
//
// The Qt half is `tools/drives/field-picker-query.py`.
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
type(list.querySelector('[data-slot="command-input"]'), 'date');
await wait(400);
return {
  verdict: 'PASS query',
  seen: {
    rows: list.querySelectorAll('[data-slot="command-item"]').length,
    query: list.querySelector('[data-slot="command-input"]').value,
  },
};
