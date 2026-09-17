// field-picker: the list of Version's fields, at the root.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/field-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/field-picker-open.js \
//       --shot /tmp/ref/field-picker-open.png
//
// The Qt half is `tools/drives/field-picker-open.py`.
async function until(read, ms = 12000) {
  const end = Date.now() + ms;
  for (;;) {
    const found = read();
    if (found) return found;
    if (Date.now() > end) return null;
    await wait(50);
  }
}

const box = $('[data-demo="free"]');
if (!box) return { verdict: 'FAIL no free field picker' };
$('[data-slot="field-picker-trigger"]', box).click();
const list = await until(() => document.querySelector('[data-picker="field"]'));
if (!list) return { verdict: 'FAIL the popover never opened' };
const rows = await until(() => {
  const found = list.querySelectorAll('[data-slot="command-item"]');
  return found.length > 0 ? found : null;
});
await wait(300);
return {
  verdict: 'PASS open',
  seen: {
    rows: rows ? rows.length : 0,
    crumb: list.querySelector('[data-slot="field-picker-breadcrumb"]')?.innerText.trim() ?? '',
    placeholder: list.querySelector('[data-slot="command-input"]')?.placeholder ?? '',
    highlighted: [...(rows ?? [])].findIndex((r) => r.getAttribute('data-selected') === 'true'),
  },
};
