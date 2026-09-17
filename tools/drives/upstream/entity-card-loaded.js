// The cards once their reads have landed, which is the state the port is read against.
//
//   pnpm qa --start --path /widgets/entity-card/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/entity-card-loaded.js \
//     --shot /tmp/ref/entity-card-loaded.png
//
// The Qt half is `tools/drives/states/entity-card.py` with `QA_STATE=loaded`. A plain shot of
// this page catches the skeletons: the demo reads a Version, its status table and its thumbnail
// after the island mounts, and the driver's own ready gate does not wait for that. Here the run
// waits for three named cards and their pictures, then reports the header and the grid of each,
// so the port is read against the labels and the strings and not only against the picture.

const drawn = () => $$('[data-pane]').find((pane) => pane.getBoundingClientRect().height > 0);
const cards = () => [...(drawn()?.querySelectorAll('[data-slot="entity-card"][data-variant="card"]') ?? [])];
const named = (card) =>
  card.querySelector('a[target="_blank"], [data-slot="entity-card-name"] span, span[title]')?.textContent.trim() ?? '';

for (let i = 0; i < 80 && cards().filter((c) => named(c).length > 0).length < 3; i += 1) await wait(250);
const held = cards().filter((c) => named(c).length > 0);
if (held.length < 3) return { verdict: `FAIL ${held.length} cards were named, expected at least 3` };

const pictures = () => [...(drawn()?.querySelectorAll('[data-slot="entity-card"] img') ?? [])];
for (let i = 0; i < 40 && pictures().some((img) => !img.complete); i += 1) await wait(250);
await wait(500);

function describe(card) {
  const badges = card.querySelectorAll('[data-slot="status-badge"]');
  const grid = [...card.querySelectorAll('dt')].map((dt, index) => ({
    label: dt.textContent.trim(),
    value: (card.querySelectorAll('dd')[index]?.textContent ?? '').trim(),
    dataType: card.querySelectorAll('dd')[index]?.dataset.dataType ?? '',
  }));
  const thumb = card.querySelector('[data-slot="thumbnail"]');
  return {
    size: card.dataset.size ?? '',
    name: named(card),
    typeLabel: card.querySelector('[data-slot="entity-card-name"] ~ div span:last-child, .text-muted-foreground span')?.textContent.trim() ?? '',
    badges: badges.length,
    status: badges[0]?.textContent.trim() ?? '',
    thumb: thumb ? Math.round(thumb.getBoundingClientRect().height) : 0,
    // A number in the grid is tabular but never right-aligned: a card is not a table.
    grid,
  };
}

const seen = held.map(describe);
held[0].scrollIntoView({ block: 'center' });
await wait(300);

return { verdict: `PASS ${seen.length} cards loaded`, cards: seen };
