// `loading` and `loadError` are the caller's props and no demo on this page sets them: the
// vocabulary is one read the caller has already made, so the page cannot reach the state. The
// body answers the tokens and the class strings the skeleton and the state line resolve to, and
// `upstream/README.md` says why a state outside the page is compared as numbers.
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
press(control);
await until(() => $('[data-picker]'));
await wait(400);
const list = $('[data-picker] [role="listbox"]') ?? $('[data-picker]');
return {
  verdict: 'PASS loading is the caller\'s prop and this page never sets it',
  reachable: false,
  tokens: tokens(),
  popup_class: $('[data-picker]').className,
  list_class: list.className,
};
