---
title: Context
description: The one object an app builds and hands to every widget.
---

A context holds a cached client, the schema service, the status table, the site it reads from and the
preferences the formatters need. An app builds one and passes it to every widget, so two widgets
asking for the same type's fields cost one request.

```ts
const context = createSgContext({
  client,
  siteUrl: 'https://studio.shotgrid.autodesk.com',
  hoursPerDay: 8,
  locale: 'en-GB',
  timeZone: 'Europe/Paris',
  frameRate: 23.976,
});
```

## Options

| option | type | default | meaning |
|---|---|---|---|
| `client` | `SgClient` | required | The client every read goes through. |
| `ttlMs` | `number` | `30000` | How long a row read stays fresh. |
| `siteUrl` | `string` | — | The web app the data comes from, so a widget can link a row to its page. |
| `hoursPerDay` | `number` | — | The site's working day. Durations then render in days. |
| `locale` | `string` | the runtime's | Used for dates, numbers and currency. |
| `timeZone` | `string` | the runtime's | IANA zone a `date_time` is shown in. |
| `frameRate` | `number` | — | Frames a second. A timecode then renders as `HH:MM:SS:FF`. |

## What it carries

| member | meaning |
|---|---|
| `client` | The cached client. Widgets read rows through this one. |
| `schema` | Types, fields, dotted paths and status vocabularies. |
| `statuses` | The site's Status table, indexed by code. |
| `siteUrl` | The site url without its trailing slash. Empty when the app named none. |
| `preferences` | The four preferences above, the ones that were given. |
| `invalidate()` | Drops everything cached. Call it after a write. |

Rows go stale at `ttlMs`. Schema and the Status table are site configuration and keep an hour of their
own, shared between the two services.

## Preferences

The preferences are display decisions the field schema does not carry. `GET /preferences` names
`duration_units` and `hours_per_day`, the pair behind a duration (`field_types/duration`). Nothing on
the site names the frame rate behind a timecode: no schema property, no preference and no related
field. A `_summarize` grouping renders one, and solving the rate out of that gives 23.976 on the
probed site (`field_types/timecode`), so the app passes it in.

`preferencesOf` returns the subset the formatters take, ready to spread.

```ts
fieldText(value, dataType, { ...preferencesOf(context), displayValues });
```

## From a client alone

A widget handed a client and no context builds one with `contextFromClient`. The same client always
returns the same context, so widgets that share a client share its caches.

```ts
const context = contextFromClient(client);
```

The options are read on the first call for a client. A later call returns the context that one built.
