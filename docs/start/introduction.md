---
title: Introduction
description: What sg-widgets-qt is and how the pieces fit.
---

sg-widgets-qt is a set of widgets for Flow Production Tracking (formerly ShotGrid) on Qt.

- `sg_widgets_core` has no Qt: field data types and their filter operators, a filter tree that serialises to the API, status logic, formatters, parsers, the `SgClient` protocol, `ShotgunClient` on shotgun_api3, `MockClient` over generated fixtures, the [context](../core/context.md), and the schema and status services.
- `sg_widgets_qt` is the Qt half: the theme, the primitives, the widgets and the showcase.

Python 3.9 is the floor. Qt comes through [qtpy](https://github.com/spyder-ide/qtpy), so one widget
runs on PySide2, PySide6, PyQt5 and PyQt6, and it binds to whichever of them the host loaded first.

A widget reads a site through the client and nothing else, and a widget is drawn by its own painter,
so it wears the theme rather than the host's stylesheet.

This is a port of [sg-widgets](https://github.com/ksallee/sg-widgets), whose React and Svelte
widgets carry the same names, props and behaviour. What the core claims about the API is measured
in [sg-groundtruth](https://github.com/ksallee/sg-groundtruth), and each claim is cited where it is
relied on.

Everything else a window needs, a tab bar, a dock, a menu, a message box, comes from Qt itself.
This package carries no widget of its own for them.
