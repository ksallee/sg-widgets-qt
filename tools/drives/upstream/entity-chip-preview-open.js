// A chip's hover card, open, for the shot the port is read against.
//
//   pnpm qa --start --path /widgets/entity-chip/ --framework react \
//     --drive .../entity-chip-preview-open.js --shot /tmp/ref/entity-chip-preview-open.png
//
// The pointer is put on the first chip that carries a preview, the same way
// `tools/drives/entity-chip-preview.js` does it, and the card is given its delay and its read.
function hover(el) {
  const box = el.getBoundingClientRect();
  const init = {
    bubbles: true,
    cancelable: true,
    composed: true,
    clientX: box.left + box.width / 2,
    clientY: box.top + box.height / 2,
    pointerType: 'mouse',
    pointerId: 1,
    isPrimary: true,
  };
  for (const type of ['pointerover', 'pointerenter', 'mouseover', 'mouseenter', 'pointermove', 'mousemove']) {
    el.dispatchEvent(new (type.startsWith('pointer') ? PointerEvent : MouseEvent)(type, init));
  }
}

const triggers = () => $$('[data-slot="entity-chip-preview"]');
for (let i = 0; i < 60 && triggers().length === 0; i += 1) await wait(250);
const trigger = triggers()[0];
if (!trigger) return { verdict: 'FAIL the page drew no chip with a preview' };
trigger.scrollIntoView({ block: 'center' });
await wait(200);
hover(trigger);
for (let i = 0; i < 40 && $$('[data-slot="hover-card-content"]').length === 0; i += 1) await wait(250);
await wait(600);
const card = $('[data-slot="hover-card-content"]');
return {
  verdict: card ? 'PASS the card is open on the chip' : 'FAIL no card opened',
  rows: $$('[data-slot="hover-card-content"] dt').map((el) => el.textContent.trim()),
};
