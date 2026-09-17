# sg-widgets-qt

Flow Production Tracking widgets for Qt. A port of `~/dev/sg-widgets` (the source of truth) to
Python on qtpy and shotgun_api3, with the same showcase: one page per widget, a live demo, the
props, events, slots and keyboard tables, and the docs prose.

## Source of truth

`~/dev/sg-widgets`, branch `dev`. Every module, widget, demo, props file and docs page here ports
one there. `sync/manifest.json` records which upstream files each item ports and their content
hash at the last sync. `python tools/sync_status.py` lists what drifted. `/sync` ports it.

Read the upstream file before porting it. Port behaviour, names and tests one for one; where Qt
or Python forces a difference, `docs/porting-conventions.md` says how, and the item's docs page
says what differs.

## Layout

| path | what |
|---|---|
| `src/sg_widgets_core/` | Port of `packages/core`. No Qt. Synchronous. Importable anywhere. |
| `src/sg_widgets_qt/theme/` | Tokens, palettes, QSS generation, radius, density. |
| `src/sg_widgets_qt/primitives/` | The shadcn primitives as custom-painted Qt widgets. |
| `src/sg_widgets_qt/widgets/` | One module per registry item, same name in snake_case. |
| `src/sg_widgets_qt/showcase/` | The app: sidebar, pages, demo stage, toolbar, tables, prose. |
| `src/sg_widgets_qt/showcase/demos/<name>.py` | One demo per widget page, ported from `apps/site/src/demos/<name>/Demo.tsx`. |
| `docs/widgets/<name>.md` | The docs prose, ported from `apps/site/src/content/docs/widgets/<name>.mdx`. |
| `docs/widgets/<name>.props.json` | The tables, ported from `apps/site/src/props/<name>.ts`. |
| `tests/core/` | Port of `packages/core/test`, one file per module, pytest. |
| `tests/qt/` | Widget tests on pytest-qt, offscreen. |
| `tools/` | `sync_status.py`, `sync_record.py`, `qa.py`, `export_palettes.py`, `lucide.py`. |
| `sync/manifest.json` | The port ledger. Written by `tools/sync_record.py`, never by hand. |
| `STATUS.md` | What is ported, what is partial, what is left, per item. |

## Rules

- Python 3.9 is the floor. `from __future__ import annotations` in every module. Modern syntax (`X | None`, `list[str]`) in
  annotations only; nothing evaluated at runtime may need 3.10 (`match`, `X | Y` in `isinstance`,
  `list[str]()`, `zip(strict=)`, `str.removeprefix` is fine, `dataclass(slots=)` is not).
- Qt through `qtpy` only. Never import `PySide6`, `PySide2`, `PyQt5` or `PyQt6` directly. Code runs
  on Qt 5.15 and Qt 6: no Qt 6-only API without a guard, enum access through the class
  (`Qt.AlignmentFlag.AlignLeft` works on both through qtpy's compat; prefer that spelling).
- The client is `shotgun_api3` behind the `SgClient` protocol. Never `fpt-api`, never the REST
  client. The mock is the other implementation and every demo and test runs on it.
- API behaviour comes from `~/dev/sg-groundtruth/corpus` (read `INDEX.md` first) and from the
  upstream comment that cites it. Keep every citation (`probe 009`, `field_types/status_list`).
  Do not guess API behaviour.
- Never read `~/dev/fpt-ai`, `~/dev/flow-data-api-docs`, `~/dev/flow-data-sdk-python`, `~/dev/fpt-api`.
- `~/dev/tk-framework-qtwidgets` and the other `~/dev/tk-*` checkouts, and Qt widget libraries
  found elsewhere (qfluentwidgets, qt-material, QDarkStyle), are inspiration only. Never copy a
  line. Name the file an idea came from in the widget's docs page under Reference.
- Widgets are custom drawn and modern. A stock `QComboBox`, `QPushButton` or `QCheckBox` look is a
  defect. Follow `docs/design-rules.md`: tokens, the spacing scale, the height ladder, painted
  focus rings, chips, popovers that fade and slide, skeletons that shimmer, reduced motion.
- Widgets never block the GUI thread. Reads run through `sg_widgets_qt.workers`; a ticket drops a
  stale answer. No `asyncio`.
- No new runtime dependency beyond `qtpy`, `shotgun_api3` and `typing_extensions` on 3.9/3.10.
  Dev dependencies are in `pyproject.toml`; a new one needs a line in `docs/DESIGN.md`.
- Order per widget: core model and tests, then the widget, its demo, its tables, its docs page, its
  tests, one light and one dark screenshot through `tools/qa.py`, then `tools/sync_record.py`.
- Never copy code from `~/Downloads`. Ideas only.
- Invented names only in demos, tests and docs. The test site, its hostname, projects and people are
  never named; say "the test site".

## Verifying UI

`python tools/qa.py --page <name> --shot shots/<name>-light.png` starts the showcase offscreen,
opens a page and screenshots it; `--dark`, `--palette`, `--radius`, `--reduced-motion`, `--qt5`
(runs on the PyQt5 environment), `--drive file.py` runs a function against the page and prints its
return as JSON; a drive that asserts returns `{"verdict": "PASS ..."}` or `{"verdict": "FAIL ..."}`
and the exit code follows. `--live` reads the test site instead of the mock, read-only.

`qa.py` comes last. Read the code, write the change, get `pytest` green on both environments,
then run one drive and one light and one dark shot per widget.

## Commands

    uv run pytest                                  # PySide6, Python 3.9
    QT_API=pyqt5 .venv-qt5/bin/python -m pytest    # PyQt5, Python 3.9
    .venv/bin/python -m sg_widgets_qt.showcase     # the showcase
    .venv/bin/python tools/qa.py --page entity-picker --shot shots/entity-picker-light.png
    .venv/bin/python tools/sync_status.py          # what drifted upstream
    .venv/bin/ruff check src tests tools

## Writing

Follow `docs/writing-rules.md` for docs pages, docstrings, comments, STATUS.md and commit messages.

## Secrets

`.env.local`, gitignored, never printed: `FPT_API_SITE_URL`, `FPT_API_SCRIPT_NAME`,
`FPT_API_API_KEY`, `FPT_PROBE_SANDBOX_PROJECT`. Reads may touch any project on the test site.
Writes go to the sandbox project only and are deleted by the test that made them.
