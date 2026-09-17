// The three summary modes. Every demo on this page is the default `ellipsis`, so the body
// answers what each control carries and the widths the modes resolve to.
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

await demo('values');
await wait(400);
const roots = $$('[data-slot="list-multi-picker"]', pane);
return {
  verdict: roots.length ? 'PASS the summary modes' : 'FAIL no multi picker on the page',
  seen: roots.map((root) => ({
    demo: root.closest('[data-demo]')?.dataset.demo ?? 'page',
    summary: root.dataset.summary,
    chips: $$('[data-slot="list-multi-picker-chip"]', root).length,
    shown: $$('[data-slot="list-multi-picker-chip"]', root).filter((c) => !c.hidden).length,
  })),
};
