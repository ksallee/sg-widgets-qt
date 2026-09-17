---
title: Context
description: The one object an app builds and hands to every widget.
---

A context holds a cached client, the schema service, the status table, the site it reads from and the
preferences the formatters need. An app builds one and passes it to every widget, so two widgets
asking for the same type's fields cost one request.

```python
from sg_widgets_core import MOCK_NOW, MockClient, SgContextOptions, create_sg_context

client = MockClient(seed=1, now=MOCK_NOW)
context = create_sg_context(
    client,
    SgContextOptions(
        site_url="https://studio.shotgrid.autodesk.com",
        hours_per_day=8,
        locale="en-GB",
        time_zone="Europe/Paris",
        frame_rate=23.976,
    ),
)
```

## Options

The client is the first argument. `SgContextOptions` carries the rest, and every field of it has a
default.

| option | type | default | meaning |
|---|---|---|---|
| `ttl_ms` | `float` | `30000` | How long a row read stays fresh. |
| `site_url` | `str` | `None` | The web app the data comes from, so a widget can link a row to its page. |
| `hours_per_day` | `float` | `None` | The site's working day. Durations then render in days. |
| `locale` | `str` | `en-US` | Used for dates, numbers and currency. One of `en-US`, `en-GB`, `fr-FR`, `de-DE` and `ja-JP`; any other name renders as `en-US`. |
| `time_zone` | `str` | UTC | IANA zone a `date_time` is shown in, resolved through `zoneinfo`. |
| `frame_rate` | `float` | `None` | Frames a second. A timecode then renders as `HH:MM:SS:FF`. |

## What it carries

| member | meaning |
|---|---|
| `client` | The cached client. Widgets read rows through this one. |
| `schema` | Types, fields, dotted paths and status vocabularies. |
| `statuses` | The site's Status table, indexed by code. |
| `site_url` | The site url without its trailing slash. Empty when the app named none. |
| `preferences` | The four preferences above, the ones that were given. |
| `invalidate()` | Drops everything cached. Call it after a write. |

Rows go stale at `ttl_ms`. Schema and the Status table are site configuration and keep an hour of their
own, shared between the two services.

## Preferences

The preferences are display decisions the field schema does not carry. `GET /preferences` names
`duration_units` and `hours_per_day`, the pair behind a duration (`field_types/duration`). Nothing on
the site names the frame rate behind a timecode: no schema property, no preference and no related
field. A `_summarize` grouping renders one, and solving the rate out of that gives 23.976 on the
probed site (`field_types/timecode`), so the app passes it in.

`preferences_of` returns the subset the formatters take, as the `FieldTextOptions` `field_text`
wants. A caller that adds one more option copies it with that field changed.

```python
import dataclasses

from sg_widgets_core import field_text, preferences_of

display_values = context.schema.fields("Shot")["sg_status_list"].display_values
options = dataclasses.replace(preferences_of(context), display_values=display_values)
text = field_text("ip", "status_list", options)
```

## From a client alone

A widget handed a client and no context builds one with `context_from_client`. The same client always
returns the same context, so widgets that share a client share its caches.

```python
from sg_widgets_core import context_from_client

context = context_from_client(client)
```

The options are read on the first call for a client. A later call returns the context that one built.
