// The project picker page as it settles, nothing open.
function press(el) {
  for (const t of ["pointerdown", "mousedown", "pointerup", "mouseup"])
    el.dispatchEvent(new PointerEvent(t, { bubbles: true, cancelable: true, button: 0, pointerType: "mouse" }));
  el.click();
}
function type(input, text) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, text);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}
function key(el, name) {
  el.dispatchEvent(new KeyboardEvent("keydown", { key: name, bubbles: true, cancelable: true }));
  el.dispatchEvent(new KeyboardEvent("keyup", { key: name, bubbles: true, cancelable: true }));
}
async function until(read, t = 10000) {
  const d = Date.now() + t;
  for (;;) { const v = read(); if (v) return v; if (Date.now() > d) return null; await wait(50); }
}
const pane = $$("[data-pane]").find((p) => p.offsetParent !== null);
await until(() => $$("[data-slot$=\"-control\"]", pane).length > 0, 15000);
await wait(800);
const controls = $$("[data-slot$=\"-control\"]", pane).filter((el) => el.getClientRects().length > 0);
const control = controls[0];
control.scrollIntoView({ block: "start" });
await wait(300);
return { verdict: "PASS rest", controls: controls.length };
