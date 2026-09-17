// The labels marked on a one-word query, for the shot the port is read against.
//
//   pnpm qa --start --path /widgets/match-text/ --framework react \
//     --drive .../match-text-one-word.js --shot /tmp/ref/match-text-one-word.png
// The docs chrome carries a search box of its own, so the query box is taken from the demo pane.
const pane = $('[data-pane="react"]') ?? document;
const input = $('[data-slot="input"]', pane);
if (!input) return { verdict: 'FAIL the page has no query box' };
const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set;
setter.call(input, 'mo');
input.dispatchEvent(new Event('input', { bubbles: true }));
await wait(400);
const labels = $$('[data-slot="match-text"]', pane);
const marked = labels.flatMap((el) =>
  [...el.children].filter((run) => Number(getComputedStyle(run).fontWeight) > Number(getComputedStyle(el).fontWeight)).map((run) => run.textContent),
);
input.scrollIntoView({ block: 'start' });
await wait(300);
return {
  verdict: marked.length > 0 ? 'PASS a one-word query marks that word wherever it occurs' : 'FAIL nothing was marked',
  marked,
};
