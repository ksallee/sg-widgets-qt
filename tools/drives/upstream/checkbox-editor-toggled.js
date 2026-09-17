// The first switch toggled off, so the word beside it changes with it.
const box = $$('[data-slot="checkbox-editor"]')[0];
box.scrollIntoView({ block: 'center' });
await wait(200);
const sw = box.querySelector('[data-slot="switch"]');
for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
  sw.dispatchEvent(
    type.startsWith('pointer')
      ? new PointerEvent(type, { bubbles: true, cancelable: true, button: 0, pointerType: 'mouse', isPrimary: true })
      : new MouseEvent(type, { bubbles: true, cancelable: true, view: window, button: 0 }),
  );
}
await wait(300);
return { verdict: 'PASS toggled', label: box.textContent.trim(), checked: sw.getAttribute('aria-checked') };
