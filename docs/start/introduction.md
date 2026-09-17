---
title: Introduction
description: What sg-widgets is and how the pieces fit.
---

sg-widgets is a set of shadcn-compatible widgets for Flow Production Tracking (formerly ShotGrid).
::qt-note

- `@sg-widgets/core` is a headless TypeScript package: field data types and their filter operators, a filter tree that serialises to the REST API, status logic, and a client adapter.
- The React widgets are a shadcn registry built on Base UI.
- The Svelte widgets are a shadcn-svelte registry built on Bits UI.
::qt-note

Both registries consume only shadcn design tokens, so they follow your theme. A widget installs the shadcn primitives it is built on.
::qt-note

Everything else a page needs, a tooltip, tabs, an accordion, a sheet, a toast, comes from [shadcn/ui](https://ui.shadcn.com/docs/components) for React and [shadcn-svelte](https://shadcn-svelte.com/docs/components) for Svelte, installed the same way. The registry carries no item of its own for them.
::qt-note
