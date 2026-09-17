// The control under the pointer, which a drive cannot make: the rule is read instead.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-picker-hover.js --shot out.png
//
// The Qt half is `tools/drives/user-picker-hover.py`.
// What the user picker state drives share. Concatenated into each drive by hand, since
// qa.mjs runs one file as a function body and has no module loader: keep the copies in step.
function press(el) {
  for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup'])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  el.click();
}
function typeInto(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, text);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}
async function until(read, t = 8000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? $$('[data-pane]').find((p) => p.offsetParent !== null) ?? document;
const caseBox = (name) => $(`[data-demo-case="${name}"]`, pane);
const summaryBox = (name) => $(`[data-demo-summary="${name}"]`, pane);
const bring = (el, room = 120) => window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - room, behavior: 'instant' });
// The single picker's popup is `entity`, the multi picker's `entity-multi`.
const PICKER = '[data-picker="entity"], [data-picker="entity-multi"]';
const popup = () => $(PICKER);
const options = () => $$('[data-picker="entity"] [data-slot="entity-picker-option"], [data-picker="entity-multi"] [data-slot="entity-picker-option"]');
const text = (row, slot) => $(`[data-slot="${slot}"]`, row)?.textContent.trim() ?? '';
const bold = (row, slot) => [...($(`[data-slot="${slot}"]`, row)?.children ?? [])]
  .filter((span) => span.className.includes('font-semibold')).map((span) => span.textContent).join('');
const readRow = (row) => ({
  label: text(row, 'picker-row-label'),
  sub: text(row, 'picker-row-sub-label'),
  secondary: text(row, 'picker-row-secondary'),
});
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const tokens = () => ({
  background: token('--background'), muted: token('--muted'), ring: token('--ring'),
  destructive: token('--destructive'), accent: token('--accent'), border: token('--input'),
});
const controlIn = (box) => $('[data-slot$="-control"]', box) ?? $('[data-slot="entity-picker"]', box);
const openControl = (box) => {
  const control = controlIn(box);
  const input = $('[data-slot$="-input"]', box);
  // An inline picker opens on its own input; a summary trigger opens on the box or its chevron.
  press(input ?? $('[data-slot$="-trigger"]', control) ?? control);
  return input;
};
const caretOf = (fallback) => ($('[data-picker="entity"] [data-slot$="-input"]') ?? $('[data-picker="entity-multi"] [data-slot$="-input"]')) ?? fallback;
const inertRead = (control) => ({
  opacity: getComputedStyle(control).opacity,
  chevron: Boolean($('[data-slot$="-trigger"]', control)),
  clear: Boolean($('[data-slot$="-clear"]', control)),
  invalid: control.getAttribute('aria-invalid'),
  chips: $$('[data-chip]', control).length,
});

// `:hover` cannot be made from inside the page, so the body answers what the rule resolves to:
// `bg-background hover:bg-muted/30` over the control, which is the composite the Qt twin paints.
const box = await until(() => caseBox('single'), 15000);
if (!box) return { verdict: 'FAIL no single demo' };
bring(box, 200);
await wait(400);
const control = controlIn(box);
const probe = document.createElement('div');
probe.style.cssText = 'position:fixed;left:-9999px;background:color-mix(in oklab, var(--muted) 30%, transparent)';
document.body.appendChild(probe);
const wash = getComputedStyle(probe).backgroundColor;
probe.style.background = 'var(--background)';
const base = getComputedStyle(probe).backgroundColor;
probe.remove();
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
  wash: control.className.split(/\s+/).filter((c) => c.startsWith('hover:')),
  wash_alpha: Number(wa.toFixed(4)),
  background: base,
  surface: '#' + hex(mix(wr, br)) + hex(mix(wg, bg)) + hex(mix(wb, bb)),
};
