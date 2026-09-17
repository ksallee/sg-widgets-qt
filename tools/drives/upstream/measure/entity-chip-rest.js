// The body every measure drive ends with: walk the React pane and report what a pixel-parity
// pass compares. Concatenated into each drive by hand, since qa.mjs runs one file as a function
// body and has no module loader: keep the copies in step.
//
//   pnpm qa --base http://127.0.0.1:4500 --path /widgets/<name>/ --framework react \
//     --drive tools/drives/upstream/measure/<name>-<state>.js
//
// Returns one record per element under `[data-pane="react"]` that carries a `data-slot`, plus
// every control (button, input, textarea, [role]) and every element with a border or a
// background of its own, with its box and the computed values the diff reads.
function measurePane() {
  const pane = document.querySelector('[data-pane="react"]');
  if (!pane) return { verdict: 'FAIL no react pane on the page' };
  const paneBox = pane.getBoundingClientRect();
  const wanted = [
    'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'gap', 'column-gap', 'row-gap',
    'font-size', 'font-weight', 'line-height', 'letter-spacing',
    'color', 'background-color', 'opacity',
    'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
    'border-top-color', 'border-left-color',
    'border-top-left-radius', 'border-top-right-radius',
    'border-bottom-left-radius', 'border-bottom-right-radius',
    'box-shadow', 'text-align', 'display', 'flex-direction', 'align-items', 'justify-content',
  ];
  const isControl = (el) =>
    el.matches('button, input, textarea, select, a[href], [role], [tabindex], svg');
  const seen = [];
  const all = [pane, ...pane.querySelectorAll('*')];
  for (const el of all) {
    const slot = el.getAttribute('data-slot');
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    const painted =
      style.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
      parseFloat(style.borderTopWidth) > 0 ||
      parseFloat(style.borderLeftWidth) > 0;
    // A bare label carries no slot and paints nothing, but its type step, its weight and
    // where its baseline sits are half of what a parity pass compares, so a leaf with text
    // of its own is measured too.
    const leafText = el.children.length === 0 && (el.textContent || '').trim().length > 0;
    if (!slot && !isControl(el) && !painted && !leafText) continue;
    if (box.width === 0 && box.height === 0) continue;
    const values = {};
    for (const name of wanted) values[name] = style.getPropertyValue(name);
    const text = (el.textContent || '').trim().replace(/\s+/g, ' ');
    seen.push({
      slot: slot || null,
      tag: el.tagName.toLowerCase(),
      cls: el.getAttribute('class') || '',
      role: el.getAttribute('role') || null,
      state: el.getAttribute('data-state') || null,
      size: el.getAttribute('data-size') || null,
      disabled: el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true',
      box: {
        x: +(box.left - paneBox.left).toFixed(2),
        y: +(box.top - paneBox.top).toFixed(2),
        w: +box.width.toFixed(2),
        h: +box.height.toFixed(2),
      },
      style: values,
      text: text.length > 80 ? text.slice(0, 80) + '…' : text,
      svg: el.tagName.toLowerCase() === 'svg' ? { w: +box.width.toFixed(2), h: +box.height.toFixed(2) } : null,
    });
  }
  // Where the pane sits in the viewport, so a shot of the page can be sampled at the same
  // points the Qt grab is: a composited colour is the only way to read a translucent token.
  return {
    verdict: `PASS measured ${seen.length} elements`,
    count: seen.length,
    paneAt: { x: +paneBox.left.toFixed(2), y: +paneBox.top.toFixed(2) },
    scroll: { x: window.scrollX, y: window.scrollY },
    elements: seen,
  };
}

// Popovers, menus and hover cards are portalled out of the pane; measure them too.
function measurePortals() {
  const roots = [...document.querySelectorAll(
    '[data-slot="popover-content"], [data-slot="hover-card-content"], [data-slot="command"],' +
    '[data-radix-popper-content-wrapper], [role="dialog"], [role="listbox"], [data-slot="calendar"]'
  )];
  const wanted = [
    'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'gap',
    'font-size', 'font-weight', 'line-height', 'color', 'background-color', 'opacity',
    'border-top-width', 'border-top-color', 'border-top-left-radius', 'box-shadow',
  ];
  const out = [];
  const pushed = new Set();
  for (const root of roots) {
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (pushed.has(el)) continue;
      pushed.add(el);
      const slot = el.getAttribute('data-slot');
      const style = getComputedStyle(el);
      const box = el.getBoundingClientRect();
      if (!slot && !el.matches('button, input, [role], svg')) continue;
      if (box.width === 0 && box.height === 0) continue;
      const values = {};
      for (const name of wanted) values[name] = style.getPropertyValue(name);
      out.push({
        slot: slot || null,
        tag: el.tagName.toLowerCase(),
        cls: el.getAttribute('class') || '',
        box: { w: +box.width.toFixed(2), h: +box.height.toFixed(2) },
        style: values,
        text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60),
      });
    }
  }
  return out;
}

async function settle() {
  await wait(400);
  for (let i = 0; i < 60; i += 1) {
    const busy = document.querySelectorAll('[data-slot="skeleton"], [data-loading="true"]').length;
    if (!busy) break;
    await wait(250);
  }
  await wait(400);
}
await settle();
const out = measurePane();
out.portals = measurePortals();
return out;
