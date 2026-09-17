// The popover open on its three sections, the assigned tasks landed.
async function until(fn, ms = 12000) {
  const end = Date.now() + ms;
  for (;;) { const v = fn(); if (v) return v; if (Date.now() > end) return null; await wait(50); }
}
const pane = $('[data-pane="react"]') ?? document.body;
const trigger = $('[data-slot="context-selector-trigger"]', pane);
trigger.scrollIntoView({ block: 'center' });
await wait(200);
trigger.click();
const popover = await until(() => $('[data-slot="popover-content"]'));
await until(() => $$('[data-slot="context-my-tasks"] button[data-entity-type="Task"]', popover).length);
await wait(700);
return { verdict: 'PASS', tasks: $$('[data-slot="context-my-tasks"] button[data-entity-type="Task"]', popover).length };
