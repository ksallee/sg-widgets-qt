// The searchable demo open over a query nothing answers, so the empty line stands.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
function type(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null) ?? document.body;
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const tokens = () => ({
  background: token('--background'), muted: token('--muted'), ring: token('--ring'),
  destructive: token('--destructive'), accent: token('--accent'), border: token('--input'),
});
const demo = async (name) => await until(() => $(`[data-demo="${name}"]`, pane), 15000);

const box = await demo('searchable');
if (!box) return { verdict: 'FAIL no searchable demo' };
box.scrollIntoView({ block: 'center' });
await wait(400);
const control = $('[data-slot$="-control"]', box);
const slot = control.dataset.slot.replace(/-control$/, '');
press(control);
await until(() => $('[data-picker]'));
const input = $(`[data-picker] input[data-slot="${slot}-input"]`) ?? $('[data-picker] input');
input.focus({ preventScroll: true });
type(input, 'zzzqqq');
await wait(700);
const rows = $$(`[data-slot="${slot}-option"]`).filter((e) => e.getClientRects().length > 0);
const line = $('[data-picker] [data-slot$="-empty"]');
return {
  verdict: rows.length === 0 ? 'PASS no rows' : 'FAIL a query nothing answers still listed rows',
  slot, rows: rows.length, line: line ? line.textContent.trim() : '',
};
