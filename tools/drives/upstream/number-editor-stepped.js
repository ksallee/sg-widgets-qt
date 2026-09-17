// The duration field one Up step on: 480 minutes becomes 495, shown as 8:15.
const row = $('[data-demo-field="duration"]') ?? $$('[data-slot="number-editor"]')[4];
const input = row.querySelector('input[role="spinbutton"]') ?? row.querySelector('input');
input.focus();
input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
await wait(300);
return { verdict: 'PASS stepped', shown: input.value };
