// The orchestration every upstream measure drive ends with: the pane at rest and with the widget
// open, in light and in dark, so one browser run answers the four states the diff reads.
const OUT = {};
async function settle(ms) { await wait(ms); }
await until(() => pane.querySelector('[data-slot]'), 15000);
await settle(900);
OUT['rest-light'] = measureAll('rest');
await openIt();
await settle(700);
OUT['open-light'] = measureAll('open');
await closeIt();
await settle(300);
harness.set({ theme: 'dark' });
document.documentElement.classList.add('dark');
document.documentElement.dataset.theme = 'dark';
await settle(700);
OUT['rest-dark'] = measureAll('rest');
await openIt();
await settle(700);
OUT['open-dark'] = measureAll('open');
return { verdict: 'PASS measured', states: OUT };
