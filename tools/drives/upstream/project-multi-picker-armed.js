// The token field with the caret on its last chip, the state clause 4 leaves behind.
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
const box = $("[data-demo-case=\"tokens\"]", pane);
if (!box) return { verdict: "FAIL no token field demo" };
box.scrollIntoView({ block: "start" });
await wait(500);
const armed = () => $$("[data-chip][data-armed=\"true\"]", box).length;
const input = $("[data-slot$=\"-input\"]", box);
const arm = () => { input.focus({ preventScroll: true }); key(input, "Backspace"); };
arm();
await until(() => armed() > 0);
setInterval(() => { if (armed() === 0) arm(); }, 80);
await wait(600);
return { verdict: "PASS armed", armed: armed(), chips: $$("[data-chip]", box).length };
