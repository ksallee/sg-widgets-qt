// entity-type-multi-picker: the `summary` state of the shot matrix.
//
//   node tools/qa.mjs --base http://127.0.0.1:4466 --path /widgets/entity-type-multi-picker/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-type-multi-picker-summary.js --shot /tmp/ref/entity-type-multi-picker-summary.png
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
// Two popups, one per picker: a descendant selector has to be written out for each, since a
// comma in a selector list binds looser than the descendant combinator.
const POPUPS = ['[data-picker="entity-type"]', '[data-picker="entity-type-multi"]'];
const POPUP = POPUPS.join(',');
const OPTION = '[data-slot="entity-type-picker-option"]';
const popup = () => $(POPUP);
const inPopup = (sel) => $$(POPUPS.map((p) => `${p} ${sel}`).join(','));
const rows = () => inPopup(OPTION);
const controls = () => $$('[data-slot="entity-type-picker-control"]', pane).filter((el) => el.getClientRects().length > 0);
await until(() => controls().length > 0, 15000);
await wait(600);
const control = controls().find((el) => el.dataset.disabled === undefined && el.dataset.readonly === undefined) ?? controls()[0];
control.scrollIntoView({ block: 'center' });
await wait(300);
const caret = () => $('[data-slot="entity-type-picker-input"]', control) ?? inPopup('[data-slot="entity-type-picker-input"]')[0] ?? null;
// The three summary modes, wide and narrow, as the demo lays them out.
const at = (mode) => {
  const box = $(`[data-demo-summary="${mode}"]`, pane);
  if (!box) return null;
  const el = $('[data-slot="entity-type-picker-control"]', box);
  return {
    width: Math.round(el?.getBoundingClientRect().width ?? 0),
    h: Math.round(el?.getBoundingClientRect().height ?? 0),
    chips: $$('[data-chip]:not([hidden])', box).length,
    hidden: $$('[data-chip][hidden]', box).length,
    pill: $('[data-slot="entity-type-picker-overflow"]', box)?.textContent.trim() ?? '',
    count: $('[data-slot="entity-type-picker-count"]', box)?.textContent.trim() ?? '',
  };
};
$('[data-demo="summary"]', pane)?.scrollIntoView({ block: 'start' });
await wait(400);
const modes = {};
const bad = [];
for (const mode of ['chips', 'chips-narrow', 'ellipsis', 'ellipsis-narrow', 'count', 'count-narrow']) {
  const seen = at(mode);
  if (!seen) { bad.push(`no ${mode} control`); continue; }
  modes[mode] = seen;
}
if (modes.chips && modes.chips.chips !== 6) bad.push(`chips drew ${modes.chips.chips} of 6`);
if (modes.count && modes.count.count !== '6 selected') bad.push(`count read "${modes.count.count}"`);
if (modes['ellipsis-narrow'] && !modes['ellipsis-narrow'].pill) bad.push('the narrow ellipsis control hid nothing');
return { verdict: bad.length ? 'FAIL ' + bad.join('; ') : 'PASS summary', modes };
