// column-picker: the dual layout under 512px, where the two panes stack.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/column-picker/ --framework react \
//       --drive ~/dev/sg-widgets-qt/tools/drives/upstream/column-picker-stacked.js \
//       --shot /tmp/ref/column-picker-stacked.png
//
// The Qt half is `tools/drives/column-picker-stacked.py`. The breakpoint is `@lg` on the
// widget's own container, so narrowing the box the demo gives it is what stacks the panes.
const box = $('[data-demo="dual"]');
if (!box) return { verdict: 'FAIL no dual column picker' };
box.style.width = '420px';
await wait(400);
const panes = $('[data-slot="column-picker-panes"]', box);
const columns = getComputedStyle(panes).gridTemplateColumns.split(' ').length;
return {
  verdict: columns === 1 ? 'PASS stacked' : `FAIL the panes still stand in ${columns} columns`,
  width: box.getBoundingClientRect().width,
  columns,
};
