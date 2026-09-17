// The narrow ellipsis control: whole chips, then +n for the rest, on one line.
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
const box = $("[data-demo-summary=\"ellipsis-narrow\"]", pane);
if (!box) return { verdict: "FAIL no narrow ellipsis demo" };
box.scrollIntoView({ block: "center" });
await wait(600);
const chips = $$("[data-chip]", box);
const pill = $("[data-slot$=\"-overflow\"]", box) ?? $("[data-overflow]", box);
return {
  verdict: "PASS overflow",
  shown: chips.length,
  pill: pill ? pill.textContent.trim() : "",
  height: Math.round($("[data-slot$=\"-control\"]", box).getBoundingClientRect().height),
  width: Math.round($("[data-slot$=\"-control\"]", box).getBoundingClientRect().width),
};
