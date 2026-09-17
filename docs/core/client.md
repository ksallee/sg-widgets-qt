---
title: Client
description: The one interface every widget reads through, and what it writes.
---

A client is an `SgClient`. `RestClient` speaks to the REST API with a token, `ProxyClient` speaks to
an app's own endpoints behind `createProxyHandler`, and `MockClient` answers from a generated site.
Every example below runs against the mock, so the writes land nowhere.

```ts
import { MockClient, createQueryCache } from '@sg-widgets/core';

const client = createQueryCache(new MockClient());
```

The cache remembers reads for `ttlMs` and drops what a write makes stale: a row read of the type the
write touched, and every note thread.

## Reads

### A note thread

`threadContents` answers a Note, its Attachments and its Replies as one list in time order. The
author sits under `created_by` on a Note and an Attachment and under `user` on a Reply, and the
row exposes it as `author` whichever key it came from. A Reply's author carries an avatar the other
two do not.

```ts
const thread = await client.threadContents(11030, { Note: ['subject', 'sg_status_list'] });
for (const row of thread) {
  console.log(row.type, row.createdAt, row.author?.name, row.content ?? '');
}
```

The second argument widens a row type by extra fields. It works on Note and Attachment; the Reply
entry is accepted and changes nothing, so extra Reply fields come from a search on replies
(`get_entity_notes_id_thread_contents`).

### The event log

`eventLog` answers what changed, newest first. It is never cached. The cut is made on the project,
the entity, the event type, the attribute and a date window; `meta` holds the old and new values
and takes no filter, so the client lifts them out of each row.

```ts
const { data } = await client.eventLog({
  entity: { type: 'Shot', id: 862 },
  attributeName: 'sg_status_list',
  page: { size: 5 },
});
for (const event of data) console.log(event.createdAt, event.oldValue, '->', event.newValue);
```

`eventLogFilters` builds the same cut as a filter group, for a search of your own.

```ts
import { eventLogFilters } from '@sg-widgets/core';

const filters = eventLogFilters({ projectId: 70, eventType: ['Shotgun_Shot_Change', 'Shotgun_Version_Change'] });
```

Ids at the head of the log are sparse and fill in later, so a cursor on the highest id seen drops
events: re-scan a window behind the head or drive the feed from `createdAt` and deduplicate on
`id` (`025_event_log`).

### What a person follows

`following` answers every row one person follows, as a type and an id each, in one unpaged body.
It takes a type to keep and a project to cut on. The person is a HumanUser: a script cannot ask
what it follows (`get_entity_human_users_id_following`).

```ts
const followed = await client.following(20, { entity: 'Shot', projectId: 70 });
const rows = await client.search('Shot', {
  filters: { logical_operator: 'and', conditions: [['id', 'in', followed.map((ref) => ref.id)]] },
  fields: ['code', 'sg_status_list'],
});
```

## Writes

### A row

`create` posts one row and answers it. `project` is the whole contract on a project-scoped type; the
field the schema flags mandatory is optional, and the server fills the identity field when it is
left out. An entity link is a `{type, id}` hash, never a bare id (`012_create_version`).

```ts
const note = await client.create('Note', {
  project: { type: 'Project', id: 70 },
  subject: 'Key light reads flat',
  content: 'Lift the fill on the left side.',
  note_links: [{ type: 'Shot', id: 862 }],
});
const reply = await client.create('Reply', { entity: { type: 'Note', id: note.id }, content: 'On it.' });
```

The answer echoes the server's defaults, so read them off it: a fresh Note is `unread` and
`published` (`entity_types/Note`). A create takes `created_at` although the schema flags it
read-only; a later update refuses it (`070_authored_timestamps`).

### A file

`upload` puts a file on a row in the three calls the API takes: a ticket, a PUT of the bytes to
storage, and a completing POST. The field in the path picks the kind: `image` is a Thumbnail,
another field an Attachment on that field, and no field a generic Attachment on the row
(`recipes/001`).

```ts
const bytes = new Uint8Array(await file.arrayBuffer());
const result = await client.upload('Note', note.id, { filename: file.name, data: bytes, field: 'attachments' });
console.log(result.uploadType, result.etag);
```

The status of the PUT is the receipt; `etag` is present when the storage exposes one. A media field
is not readable straight after: it answers a placeholder under `/images/status/transient/` on the
site root until the transcode lands (`013_upload_media`).
