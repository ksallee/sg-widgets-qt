// A group added at the root, on its own inset surface.
//
//   cd ~/dev/sg-widgets && pnpm qa --start --path /widgets/filter-editor/ --framework react \
//     --drive ~/dev/sg-widgets-qt/tools/drives/upstream/filter-editor-nested.js \
//     --shot /tmp/ref/filter-editor-nested.png
//
// The Qt half is `QA_STATE=nested tools/drives/states/filter-editor.py`.
function press(el) {
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
    el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, button: 0 }));
  }
}

function setValue(el, text) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(el, text);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

async function until(find, label) {
  for (let i = 0; i < 200; i++) {
    const found = find();
    if (found) return found;
    await wait(50);
  }
  throw new Error(`timed out waiting for ${label}`);
}

function openSurfaces() {
  return $$('[data-slot="popover-content"], [data-slot="select-content"]').filter(
    (el) => !el.hasAttribute('data-closed') && el.getAttribute('data-state') !== 'closed' && el.checkVisibility(),
  );
}

function within(selector) {
  return openSurfaces().flatMap((surface) => (surface.matches(selector) ? [surface] : $$(selector, surface)));
}

const closeOverlays = () => until(() => openSurfaces().length === 0 || null, 'the overlays to close');
const fieldList = () => within('[data-picker="field"]')[0] ?? null;
const items = () => (fieldList() ? $$('[data-slot="command-item"]', fieldList()) : []);
const itemFor = (label) => items().find((i) => [...i.querySelectorAll('span')].some((s) => s.textContent.trim() === label));

async function settledItem(label) {
  await wait(150);
  let seen = -1;
  for (let i = 0; i < 200; i++) {
    const count = items().length;
    if (count === seen && itemFor(label)) return itemFor(label);
    seen = count;
    await wait(50);
  }
  throw new Error(`timed out waiting for the ${label} row`);
}

const pane = $('[data-pane="react"]') ?? $('[data-sg-demo]');
// The page draws five editors; the matrix drives the demo's own, which is the first.
const editor = () => $('[data-slot="filter-editor"]', pane);
const rows = () => $$('[data-slot="filter-row"]', editor());
const groups = () => $$('[data-slot="filter-group"]', editor());

async function pickField(row, label) {
  press($('[data-slot="filter-field"] [data-slot="field-picker-trigger"]', row));
  const search = await until(() => (fieldList() ? $('[data-slot="command-input"]', fieldList()) : null), 'the field picker');
  setValue(search, label);
  press(await settledItem(label));
  await closeOverlays();
  await until(
    () => $('[data-slot="filter-field"] [data-slot="field-picker-label"]', row)?.textContent.includes(label),
    `${label} on the row`,
  );
}

async function setPreset(row, id) {
  press($('[data-slot="filter-operator"]', row));
  press(await until(() => within(`[data-slot="select-item"][data-preset="${id}"]`)[0], `the ${id} entry`));
  await closeOverlays();
  await wait(60);
}

await until(() => (editor() && rows().length > 0 ? rows() : null), 'the demo tree');
await until(() => $$('[data-testid="result-count"]').every((p) => p.textContent.trim() !== 'Counting\u2026') || null, 'the count line');
await closeOverlays();

const before = rows().length;
const groupsBefore = groups().length;
press($('[data-slot="filter-add-group"][data-path=""]', editor()));
await until(() => groups().length > groupsBefore || null, 'the new group');

$('[data-sg-demo]')?.scrollIntoView({ block: 'start' });
await wait(500);
return { verdict: `PASS nested`, state: 'nested', rows: rows().length, groups: groups().length };
