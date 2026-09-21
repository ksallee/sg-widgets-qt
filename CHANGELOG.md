# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[semantic versioning](https://semver.org/spec/v2.0.0.html). While the version is 0.x, a minor
release may change a name, a prop or a signal.

## [Unreleased]

## [0.1.0] - 2026-09-20

First release, from the port of [sg-widgets](https://github.com/ksallee/sg-widgets).

### Added

- `sg_widgets_core`: field data types and their operators, the filter tree and its serialisation,
  status logic, formatters, parsers, the query cache, the `SgClient` protocol, `ShotgunClient` on
  shotgun_api3 and `MockClient` over generated fixtures. No Qt.
- `sg_widgets_qt`: the theme with light and dark palettes, the painted primitives, and the widgets:
  thumbnails, avatars, the field editors, the pickers for entities, fields, statuses and columns,
  the entity table, grid, tree and card, the collection and search controls, and the filter editor.
- The showcase, `python -m sg_widgets_qt.showcase`: one page per widget with a demo, the props,
  signals, slots and keyboard tables, and the prose. It runs on the mock site, and on a live site
  through `.env.local`.
- `py.typed` in both packages.
- Gates on every pull request and on pushes to `dev` and `main`: ruff, and pytest offscreen on
  PySide6 and on PyQt5, on Python 3.9.
- Release to PyPI by trusted publishing when a GitHub release is published.

[Unreleased]: https://github.com/ksallee/sg-widgets-qt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ksallee/sg-widgets-qt/releases/tag/v0.1.0
