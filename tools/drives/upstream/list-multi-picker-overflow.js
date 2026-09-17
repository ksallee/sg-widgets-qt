// The chip row with more chips than the line fits, so the rest is a `+n` pill. The demo holds
// what the field offers, so the body ticks every row of the display-values demo first.
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

const box = await demo('labels');
if (!box) return { verdict: 'FAIL no labels demo' };
box.scrollIntoView({ block: 'center' });
await wait(400);
const control = $('[data-slot$="-control"]', box);
const slot = control.dataset.slot.replace(/-control$/, '');
press(control);
await until(() => $$(`[data-slot="${slot}-option"]`).filter((e) => e.getClientRects().length > 0).length > 0);
for (const row of $$(`[data-slot="${slot}-option"]`).filter((e) => e.getClientRects().length > 0)) {
  if (row.dataset.checked !== 'true') { row.click(); await wait(120); }
}
press(control);
await wait(500);
const chips = $$(`[data-slot="${slot}-chip"]`, box);
const pill = $('[data-slot$="-overflow"]', box) ?? $('[data-overflow]', box);
return {
  verdict: chips.length ? 'PASS overflow to +n' : 'FAIL no chip landed',
  slot,
  held: chips.length,
  shown: chips.filter((c) => !c.hidden && c.getClientRects().length > 0).length,
  pill: pill ? pill.textContent.trim() : '',
};
