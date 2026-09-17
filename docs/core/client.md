---
title: Client
description: The one interface every widget reads through, and what it writes.
---

A client is an `SgClient`, a protocol with one synchronous method per call. `ShotgunClient` speaks to
a site through shotgun_api3, and `MockClient` answers from a generated site. The upstream
`RestClient` and `ProxyClient` are not ported: they carry a token and a proxy endpoint through a
browser, and a Qt application holds its own credentials and calls the Python API directly.

```python
from sg_widgets_core import ShotgunClient

client = ShotgunClient.from_env()
```

`from_env` reads `FPT_API_SITE_URL`, `FPT_API_SCRIPT_NAME` and `FPT_API_API_KEY`. One
`shotgun_api3.Shotgun` is built per thread, because a connection is not thread-safe.

Every example below runs against the mock instead, so the writes land nowhere.

```python
from sg_widgets_core import MOCK_NOW, MockClient, create_query_cache

client = create_query_cache(MockClient(seed=1, now=MOCK_NOW))
```

The cache remembers reads for `ttl_ms` and drops what a write makes stale: a row read of the type the
write touched, and every note thread.

## Reads

### A note thread

`thread_contents` answers a Note, its Attachments and its Replies as one list in time order. The
author sits under `created_by` on a Note and an Attachment and under `user` on a Reply, and the
row exposes it as `author` whichever key it came from. A Reply's author carries an avatar the other
two do not.

```python
thread = client.thread_contents(11030, {"Note": ["subject", "sg_status_list"]})
for row in thread:
    print(row.type, row.created_at, row.author.name if row.author else None, row.content or "")
```

The second argument widens a row type by extra fields. It works on Note and Attachment; the Reply
entry is accepted and changes nothing, so extra Reply fields come from a search on replies
(`get_entity_notes_id_thread_contents`).

### The event log

`event_log` answers what changed, newest first. It is never cached. The cut is made on the project,
the entity, the event type, the attribute and a date window; `meta` holds the old and new values
and takes no filter, so the client lifts them out of each row.

```python
from sg_widgets_core import EntityRef, EventLogOptions

result = client.event_log(
    EventLogOptions(
        entity=EntityRef(type="Shot", id=862),
        attribute_name="sg_status_list",
        page={"size": 5},
    )
)
for event in result.data:
    print(event.created_at, event.old_value, "->", event.new_value)
```

`event_log_filters` builds the same cut as a filter group, for a search of your own.

```python
from sg_widgets_core import event_log_filters

filters = event_log_filters(
    EventLogOptions(project_id=70, event_type=["Shotgun_Shot_Change", "Shotgun_Version_Change"])
)
```

Ids at the head of the log are sparse and fill in later, so a cursor on the highest id seen drops
events: re-scan a window behind the head or drive the feed from `created_at` and deduplicate on
`id` (`025_event_log`).

### What a person follows

`following` answers every row one person follows, as a type and an id each, in one unpaged body.
It takes a type to keep and a project to cut on. The person is a HumanUser: a script cannot ask
what it follows (`get_entity_human_users_id_following`).

```python
from sg_widgets_core import FollowingOptions, SearchOptions

followed = client.following(20, FollowingOptions(entity="Task", project_id=70))
rows = client.search(
    "Task",
    SearchOptions(
        filters={"logical_operator": "and", "conditions": [["id", "in", [ref.id for ref in followed]]]},
        fields=["content", "sg_status_list"],
    ),
)
```

## Writes

### A row

`create` posts one row and answers it. `project` is the whole contract on a project-scoped type; the
field the schema flags mandatory is optional, and the server fills the identity field when it is
left out. An entity link is a `{type, id}` hash, never a bare id (`012_create_version`).

```python
note = client.create(
    "Note",
    {
        "project": {"type": "Project", "id": 70},
        "subject": "Key light reads flat",
        "content": "Lift the fill on the left side.",
        "note_links": [{"type": "Shot", "id": 862}],
    },
)
reply = client.create("Reply", {"entity": {"type": "Note", "id": note.id}, "content": "On it."})
```

The answer echoes the server's defaults, so read them off `note.values`: a fresh Note is `unread` and
`published` (`entity_types/Note`). A create takes `created_at` although the schema flags it
read-only; a later update refuses it (`070_authored_timestamps`).

### A file

`upload` puts a file on a row in the three calls the API takes: a ticket, a PUT of the bytes to
storage, and a completing POST. The field in the path picks the kind: `image` is a Thumbnail,
another field an Attachment on that field, and no field a generic Attachment on the row
(`recipes/001`).

```python
from sg_widgets_core import UploadFile

uploaded = client.upload(
    "Note",
    note.id,
    UploadFile(filename="key-light.txt", data=b"Lift the fill on the left side.\n", field="attachments"),
)
print(uploaded.upload_type, uploaded.etag)
```

`data` is the bytes themselves; a file on disk is `Path(name).read_bytes()`.

The status of the PUT is the receipt; `etag` is present when the storage exposes one. A media field
is not readable straight after: it answers a placeholder under `/images/status/transient/` on the
site root until the transcode lands (`013_upload_media`).
