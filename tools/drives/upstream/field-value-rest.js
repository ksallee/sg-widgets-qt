// Every data type as upstream renders it, once the demo's read has landed.
//
//   pnpm qa --start --path /widgets/field-value/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/field-value-rest.js \
//     --shot /tmp/ref/field-value-rest.png
//
// The Qt half is `tools/drives/states/field-value.py` with `QA_STATE=rest`. The table is read row
// by row rather than only shot, because what has to match per data type is the string core's
// `fieldText` gave the value and which atom drew it, and a shot of 26 rows cannot be diffed by
// eye. `kind` names the atom: the slot a chip, a badge, a picture or a switch carries, else the
// text. Both framework islands stay mounted whichever the toolbar is on, and a hidden pane has no
// layout, so only the drawn one is read.

const drawn = () => $$('[data-pane]').find((pane) => pane.getBoundingClientRect().height > 0);
const table = () => drawn()?.querySelector('table') ?? null;
const rows = () => (table() ? [...table().querySelectorAll('tbody tr')] : []);

for (let i = 0; i < 60 && rows().length < 20; i += 1) await wait(250);
if (rows().length === 0) return { verdict: 'FAIL the drawn pane holds no data types' };

// A picture is read after the row, so the run waits for it the way the Qt half does.
const pictures = () => [...(drawn()?.querySelectorAll('img') ?? [])];
for (let i = 0; i < 24 && pictures().some((img) => !img.complete); i += 1) await wait(250);
await wait(400);

function kindOf(cell) {
  if (cell.querySelector('[data-slot="entity-chip"]')) return 'chip';
  if (cell.querySelector('[data-slot="status-badge"]')) return 'badge';
  if (cell.querySelector('[data-slot="thumbnail"]')) return 'image';
  if (cell.querySelector('[data-slot="switch"],[role="switch"]')) return 'switch';
  if (cell.querySelector('a[href]')) return 'link';
  if (cell.querySelector('time')) return 'time';
  if (cell.querySelector('.italic')) return 'empty';
  return 'text';
}

const seen = rows().map((row) => {
  const cell = row.querySelector('td');
  const value = cell?.querySelector('[data-slot="field-value"]') ?? cell;
  const inner = value?.firstElementChild ?? value;
  const style = inner ? getComputedStyle(inner) : null;
  return {
    label: row.querySelector('th')?.textContent.trim() ?? '',
    text: (cell?.textContent ?? '').trim(),
    kind: cell ? kindOf(cell) : 'none',
    // Right alignment and tabular figures are what the Qt port claims for a number.
    align: value ? getComputedStyle(value).justifyContent : '',
    variant: style?.fontVariantNumeric ?? '',
    family: (style?.fontFamily ?? '').split(',')[0],
    // The mark on a link that leaves the application, which upstream does not draw.
    externalMark: Boolean(cell?.querySelector('a svg')),
    title: value?.getAttribute('title') ?? '',
  };
});

table()?.scrollIntoView({ block: 'center' });
await wait(300);

return { verdict: `PASS ${seen.length} data types drawn`, rows: seen };
