// field-editor: every row on the edit half, which is what the demo's own toggle does.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/field-editor/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/field-editor-editing.js \
//       --shot /tmp/ref/field-editor-editing.png
//
// The Qt half is `tools/drives/field-editor-editing.py`.
const pane = $('[data-pane="react"]') || document.body;
const toggle = $('[data-demo-toggle]', pane);
if (!toggle) return { verdict: 'FAIL no toggle on this page' };
toggle.click();
await wait(500);
const rows = $$('[data-slot="field-editor"]', pane);
return {
  verdict: 'PASS editing',
  rows: rows.length,
  editing: rows.filter((row) => row.dataset.mode === 'edit').length,
};
