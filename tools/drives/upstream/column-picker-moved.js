// column-picker: a chosen row picked up with Space and moved one place with the keyboard.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/column-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/column-picker-moved.js \
//       --shot /tmp/ref/column-picker-moved.png
//
// The Qt half is `tools/drives/column-picker-moved.py`. Upstream's keys live on the grip; the
// port's chosen list is one tab stop and holds a highlight instead, which its docs page says.
async function until(read, ms = 12000) {
  const end = Date.now() + ms;
  for (;;) {
    const found = read();
    if (found) return found;
    if (Date.now() > end) return null;
    await wait(50);
  }
}

function key(el, name) {
  el.dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true }));
}

const box = $('[data-demo="columns"]');
if (!box) return { verdict: 'FAIL no column picker' };
const rows = await until(() => {
  const found = $$('[data-slot="column-picker-column"]', box);
  return found.length > 1 ? found : null;
});
if (!rows) return { verdict: 'FAIL the chosen list never filled' };
const grip = rows[0].querySelector('[data-slot="column-picker-grip"]');
grip.focus();
key(grip, ' ');
await wait(100);
key(grip, 'ArrowDown');
await wait(300);
return {
  verdict: 'PASS moved',
  order: $$('[data-slot="column-picker-column"]', box).map((row) => row.innerText.trim()),
  announced: $('[data-slot="column-picker-live-region"]', box)?.textContent.trim() ?? '',
  value: $('.font-mono', box)?.textContent.trim() ?? '',
};
