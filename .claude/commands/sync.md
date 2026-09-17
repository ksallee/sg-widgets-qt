---
description: Port what changed in ~/dev/sg-widgets since the last sync, item by item, with one agent per item
---

Scope: $ARGUMENTS (empty means everything the status tool lists; an item name or a kind such as
`widgets` narrows it)

The source of truth is `~/dev/sg-widgets` on `dev`. `sync/manifest.json` records what this repo
ports and the hash each upstream file had then. This command brings the repo back level.

1. `git -C ~/dev/sg-widgets pull --ff-only` if the checkout is clean, then
   `python tools/sync_status.py --json`. Read the three lists and the upstream log since the
   recorded commit. Say back, in one line per item, what drifted and what is new.
2. Order the work by dependency: `core/*` first, then `primitives/*`, then `widgets/*` in the
   sidebar order of `apps/site/astro.config.mjs`, each widget with its `demos/<name>` and
   `docs/<name>`. An item whose upstream is only a comment or a class-string change still gets a
   read; it may change a pixel value in `docs/design-rules.md`.
3. For each item, one agent, in parallel where items are independent. The agent reads the
   upstream file at the current and the recorded state (`git -C ~/dev/sg-widgets diff <commit> HEAD -- <path>`),
   reads the ported file, applies the change under `docs/porting-conventions.md`, ports any test
   that changed, runs `pytest` on both environments for the files it touched, and for a widget
   runs `tools/qa.py` for one light and one dark shot. It ends with
   `python tools/sync_record.py <item> --upstream ... --ported ... --status ...`.
4. A new upstream item is a full port under the order in `CLAUDE.md`: core model and tests, the
   widget, its demo, its tables, its docs page, its tests, the shots, the record.
5. A change this repo cannot take (a browser-only concern, a primitive Qt has no equal for) is
   recorded `--status skipped --note "<why>"` and listed in `STATUS.md` under Not ported.
6. Run the whole suite on both environments once every agent has reported. Update `STATUS.md`.
   Commit per item, message in the upstream's style. Finish with `python tools/sync_status.py`
   and say what is still listed.
