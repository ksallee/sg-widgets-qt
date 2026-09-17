// The md date-time-editor with its popover open on the typed day, the grid and the time.
//
// The shot of this state is the page, not the surface: Base UI places the surface from the anchor
// rect it measured when the press landed, and a press dispatched from inside the page leaves it
// above the viewport, where no screenshot reaches it. What the surface holds is what this drive
// counts and returns; the Qt half grabs its own surface as `shots/date-time-editor-open-popup.png`.
const row = $('[data-demo-row="md"]') ?? document;
row.scrollIntoView({ block: 'start' });
await wait(400);
const trigger = row.querySelector('[data-slot="date-time-editor-trigger"]');
for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
  trigger.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, button: 0 }));
}
await wait(500);
const open = $$('[data-slot="popover-content"]').filter((el) => el.checkVisibility());
const surface = open[0];
return {
  verdict: open.length ? 'PASS open' : 'FAIL the popover did not open',
  inputs: open.flatMap((el) => [...el.querySelectorAll('input')]).length,
  grids: open.flatMap((el) => [...el.querySelectorAll('table')]).length,
  padding: surface ? getComputedStyle(surface).padding : '',
  gap: surface ? getComputedStyle(surface).rowGap : '',
  order: surface ? [...surface.children].map((el) => el.tagName.toLowerCase()).join(',') : '',
};
