---
title: Install
description: How a host app installs the widgets, and the one line it runs by hand.
---

One command installs every item of a registry.
::qt-note

```sh
pnpm dlx shadcn@latest add https://sg-widgets.dev/r/react/sg-widgets.json
pnpm dlx shadcn-svelte@latest add https://sg-widgets.dev/r/svelte/sg-widgets.json
```

A widget page names its own item, for a host that wants one widget rather than the set.

Run `init` first. It writes `components.json`, the stylesheet and `lib/utils`, and installs the
packages those need. Every item imports `lib/utils`, and no item generates it.

Every item names `@sg-widgets/core`. That package is not on npm. The CLI installs an item's packages
in one call, and the call fails on that name, so it installs nothing. Run the line for your
framework before `add`, with core pointed at a local checkout.

```sh
pnpm add @sg-widgets/core@link:../sg-widgets/packages/core \
  @base-ui/react lucide-react class-variance-authority \
  @tanstack/react-table @tanstack/react-virtual \
  cn react-day-picker date-fns tw-animate-css
```

```sh
pnpm add @sg-widgets/core@link:../sg-widgets/packages/core \
  bits-ui @lucide/svelte @internationalized/date \
  @tanstack/svelte-table @tanstack/virtual-core \
  clsx tailwind-merge tailwind-variants tw-animate-css
```

Each line is the union of what the items name and what the shadcn primitives they pull import. A
host installing one widget needs less.
::qt-note

With the line in place, `shadcn add` names only the packages `package.json` lacks, so its call
succeeds and the files land. `shadcn-svelte add` writes the files first and then fails on its
install call. Either way `package.json` is left as it was, `link:` included.
::qt-note

This registry ships its own `command` and `popover` for React, and its own `command`, `select` and
`checkbox` for Svelte. A host that already has a primitive of that name is asked before it is
overwritten. Accept, or pass `--overwrite`. A host that keeps its own `command` has no status part,
and `search-control` fails to compile against it; one that keeps its own `popover` has no
`positionMethod`, and the date editors fail the same way.
::qt-note
