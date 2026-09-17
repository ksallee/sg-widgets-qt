// The states section: a person in every control, the three heights, then disabled,
// read-only and invalid.
//
//   cd ~/dev/sg-widgets && node tools/qa.mjs --base http://127.0.0.1:4466 \
//       --path /widgets/user-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/user-picker-filled.js --shot out.png
//
// The Qt half is `QA_STATE=filled tools/drives/states/user-picker.py`. Hover and keyboard
// focus are not here: a drive cannot make the browser hover or tab, so upstream's own
// `tools/drives/upstream/README.md` compares those two from the class strings instead.

const pane = $('[data-pane="react"]') ?? document;
const section = $('[data-demo-case="states"]', pane);
if (!section) return { verdict: 'FAIL no states section' };
window.scrollTo({ top: section.getBoundingClientRect().top + window.scrollY - 60, behavior: 'instant' });
await wait(700);
const boxes = $$('[data-demo-case="states"] [data-slot="entity-picker"]', pane);
return {
  verdict: boxes.length ? 'PASS the states section is on show' : 'FAIL no control in the states section',
  controls: boxes.length,
  inert: boxes.map((box) => ({
    disabled: box.getAttribute('data-disabled') ?? box.dataset.disabled ?? null,
    readonly: box.getAttribute('data-readonly') ?? null,
    invalid: box.getAttribute('aria-invalid') ?? null,
  })),
};
