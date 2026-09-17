// The remove control of a status badge, holding focus, for the shot the port is read against.
//
//   pnpm qa --start --path /widgets/status-badge/ --framework react \
//     --drive .../status-badge-cross-focus.js --shot /tmp/ref/status-badge-cross-focus.png
//
// `focus-visible` follows the browser's own heuristic, so what this state shows for certain is
// where the cross sits and what it is; the ring is read against `REMOVE_CONTROL` in the port's
// own drive.
const box = $('[data-demo="removable"]');
if (!box) return { verdict: 'FAIL no removable demo on the page' };
box.scrollIntoView({ block: 'center' });
await wait(200);
const cross = $('[data-slot="status-badge-remove"]', box);
if (!cross) return { verdict: 'FAIL no cross on a removable badge' };
cross.focus();
await wait(300);
return {
  verdict:
    document.activeElement === cross
      ? 'PASS the cross holds focus'
      : 'FAIL the cross did not take focus',
  where: cross.getBoundingClientRect().toJSON(),
};
