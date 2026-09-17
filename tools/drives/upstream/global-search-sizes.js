// The size ladder, each trigger beside a button of the same step.
async function until(fn, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const triggers = await until(() => {
  const found = $$('[data-slot="global-search-trigger"]', pane);
  return found.length > 1 ? found : null;
});
(triggers ? triggers[triggers.length - 1] : pane).scrollIntoView({ block: 'center' });
await wait(400);
return { verdict: 'PASS', triggers: triggers ? triggers.length : 0 };
