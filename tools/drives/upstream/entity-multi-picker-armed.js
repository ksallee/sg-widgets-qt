// The token field with the caret on its last chip, the state `picker-armed-chip.js` leaves.
function key(el, name) {
  el.dispatchEvent(new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true }));
  el.dispatchEvent(new KeyboardEvent('keyup', { key: name, bubbles: true, cancelable: true }));
}
async function until(read, t = 6000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$('[data-pane]').find((p) => p.offsetParent !== null);
const box = $('[data-demo-case="tokens"]', pane) ?? $('[data-demo="tokens"]', pane);
if (!box) return { verdict: 'FAIL no token field demo' };
box.scrollIntoView({ block: 'start' });
await wait(500);
const armed = () => $$('[data-chip][data-armed="true"]', box).length;
const input = $('[data-slot$="-input"]', box);
const arm = () => { input.focus({ preventScroll: true }); key(input, 'Backspace'); };
arm();
await until(() => armed() > 0);
setInterval(() => { if (armed() === 0) arm(); }, 80);
await wait(600);
return { verdict: 'PASS armed', armed: armed(), chips: $$('[data-chip]', box).length };
