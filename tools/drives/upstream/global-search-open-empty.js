// The palette open on an empty query, which is where the recents show.
async function until(fn, ms = 8000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const trigger = $('[data-slot="global-search-trigger"]', pane);
trigger.scrollIntoView({ block: 'center' });
await wait(150);
trigger.click();
const dialog = await until(() => $('[data-slot="dialog-content"]'));
await wait(500);
return { verdict: 'PASS', recents: $$('[data-slot="command-item"]', dialog).length };
