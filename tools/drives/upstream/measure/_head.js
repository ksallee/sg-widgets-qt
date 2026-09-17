// What every upstream measure drive shares: the pane, a press, a wait-until, and the demo cases.
// Concatenated by `_build.py`; keep the copy there in step.
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
const anyCase = (...names) => names.map(caseBox).find(Boolean) ?? pane;
const controlIn = (box) => $('[data-slot$="-control"]', box) ?? $('[data-slot$="-trigger"]', box) ?? box;
const openControl = (box) => {
  const control = controlIn(box);
  const input = $('[data-slot$="-input"]', box);
  press(input ?? $('[data-slot$="-trigger"]', control) ?? control);
  return input;
};
const anyPopup = () => $('[data-picker]') ?? $('[role="listbox"]') ?? $('[data-slot$="-content"]');
