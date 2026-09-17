---
title: Core
description: The headless package every widget is built on.
---

`sg_widgets_core` has no Qt and no dependency beyond shotgun_api3. It holds what the widgets share:

- **[Client](client.md)**: `ShotgunClient` for a site over shotgun_api3, `MockClient` for demos and tests, and the [context](context.md), the one object an app builds and hands to every widget: the cached client, the schema and status services, the site url and the site preferences. A client reads rows, the schema, the status table, the navigation tree, a note thread and what a person follows, and it reads the event log for what changed. It writes too: it creates a row, changes one, and puts a file on one.
- **Schema**: the schema service, field data types and the operators each accepts, status vocabularies with per-project hidden values.
- **Filters**: the filter tree, its serialisation to the API, and the operator presets the editor offers.
- **Rendering**: formatters for every data type, initials, display names, the stock status icons.
- **Editing**: parsers for what a person types and the shape the API stores.

Everything here is synchronous, and nothing here touches a GUI thread. A Qt widget runs a read on a
worker, as `sg_widgets_qt.workers` does.

The package ships in the same distribution as the widgets, as the
[install page](../start/install.md) shows.

```sh
pip install sg-widgets-qt
```

```python
from sg_widgets_core import MockClient, create_sg_context
```
