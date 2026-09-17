// field-picker: one level down through a link, with the breadcrumb over the list.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/field-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/field-picker-deep.js \
//       --shot /tmp/ref/field-picker-deep.png
//
// The Qt half is `tools/drives/field-picker-deep.py`. `Link` on Version declares several
// target types, so the level asks which one first and the first is taken.
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
const link = await until(() =>
  [...list.querySelectorAll('[data-slot="command-item"][data-traversable="true"]')].find((row) =>
    row.textContent.trim().startsWith('Link'),
  ),
);
if (!link) return { verdict: 'FAIL Version offered no traversable Link' };
link.querySelector('[data-slot="field-picker-descend"]').click();
const target = await until(() => list.querySelector('[data-slot="command-item"]'));
if (!target) return { verdict: 'FAIL the link offered no target type' };
target.click();
const crumb = await until(() => {
  const bar = list.querySelector('[data-slot="field-picker-breadcrumb"]');
  return bar && bar.innerText.includes('Link') ? bar : null;
});
await until(() => list.querySelectorAll('[data-slot="command-item"]').length > 0 || null);
await wait(300);
return {
  verdict: crumb ? 'PASS deep' : 'FAIL the hop never landed',
  seen: {
    rows: list.querySelectorAll('[data-slot="command-item"]').length,
    crumb: crumb?.innerText.replace(/\s+/g, ' ').trim() ?? '',
    placeholder: list.querySelector('[data-slot="command-input"]')?.placeholder ?? '',
  },
};
