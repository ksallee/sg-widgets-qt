---
title: Core
description: The headless package every widget is built on.
---

`@sg-widgets/core` has no framework and no dependencies. It holds what the widgets share:

- **[Client](client.md)**: `RestClient` for the REST API, `ProxyClient` for an app's own endpoints with a matching server handler, `MockClient` for tests, and the [context](context.md), the one object an app builds and hands to every widget: the cached client, the schema and status services, the site url and the site preferences. A client reads rows, the schema, the status table, the navigation tree, a note thread and what a person follows, and it reads the event log for what changed. It writes too: it creates a row, changes one, and puts a file on one.
- **Schema**: the schema service, field data types and the operators each accepts, status vocabularies with per-project hidden values.
- **Filters**: the filter tree, its serialisation to the API, and the operator presets the editor offers.
- **Rendering**: formatters for every data type, initials, display names, the stock status icons.
- **Editing**: parsers for what a person types and the shape the API stores.

The package is not published yet. Until it is, it is linked from a checkout of the repo, as the
[install page](../start/install.md) shows.

```sh
pnpm add @sg-widgets/core@link:../sg-widgets/packages/core
```
