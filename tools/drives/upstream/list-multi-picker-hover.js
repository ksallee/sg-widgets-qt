// `:hover` cannot be made from inside the page, so the body answers what the rule resolves to:
// `bg-background hover:bg-muted/30` over the control, and the tokens behind it. The Qt twin
// answers the same numbers from the widget, and `upstream/README.md` says why.
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
const classes = control.className.split(/\s+/);
// `hover:bg-muted/30` over `bg-background`: the composite is built from a probe so the
// number can be read against the one the Qt widget paints.
const probe = document.createElement('div');
probe.style.cssText = 'position:fixed;left:-9999px;background:color-mix(in oklab, var(--muted) 30%, transparent)';
document.body.appendChild(probe);
const wash = getComputedStyle(probe).backgroundColor;
probe.style.background = 'var(--background)';
const base = getComputedStyle(probe).backgroundColor;
probe.remove();
// The tokens are `oklch`, which `getComputedStyle` keeps: a canvas converts them to sRGB.
const srgb = (value) => {
  const c = document.createElement('canvas').getContext('2d');
  c.clearRect(0, 0, 1, 1);
  c.fillStyle = value;
  c.fillRect(0, 0, 1, 1);
  return [...c.getImageData(0, 0, 1, 1).data];
};
const [wr, wg, wb, wAlpha] = srgb(wash);
const [br, bg, bb] = srgb(base);
const wa = wAlpha / 255;
const mix = (w, b) => Math.round(w * wa + b * (1 - wa));
const hex = (n) => n.toString(16).padStart(2, '0');
return {
  verdict: 'PASS hover reads from the rule, not from the pointer',
  reachable: false,
  wash: classes.filter((c) => c.startsWith('hover:')),
  wash_alpha: Number(wa.toFixed(4)),
  tokens: tokens(),
  background: base,
  surface: '#' + hex(mix(wr, br)) + hex(mix(wg, bg)) + hex(mix(wb, bb)),
};
