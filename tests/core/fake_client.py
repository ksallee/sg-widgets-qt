"""A small fake `SgClient` for the core tests.

Upstream's tests read `MockClient`; this stands in for it with the fixture values a
test names: the status vocabularies and their `display_values`, the per-project
`hidden_values`, the `bg_color` of a code and the field schemas the pickers walk
(009_status_lists, 010_status_icons, probe 002).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from sg_widgets_core.client import (
    EntityRow,
    EntityTypeInfo,
    EventLogOptions,
    EventLogResult,
    FollowingOptions,
    HierarchyNode,
    HierarchyPath,
    HierarchyRef,
    Page,
    SearchOptions,
    SearchResult,
    SgApiError,
    SgClient,
    SummarizeOptions,
    SummarizeResult,
    TextSearchRow,
    ThreadAuthor,
    ThreadRow,
    UploadFile,
    UploadResult,
)
from sg_widgets_core.filter import EntityRef, TextSearchFilter
from sg_widgets_core.schema import FieldSchema, display_name_of, field_schema_override
from sg_widgets_core.status import ImageMapIcon, StatusRecord

VERSION_STATUSES = [
    "na", "rev", "vwd", "apr", "custom", "fin", "ip", "clsd",
    "cmpt", "cfrm", "pndad", "pndl", "pndvs", "part", "pass", "pndng",
]
TASK_STATUSES = ["wtg", "ip", "fin", "apr", "dis", "na", "hld", "rev", "omt", "ready"]
SHOT_STATUSES = ["wtg", "ip", "rev", "apr", "fin", "hld", "omt"]
SEQUENCE_STATUSES = ["wtg", "ip", "fin"]
NOTE_STATUSES = ["opn", "clsd"]
VERSION_TYPES = ["Type A", "Type B", "Type C"]
SHOT_TYPES = ["VFX", "2D", "Full CG", "Trailer", "Marketing", "Look Dev"]
ASSET_TYPES = ["Character", "Environment", "Prop", "Vehicle", "FX", "Matte Painting"]
#: Project's own status field is a plain `list` with no Status row behind it (entity_types/Project).
PROJECT_STATUSES = ["Active", "Bidding", "Complete", "On Hold"]

#: `display_values` is per site, not per type; a missing key falls back to the raw code (009_status_lists).
STATUS_DISPLAY: dict[str, str] = {
    "na": "N/A", "rev": "Pending Review", "vwd": "Viewed", "apr": "Approved", "custom": "CustomIcon",
    "fin": "Final", "ip": "In Progress", "clsd": "Closed", "cmpt": "Complete", "cfrm": "Confirmed",
    "pndad": "Pending Art Director", "pndl": "Pending Lead", "pndvs": "Pending VFX Supervisor",
    "part": "partial", "pass": "pass", "pndng": "Pending", "wtg": "Waiting to Start", "hld": "On Hold",
    "omt": "Omitted", "dis": "Discarded", "ready": "Ready to Start", "act": "Active", "opn": "Open",
}

#: `bg_color` is comma-separated decimal RGB, never hex (010_status_icons).
STATUS_BG: dict[str, str] = {
    "na": "150,150,150", "wtg": "178,178,178", "ready": "120,190,240", "ip": "43,139,214",
    "rev": "250,190,53", "vwd": "154,113,190", "apr": "25,118,27", "fin": "80,143,66",
    "cmpt": "25,118,27", "cfrm": "52,152,219", "clsd": "90,90,90", "hld": "224,80,80",
    "omt": "128,128,128", "dis": "160,160,160", "part": "200,150,50", "pass": "100,180,100",
    "pndad": "236,151,31", "pndl": "236,151,31", "pndvs": "236,151,31", "pndng": "236,151,31",
    "custom": "255,105,180", "act": "25,118,27", "opn": "236,151,31",
}


def _spec(display_name: str, data_type: str, **rest: Any) -> dict[str, Any]:
    return {"display_name": display_name, "data_type": data_type, **rest}


def _status_spec(valid_values: list[str], default_value: str, mandatory: bool = False) -> dict[str, Any]:
    return _spec(
        "Status",
        "status_list",
        valid_values=valid_values,
        display_values={code: STATUS_DISPLAY.get(code, code) for code in valid_values},
        default_value=default_value,
        mandatory=mandatory,
    )


AUDIT: dict[str, dict[str, Any]] = {
    "id": _spec("Id", "number", editable=False),
    "cached_display_name": _spec("Display Name", "text"),
    "created_at": _spec("Date Created", "date_time", editable=False),
    "updated_at": _spec("Date Updated", "date_time", editable=False),
    "created_by": _spec("Created by", "entity", editable=False, valid_types=["HumanUser", "ApiUser"]),
    "updated_by": _spec("Updated by", "entity", editable=False, valid_types=["HumanUser", "ApiUser"]),
}

SPECS: dict[str, dict[str, dict[str, Any]]] = {
    "Project": {
        **AUDIT,
        "name": _spec("Project Name", "text", mandatory=True, unique=True),
        "code": _spec("Project Code", "text", unique=True),
        "sg_status": _spec("Status", "list", valid_values=PROJECT_STATUSES, default_value="Active"),
        "sg_type": _spec("Type", "list", valid_values=["Feature", "Episodic", "Commercial", "Short"]),
        "sg_description": _spec("Description", "text"),
        "sg_start_date": _spec("Start Date", "date"),
        "sg_end_date": _spec("End Date", "date"),
        "archived": _spec("Archived", "checkbox"),
        "image": _spec("Thumbnail", "image"),
        "users": _spec("Users", "multi_entity", valid_types=["HumanUser"]),
    },
    "Sequence": {
        **AUDIT,
        "code": _spec("Sequence Name", "text", mandatory=True),
        "description": _spec("Description", "text"),
        "sg_status_list": _status_spec(SEQUENCE_STATUSES, "ip"),
        "sg_cut_duration": _spec("Cut Duration", "number"),
        "image": _spec("Thumbnail", "image"),
        "project": _spec("Project", "entity", mandatory=True, valid_types=["Project"]),
        "shots": _spec("Shots", "multi_entity", valid_types=["Shot"]),
    },
    "Shot": {
        **AUDIT,
        "code": _spec("Shot Code", "text", mandatory=True),
        "description": _spec("Description", "text"),
        "sg_status_list": _status_spec(SHOT_STATUSES, "wtg"),
        "sg_shot_type": _spec("Shot Type", "list", valid_values=SHOT_TYPES),
        "sg_cut_in": _spec("Cut In", "number"),
        "sg_cut_out": _spec("Cut Out", "number"),
        "sg_working_duration": _spec("Working Duration", "duration"),
        "sg_turnover_date": _spec("Turnover Date", "date"),
        "sg_complexity": _spec("Complexity", "percent"),
        "sg_omit": _spec("Omitted", "checkbox"),
        "image": _spec("Thumbnail", "image"),
        "sg_shot_notes_url": _spec("Notes URL", "url"),
        "project": _spec("Project", "entity", mandatory=True, valid_types=["Project"]),
        "sg_sequence": _spec("Sequence", "entity", valid_types=["Sequence"]),
        "assets": _spec("Assets", "multi_entity", valid_types=["Asset"]),
        "tasks": _spec("Tasks", "multi_entity", valid_types=["Task"]),
    },
    "Asset": {
        **AUDIT,
        "code": _spec("Asset Name", "text", mandatory=True),
        "description": _spec("Description", "text"),
        "sg_status_list": _status_spec(SHOT_STATUSES, "wtg"),
        "sg_asset_type": _spec("Asset Type", "list", valid_values=ASSET_TYPES),
        "sg_due_date": _spec("Due Date", "date"),
        "image": _spec("Thumbnail", "image"),
        "project": _spec("Project", "entity", mandatory=True, valid_types=["Project"]),
        "shots": _spec("Shots", "multi_entity", valid_types=["Shot"]),
        "tasks": _spec("Tasks", "multi_entity", valid_types=["Task"]),
    },
    "Version": {
        **AUDIT,
        "code": _spec("Version Name", "text", mandatory=True),
        "description": _spec("Description", "text"),
        "sg_department": _spec("Department", "text"),
        "sg_status_list": _status_spec(VERSION_STATUSES, "rev"),
        "sg_version_type": _spec("Version Type", "list", valid_values=VERSION_TYPES, default_value="Type A"),
        "sg_first_frame": _spec("First Frame", "number"),
        "sg_last_frame": _spec("Last Frame", "number"),
        "client_approved": _spec("Client Approved", "checkbox"),
        "client_approved_at": _spec("Client Approved at", "date_time"),
        "image": _spec("Thumbnail", "image"),
        "sg_uploaded_movie": _spec("Uploaded Movie", "url"),
        "sg_bar_color": _spec("Bar Colour", "color"),
        "project": _spec("Project", "entity", mandatory=True, valid_types=["Project"]),
        "entity": _spec("Link", "entity", valid_types=["Shot", "Asset", "Sequence"]),
        "sg_task": _spec("Task", "entity", valid_types=["Task"]),
        "user": _spec("Artist", "entity", valid_types=["HumanUser", "ApiUser"]),
        "playlists": _spec("Playlists", "multi_entity", valid_types=["Playlist"]),
    },
    "Task": {
        **AUDIT,
        "content": _spec("Task Name", "text", mandatory=True),
        "sg_description": _spec("Description", "text"),
        "sg_status_list": _status_spec(TASK_STATUSES, "wtg"),
        "start_date": _spec("Start Date", "date"),
        "due_date": _spec("Due Date", "date"),
        "duration": _spec("Duration", "duration"),
        "milestone": _spec("Milestone", "checkbox"),
        "project": _spec("Project", "entity", mandatory=True, valid_types=["Project"]),
        "entity": _spec("Link", "entity", valid_types=["Shot", "Asset", "Sequence"]),
        "step": _spec("Pipeline Step", "entity", valid_types=["Step"]),
        "task_assignees": _spec("Assigned To", "multi_entity", valid_types=["Group", "HumanUser"]),
        "task_reviewers": _spec("Reviewers", "multi_entity", valid_types=["Group", "HumanUser"]),
    },
    "Note": {
        **AUDIT,
        "subject": _spec("Subject", "text", mandatory=True),
        "content": _spec("Body", "text"),
        "sg_status_list": _status_spec(NOTE_STATUSES, "opn", True),
        "project": _spec("Project", "entity", valid_types=["Project"]),
        "user": _spec("Author", "entity", valid_types=["HumanUser", "ApiUser"]),
        "note_links": _spec("Link", "multi_entity", valid_types=["Shot", "Asset", "Version"]),
        "replies": _spec("Replies", "multi_entity", valid_types=["Reply"]),
        "attachments": _spec("Attachments", "multi_entity", valid_types=["Attachment"]),
    },
    "Reply": {
        "id": AUDIT["id"],
        "cached_display_name": AUDIT["cached_display_name"],
        "created_at": AUDIT["created_at"],
        "content": _spec("Reply Text", "text", mandatory=True),
        "entity": _spec("Link", "entity", valid_types=["Note", "Version", "Shot", "Asset", "Task"]),
        "user": _spec("Author", "entity", valid_types=["HumanUser", "ApiUser"]),
    },
    "Attachment": {
        **AUDIT,
        "display_name": _spec("File Display Name", "text"),
        "filename": _spec("File Name", "text", editable=False),
        "attachment_links": _spec("Attachment Links", "multi_entity", valid_types=["Note", "Version", "Shot"]),
    },
    #: A type with no status field at all, so `status_field` falls back to the conventional name.
    "Icon": {
        **AUDIT,
        "name": _spec("Icon Name", "text"),
        "display_type": _spec("Display Type", "list", valid_values=["image_map", "image", "html"]),
        "image_map_key": _spec("Image Map Key", "text"),
    },
}

DISPLAY_NAMES: dict[str, str] = {
    "Project": "Project", "Sequence": "Sequence", "Shot": "Shot", "Asset": "Asset", "Version": "Version",
    "Task": "Task", "Note": "Note", "Reply": "Reply", "Attachment": "Attachment", "Icon": "Icon",
}

#: Which codes each project hides, per type. `hidden_values` is the only thing
#: `project_id` changes (009_status_lists), and it is not a subset of `valid_values`.
HIDDEN_VALUES: dict[int, dict[str, list[str]]] = {
    70: {
        "Version.sg_status_list": ["part", "pass", "pndad", "pndl", "pndvs", "pndng"],
        "Task.sg_status_list": ["omt", "dis"],
        "Shot.sg_status_list": ["omt"],
        "Asset.sg_status_list": ["omt"],
        "Sequence.sg_status_list": [],
        "Project.sg_status": [],
    },
    71: {
        "Version.sg_status_list": ["pndl", "pndvs"],
        "Task.sg_status_list": ["dis", "hld", "blk"],
        "Shot.sg_status_list": ["hld", "omt"],
        "Asset.sg_status_list": [],
        "Sequence.sg_status_list": [],
        "Project.sg_status": ["On Hold"],
    },
}


def _rows() -> dict[str, list[EntityRow]]:
    """The few rows the tests read, written the way `find` answers them."""
    project = {"type": "Project", "id": 70, "name": "Aurora"}
    return {
        "Project": [
            EntityRow("Project", 70, {"name": "Aurora", "sg_status": "Active"}),
            EntityRow("Project", 71, {"name": "Borealis", "sg_status": "Bidding"}),
        ],
        "Sequence": [EntityRow("Sequence", 300, {"code": "sq001", "project": project})],
        "Shot": [
            EntityRow("Shot", 862, {"code": "sh010", "description": "Wide on the bridge",
                                    "sg_status_list": "ip", "project": project,
                                    "sg_sequence": {"type": "Sequence", "id": 300, "name": "sq001"}}),
            EntityRow("Shot", 863, {"code": "sh020", "description": "Reverse", "sg_status_list": "wtg",
                                    "project": project}),
            EntityRow("Shot", 864, {"code": "sh030", "description": "Insert", "sg_status_list": "fin",
                                    "project": project}),
        ],
        "Asset": [EntityRow("Asset", 1226, {"code": "Lantern", "sg_status_list": "ip", "project": project})],
        "Version": [
            EntityRow("Version", 5100, {"code": "sh010_v001", "sg_status_list": "rev", "project": project,
                                        "entity": {"type": "Shot", "id": 862, "name": "sh010"}}),
            EntityRow("Version", 5101, {"code": "sh020_v001", "sg_status_list": "apr", "project": project}),
        ],
        "Task": [EntityRow("Task", 5700, {"content": "comp", "sg_status_list": "ip", "project": project})],
        "Note": [EntityRow("Note", 11030, {"subject": "Bridge lighting", "content": "Too warm.",
                                           "created_at": "2026-01-05T12:00:00Z", "project": project,
                                           "user": {"type": "HumanUser", "id": 20, "name": "Ada Lovelace"}})],
        "Reply": [],
        "Attachment": [],
    }


def _statuses() -> list[StatusRecord]:
    return [
        StatusRecord(
            id=index + 1,
            code=code,
            name=STATUS_DISPLAY.get(code, code),
            bg_color=bg_color,
            icon=ImageMapIcon(image_map_key=f"icon_{code}"),
        )
        for index, (code, bg_color) in enumerate(STATUS_BG.items())
    ]


class FakeClient:
    """Enough of an `SgClient` for the cache, the services and the pickers."""

    def __init__(self, latency: float = 0.0) -> None:
        #: Seconds each call waits before it answers.
        self.latency = latency
        #: Set once a call has reached the client, so a test knows a read is under way.
        self.entered = threading.Event()
        #: A call waits on this when it is set to an Event, so two threads can be in one read at once.
        self.gate: threading.Event | None = None
        self.rows = _rows()
        self.status_rows = _statuses()
        self._lock = threading.Lock()
        self._next_id = 90000
        self._order: dict[tuple[str, int], int] = {}
        self._clock = 0
        self._fail: SgApiError | None = None

    def fail_next(self, status: int, message: str | None = None) -> None:
        """Make the next call raise, once."""
        self._fail = SgApiError(status, None, message)

    def _gate(self) -> None:
        failure, self._fail = self._fail, None
        self.entered.set()
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if self.latency > 0:
            time.sleep(self.latency)
        if failure is not None:
            raise failure

    def _mint(self, entity_type: str) -> int:
        with self._lock:
            self._next_id += 1
            new_id = self._next_id
            self._clock += 1
            self._order[(entity_type, new_id)] = self._clock
            return new_id

    def _row(self, entity_type: str, id: int) -> EntityRow:
        for row in self.rows.get(entity_type, []):
            if row.id == id:
                return row
        raise SgApiError(404, None, f"{entity_type} {id} does not exist.")

    def entity_types(self) -> list[EntityTypeInfo]:
        self._gate()
        return [EntityTypeInfo(name=name, display_name=label) for name, label in DISPLAY_NAMES.items()]

    def fields(self, entity_type: str, project_id: int | None = None) -> dict[str, FieldSchema]:
        self._gate()
        specs = SPECS.get(entity_type)
        if specs is None:
            raise SgApiError(404, None, f"Entity type '{entity_type}' does not exist.")
        hidden = None if project_id is None else HIDDEN_VALUES.get(project_id, {})
        out: dict[str, FieldSchema] = {}
        for name, spec in specs.items():
            field = FieldSchema(
                name=name,
                display_name=spec["display_name"],
                entity_type=entity_type,
                data_type=spec["data_type"],
                editable=spec.get("editable", True),
                mandatory=spec.get("mandatory", False),
                unique=spec.get("unique", False),
                valid_types=spec.get("valid_types"),
                valid_values=spec.get("valid_values"),
                display_values=spec.get("display_values"),
                default_value=spec.get("default_value"),
            )
            # `hidden_values` appears only when the schema is read with `project_id` (009_status_lists).
            if hidden is not None and field.data_type in ("status_list", "list"):
                field.hidden_values = hidden.get(f"{entity_type}.{name}", [])
            for key, value in (field_schema_override(entity_type, name) or {}).items():
                setattr(field, key, value)
            out[name] = field
        return out

    def field_with_project(self, entity_type: str, field: str, project_id: int) -> FieldSchema:
        one = self.fields(entity_type, project_id).get(field)
        if one is None:
            raise SgApiError(404, None, f"Field '{entity_type}.{field}' does not exist.")
        return one

    def search(self, entity_type: str, options: SearchOptions) -> SearchResult:
        self._gate()
        rows = list(self.rows.get(entity_type, []))
        if options.sort:
            key = options.sort.lstrip("-")
            rows.sort(key=lambda row: str(row.values.get(key, "")), reverse=options.sort.startswith("-"))
        page = options.page or {}
        size = page.get("size", 50)
        number = page.get("number", 1)
        start = (number - 1) * size
        window = rows[start:start + size]
        wanted = options.fields
        data = [
            EntityRow(
                type=row.type,
                id=row.id,
                values=dict(row.values) if wanted is None else {k: row.values.get(k) for k in wanted},
            )
            for row in window
        ]
        return SearchResult(data=data, has_more=len(window) == size and start + size < len(rows))

    def text_search(
        self,
        text: str,
        entity_types: dict[str, TextSearchFilter],
        page: Page | None = None,
    ) -> list[TextSearchRow]:
        self._gate()
        needle = text.lower()
        out: list[TextSearchRow] = []
        for entity_type in entity_types:
            for row in self.rows.get(entity_type, []):
                name = display_name_of(row.values)
                if needle in name.lower():
                    out.append(TextSearchRow(type=row.type, id=row.id, name=name))
        return out[: (page or {}).get("size", 25)]

    def statuses(self) -> list[StatusRecord]:
        self._gate()
        return list(self.status_rows)

    def summarize(self, entity_type: str, options: SummarizeOptions | None = None) -> SummarizeResult:
        self._gate()
        return SummarizeResult(summaries={"id": float(len(self.rows.get(entity_type, [])))})

    def hierarchy_expand(self, path: str) -> HierarchyNode:
        self._gate()
        return HierarchyNode(label=path, ref=HierarchyRef(kind="empty"), path=path)

    def hierarchy_search(self, root_path: str, entity: EntityRef) -> list[HierarchyPath]:
        self._gate()
        return [
            HierarchyPath(
                label=f"{entity.type} {entity.id}",
                path_label=root_path,
                incremental_path=[root_path, f"{root_path}/{entity.type}/id/{entity.id}"],
                ref=entity,
            )
        ]

    def thread_contents(self, note_id: int, entity_fields: dict[str, list[str]] | None = None) -> list[ThreadRow]:
        self._gate()
        note = self._row("Note", note_id)
        rows = [
            ThreadRow(
                type="Note",
                id=note.id,
                created_at=note.values.get("created_at"),
                content=note.values.get("content"),
                author=_author(note.values.get("user")),
                fields=dict(note.values),
            )
        ]
        members: list[tuple[int, ThreadRow]] = []
        for row in self.rows.get("Attachment", []):
            if _links(row.values.get("attachment_links"), note_id):
                members.append((self._order.get((row.type, row.id), row.id), ThreadRow(
                    type="Attachment", id=row.id, created_at=row.values.get("created_at"),
                    author=_author(row.values.get("created_by")), fields=dict(row.values),
                )))
        for row in self.rows.get("Reply", []):
            if _links(row.values.get("entity"), note_id):
                members.append((self._order.get((row.type, row.id), row.id), ThreadRow(
                    type="Reply", id=row.id, created_at=row.values.get("created_at"),
                    content=row.values.get("content"), author=_author(row.values.get("user")),
                    fields=dict(row.values),
                )))
        rows.extend(row for _, row in sorted(members, key=lambda pair: pair[0]))
        return rows

    def event_log(self, options: EventLogOptions | None = None) -> EventLogResult:
        self._gate()
        return EventLogResult(data=[], has_more=False)

    def following(self, user_id: int, options: FollowingOptions | None = None) -> list[EntityRef]:
        self._gate()
        return [EntityRef(type="Shot", id=862)]

    def create(self, entity_type: str, body: dict[str, Any]) -> EntityRow:
        self._gate()
        row = EntityRow(type=entity_type, id=self._mint(entity_type), values=dict(body))
        self.rows.setdefault(entity_type, []).append(row)
        return EntityRow(type=row.type, id=row.id, values=dict(row.values))

    def upload(self, entity_type: str, id: int, file: UploadFile) -> UploadResult:
        self._gate()
        parent = {"type": entity_type, "id": id}
        attachment = EntityRow(
            type="Attachment",
            id=self._mint("Attachment"),
            values={"display_name": file.filename, "filename": file.filename, "attachment_links": [parent]},
        )
        self.rows.setdefault("Attachment", []).append(attachment)
        return UploadResult(upload_type="Attachment", upload_info={"filename": file.filename})

    def update(self, entity_type: str, id: int, patch: dict[str, Any]) -> EntityRow:
        self._gate()
        row = self._row(entity_type, id)
        row.values.update(patch)
        return EntityRow(type=row.type, id=row.id, values=dict(row.values))


def _author(value: Any) -> ThreadAuthor | None:
    if not isinstance(value, dict):
        return None
    return ThreadAuthor(type=value.get("type", ""), id=value.get("id", 0), name=value.get("name"))


def _links(value: Any, note_id: int) -> bool:
    entries = value if isinstance(value, list) else [value]
    return any(isinstance(e, dict) and e.get("type") == "Note" and e.get("id") == note_id for e in entries)


class CountingClient:
    """Wrap a client and record every call that actually reaches it."""

    def __init__(self, inner: SgClient) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def entity_types(self) -> list[EntityTypeInfo]:
        self.calls.append("entity_types")
        return self.inner.entity_types()

    def fields(self, entity_type: str, project_id: int | None = None) -> dict[str, FieldSchema]:
        self.calls.append(f"fields {entity_type} {project_id if project_id is not None else '-'}")
        return self.inner.fields(entity_type, project_id)

    def field_with_project(self, entity_type: str, field: str, project_id: int) -> FieldSchema:
        self.calls.append(f"field_with_project {entity_type}.{field} {project_id}")
        return self.inner.field_with_project(entity_type, field, project_id)

    def search(self, entity_type: str, options: SearchOptions) -> SearchResult:
        self.calls.append(f"search {entity_type}")
        return self.inner.search(entity_type, options)

    def text_search(
        self,
        text: str,
        entity_types: dict[str, TextSearchFilter],
        page: Page | None = None,
    ) -> list[TextSearchRow]:
        self.calls.append(f"text_search {text}")
        return self.inner.text_search(text, entity_types, page)

    def statuses(self) -> list[StatusRecord]:
        self.calls.append("statuses")
        return self.inner.statuses()

    def summarize(self, entity_type: str, options: SummarizeOptions | None = None) -> SummarizeResult:
        self.calls.append(f"summarize {entity_type}")
        return self.inner.summarize(entity_type, options)

    def hierarchy_expand(self, path: str) -> HierarchyNode:
        self.calls.append(f"hierarchy_expand {path}")
        return self.inner.hierarchy_expand(path)

    def hierarchy_search(self, root_path: str, entity: EntityRef) -> list[HierarchyPath]:
        self.calls.append(f"hierarchy_search {root_path} {entity.type}:{entity.id}")
        return self.inner.hierarchy_search(root_path, entity)

    def thread_contents(self, note_id: int, entity_fields: dict[str, list[str]] | None = None) -> list[ThreadRow]:
        self.calls.append(f"thread_contents {note_id}")
        return self.inner.thread_contents(note_id, entity_fields)

    def event_log(self, options: EventLogOptions | None = None) -> EventLogResult:
        self.calls.append("event_log")
        return self.inner.event_log(options)

    def following(self, user_id: int, options: FollowingOptions | None = None) -> list[EntityRef]:
        self.calls.append(f"following {user_id}")
        return self.inner.following(user_id, options)

    def create(self, entity_type: str, body: dict[str, Any]) -> EntityRow:
        self.calls.append(f"create {entity_type}")
        return self.inner.create(entity_type, body)

    def upload(self, entity_type: str, id: int, file: UploadFile) -> UploadResult:
        self.calls.append(f"upload {entity_type} {id}")
        return self.inner.upload(entity_type, id, file)

    def update(self, entity_type: str, id: int, patch: dict[str, Any]) -> EntityRow:
        self.calls.append(f"update {entity_type} {id}")
        return self.inner.update(entity_type, id, patch)


class FakeClock:
    """Time a test moves by hand, in seconds."""

    def __init__(self, start: float = 0.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def concurrently(client: FakeClient, call: Callable[[], Any]) -> tuple[list[Any], list[BaseException | None]]:
    """Two threads in one call: the second starts once the first is inside the client."""
    client.entered.clear()
    client.gate = threading.Event()
    values: list[Any] = [None, None]
    errors: list[BaseException | None] = [None, None]

    def work(slot: int) -> None:
        try:
            values[slot] = call()
        except BaseException as error:  # noqa: B036 - the test asserts on what was raised
            errors[slot] = error

    first = threading.Thread(target=work, args=(0,))
    first.start()
    assert client.entered.wait(5)
    second = threading.Thread(target=work, args=(1,))
    second.start()
    time.sleep(0.1)
    client.gate.set()
    first.join(5)
    second.join(5)
    client.gate = None
    return values, errors
