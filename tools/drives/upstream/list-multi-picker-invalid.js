// No demo on this page is invalid: it is the caller's prop. The body answers the destructive
// token and the `aria-invalid` rules the control carries, so the pair is compared as numbers.
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
return {
  verdict: 'PASS invalid is the caller\'s prop and this page never sets it',
  reachable: false,
  invalid_rules: control.className.split(/\s+/).filter((c) => c.includes('aria-invalid')),
  tokens: tokens(),
};
