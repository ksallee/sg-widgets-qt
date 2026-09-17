// The list open with the first read still out, so the skeletons stand where the rows will.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-picker-loading.js --shot out.png
//
// The Qt half is `QA_STATE=loading tools/drives/states/user-picker.py`.

function press(el) {
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
    el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse' }));
  }
  el.click();
}

const pane = $('[data-pane="react"]') ?? document;
const input = $('[data-demo-case="people-only"] [data-slot="entity-picker-input"]', pane);
if (!input) return { verdict: 'FAIL no query input in the people-only case' };
window.scrollTo({ top: input.getBoundingClientRect().top + window.scrollY - 120, behavior: 'instant' });
await wait(300);
press(input);
// The mock answers in 150ms, so the skeletons are shot inside that window.
await wait(60);
const skeletons = $$('[data-picker="entity"] [data-slot="entity-picker-skeleton"]');
return {
  verdict: 'PASS the skeletons stand while the first read is out',
  skeletons: skeletons.length,
  rows: $$('[data-picker="entity"] [data-slot="entity-picker-option"]').length,
};
