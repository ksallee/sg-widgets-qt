"""The `SgClient` implementation on `shotgun_api3`.

It stands where `RestClient` stands upstream: the same methods against the Python
API instead of `/api/v1`. A `shotgun_api3.Shotgun` is not thread-safe, so one is
built per thread and kept in a `threading.local`.
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import shotgun_api3

from .client import (
    EVENT_LOG_FIELDS,
    EntityRow,
    EntityTypeInfo,
    EventLogOptions,
    EventLogResult,
    FollowingOptions,
    HierarchyNode,
    HierarchyPath,
    Page,
    SearchOptions,
    SearchResult,
    SgApiError,
    SummarizeOptions,
    SummarizeResult,
    SummaryField,
    SummaryGroup,
    TextSearchRow,
    ThreadAuthor,
    ThreadRow,
    UploadFile,
    UploadResult,
    event_log_filters,
    normalize_event_log_entry,
    normalize_hierarchy_node,
)
from .filter import EntityRef, TextSearchFilter, WireGroup, to_filter_array
from .schema import FieldSchema, normalize_field, normalize_fields, undeclared_field
from .status import HtmlIcon, ImageIcon, ImageMapIcon, StatusIcon, StatusRecord

__all__ = [
    "SITE_URL_ENV",
    "SCRIPT_NAME_ENV",
    "API_KEY_ENV",
    "ShotgunClient",
    "from_api3_value",
    "to_api3_value",
    "wire_to_api3",
]

SITE_URL_ENV = "FPT_API_SITE_URL"
SCRIPT_NAME_ENV = "FPT_API_SCRIPT_NAME"
API_KEY_ENV = "FPT_API_API_KEY"

#: The shape a `date_time` value has on the wire, which is what core carries.
ISO_DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_HTTP_STATUS = re.compile(r"HTTP\D{0,16}(\d{3})\b", re.IGNORECASE)

#: The four fields whose upload `shotgun_api3` routes to the thumbnail endpoint.
_THUMBNAIL_FIELD = "image"


def from_api3_value(value: Any) -> Any:
    """A value the Python API answered, as the REST API would have sent it.

    A `datetime` becomes `YYYY-MM-DDTHH:MM:SSZ` in UTC and a `date` stays
    `YYYY-MM-DD`; everything else, entity link hashes included, is left alone.
    """
    if isinstance(value, datetime):
        # Naive only when the connection was built without `convert_datetimes_to_utc`,
        # where the API's own contract is that the value is already UTC.
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: from_api3_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [from_api3_value(v) for v in value]
    return value


def to_api3_value(value: Any) -> Any:
    """A value core holds, as the Python API takes it on a write.

    A `date_time` string becomes an aware `datetime`, which is the only type
    `_transform_outbound` converts; a `date` string is sent as it is.
    """
    if isinstance(value, str):
        if ISO_DATE_TIME.match(value):
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, dict):
        return {k: to_api3_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_api3_value(v) for v in value]
    return value


def wire_to_api3(filters: WireGroup | None) -> list[Any]:
    """The filter list `find` takes, from the wire group the editor builds.

    `find` translates a list through `_translate_filters` and passes a dict
    through untouched, so the list form is the one that carries a nested group:
    a group below the top is `{filter_operator, filters}` and a condition stays
    the three-item list it is on the wire. An `or` at the top is one nested
    group, which is the same query.
    """
    group = filters or {"logical_operator": "and", "conditions": []}
    conditions = [_wire_node_to_api3(node) for node in (group.get("conditions") or [])]
    if (group.get("logical_operator") or "and") == "and":
        return conditions
    return [{"filter_operator": "any", "filters": conditions}]


def _wire_node_to_api3(node: Any) -> Any:
    if isinstance(node, dict):
        operator = "any" if node.get("logical_operator") == "or" else "all"
        return {
            "filter_operator": operator,
            "filters": [_wire_node_to_api3(child) for child in (node.get("conditions") or [])],
        }
    return list(node)


def _order_of(sort: str | None) -> list[dict[str, str]] | None:
    """`-field` and `field` as the `order` list `find` takes."""
    if not sort:
        return None
    order: list[dict[str, str]] = []
    for part in sort.split(","):
        name = part.strip()
        if not name:
            continue
        descending = name.startswith("-")
        order.append({"field_name": name[1:] if descending else name, "direction": "desc" if descending else "asc"})
    return order or None


def _page_of(page: Page | None, default_size: int) -> tuple[int, int]:
    p = page or {}
    return int(p.get("size") or default_size), int(p.get("number") or 1)


def _entity_row(raw: Mapping[str, Any]) -> EntityRow:
    """One row of a `find`, its fields in one flat map as `EntityRow` holds them."""
    values = {k: from_api3_value(v) for k, v in raw.items() if k not in ("type", "id")}
    return EntityRow(type=str(raw.get("type") or ""), id=int(raw["id"]), values=values)


def _text_search_row(raw: Mapping[str, Any]) -> TextSearchRow:
    links = raw.get("links")
    pair = (
        (str(links[0] if links[0] is not None else ""), str(links[1] if links[1] is not None else ""))
        if isinstance(links, (list, tuple)) and len(links) >= 2
        else ("", "")
    )
    return TextSearchRow(
        type=str(raw.get("type") or ""),
        id=int(raw["id"]),
        name=str(raw.get("name") or ""),
        links=pair,
        status=raw.get("status"),
    )


def _thread_author(value: Any) -> ThreadAuthor | None:
    if not isinstance(value, dict):
        return None
    if not isinstance(value.get("type"), str) or not isinstance(value.get("id"), int):
        return None
    author = ThreadAuthor(type=value["type"], id=value["id"])
    if isinstance(value.get("name"), str):
        author.name = value["name"]
    if "image" in value:
        author.image = value["image"]
    return author


def _thread_row(raw: Mapping[str, Any]) -> ThreadRow:
    """One row of a note thread.

    The author key follows the row type: `created_by` on a Note and an
    Attachment, `user` on a Reply (get_entity_notes_id_thread_contents). A Note
    widened with `user` still names its author under `created_by`.
    """
    fields = {k: from_api3_value(v) for k, v in raw.items()}
    author = _thread_author(fields.get("user") if raw.get("type") == "Reply" else fields.get("created_by"))
    return ThreadRow(
        type=str(raw.get("type") or ""),
        id=int(raw["id"]),
        created_at=fields.get("created_at"),
        content=fields.get("content"),
        author=author,
        fields=fields,
    )


def _hierarchy_path(raw: Mapping[str, Any]) -> HierarchyPath:
    """One row of a navigation search, whose `ref` is the flat `{type, id}`."""
    ref = raw.get("ref") or {}
    return HierarchyPath(
        label=str(raw.get("label") or ""),
        path_label=str(raw.get("path_label") or ""),
        incremental_path=list(raw.get("incremental_path") or []),
        ref=EntityRef(type=str(ref.get("type") or ""), id=int(ref.get("id") or 0)),
        project_id=raw.get("project_id"),
    )


def _status_icon(raw: Mapping[str, Any]) -> StatusIcon | None:
    """The icon row rendered three ways, by `display_type` (probe 010)."""
    kind = raw.get("display_type")
    if kind == "image_map":
        return ImageMapIcon(image_map_key=str(raw.get("image_map_key") or ""))
    if kind == "image":
        # The data URL comes with embedded newlines that must be stripped; `image_data`
        # holds the same bytes and is what a narrowed projection still fills.
        url = re.sub(r"\s+", "", str(raw.get("url") or ""))
        data = re.sub(r"\s+", "", str(raw.get("image_data") or ""))
        data_url = url or (f"data:image/png;base64,{data}" if data else "")
        return ImageIcon(data_url=data_url) if data_url else None
    if kind == "html":
        return HtmlIcon(html=str(raw.get("html") or ""))
    return None


def _node_of(answer: Any) -> dict[str, Any]:
    """The node an expand answered, whether or not it is wrapped in `data`."""
    if isinstance(answer, dict):
        if "label" not in answer and isinstance(answer.get("data"), dict):
            return answer["data"]
        return dict(answer)
    return {}


def _rows_of(answer: Any) -> list[Any]:
    """The rows a call answered, whether or not they are wrapped in `data`."""
    if isinstance(answer, dict):
        rows = answer.get("data")
        return list(rows) if isinstance(rows, list) else []
    return list(answer or [])


def _summarize_result(raw: Mapping[str, Any]) -> SummarizeResult:
    body = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    groups = [
        SummaryGroup(
            group_name=str(g.get("group_name") or ""),
            group_value=from_api3_value(g.get("group_value")),
            summaries=from_api3_value(g.get("summaries") or {}),
        )
        for g in (body.get("groups") or [])
    ]
    return SummarizeResult(summaries=from_api3_value(body.get("summaries") or {}), groups=groups)


def _sg_api_error(exc: Exception) -> SgApiError:
    """A `shotgun_api3` failure as the error core catches, with the status it named."""
    status = getattr(exc, "errcode", None)
    message = str(getattr(exc, "errmsg", None) or exc)
    if status is None:
        found = _HTTP_STATUS.search(message)
        status = int(found.group(1)) if found else None
    return SgApiError(status, exc, message)


class ShotgunClient:
    """`SgClient` against a site over `shotgun_api3`."""

    def __init__(
        self,
        site_url: str,
        script_name: str | None = None,
        api_key: str | None = None,
        session_token: str | None = None,
        sudo_as_login: str | None = None,
        connect_kwargs: dict[str, Any] | None = None,
        factory: Callable[[], Any] | None = None,
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self.script_name = script_name
        self.api_key = api_key
        self.session_token = session_token
        self.sudo_as_login = sudo_as_login
        self.connect_kwargs = dict(connect_kwargs or {})
        self._factory = factory
        self._local = threading.local()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **kwargs: Any) -> ShotgunClient:
        """A client from `FPT_API_SITE_URL`, `FPT_API_SCRIPT_NAME` and `FPT_API_API_KEY`."""
        source = os.environ if env is None else env
        values: dict[str, str] = {}
        for key in (SITE_URL_ENV, SCRIPT_NAME_ENV, API_KEY_ENV):
            value = source.get(key)
            if not value:
                raise SgApiError(None, None, f"{key} is not set.")
            values[key] = value
        return cls(
            site_url=values[SITE_URL_ENV],
            script_name=values[SCRIPT_NAME_ENV],
            api_key=values[API_KEY_ENV],
            **kwargs,
        )

    @property
    def connection(self) -> Any:
        """This thread's connection, built on first use."""
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = self._connect()
            self._local.connection = connection
        return connection

    def _connect(self) -> Any:
        if self._factory is not None:
            return self._factory()
        kwargs: dict[str, Any] = {
            "base_url": self.site_url,
            # Datetimes arrive aware, which is what `from_api3_value` needs to write UTC.
            "convert_datetimes_to_utc": True,
        }
        if self.session_token is not None:
            kwargs["session_token"] = self.session_token
        else:
            kwargs["script_name"] = self.script_name
            kwargs["api_key"] = self.api_key
        if self.sudo_as_login is not None:
            kwargs["sudo_as_login"] = self.sudo_as_login
        kwargs.update(self.connect_kwargs)
        return shotgun_api3.Shotgun(**kwargs)

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return getattr(self.connection, method)(*args, **kwargs)
        except (shotgun_api3.ShotgunError, shotgun_api3.ProtocolError, shotgun_api3.ResponseError) as exc:
            raise _sg_api_error(exc) from exc

    def entity_types(self) -> list[EntityTypeInfo]:
        """Enabled entity types on the site with their display names."""
        raw = self._call("schema_entity_read") or {}
        out: list[EntityTypeInfo] = []
        for name, entry in raw.items():
            visible = (entry.get("visible") or {}).get("value", True)
            if not visible:
                continue
            out.append(EntityTypeInfo(name=name, display_name=str((entry.get("name") or {}).get("value") or name)))
        return out

    def fields(self, entity_type: str, project_id: int | None = None) -> dict[str, FieldSchema]:
        """All fields of a type. Pass `project_id` to get `hidden_values` on status and list fields."""
        raw = self._call(
            "schema_field_read",
            entity_type,
            project_entity=_project_ref(project_id),
        )
        return normalize_fields({"data": raw or {}}, entity_type)

    def field_with_project(self, entity_type: str, field: str, project_id: int) -> FieldSchema:
        """One field at project scope, 1.2KB against 48KB for the whole type (probe 002)."""
        raw = self._call(
            "schema_field_read",
            entity_type,
            field_name=field,
            project_entity=_project_ref(project_id),
        )
        one = (raw or {}).get(field)
        if one is not None:
            return normalize_field(field, one)
        # A field the site answers on the row but leaves out of its schema is absent
        # here rather than an error (068_note_read_state).
        known = undeclared_field(entity_type, field)
        if known:
            return known
        raise SgApiError(None, raw, f"Field '{entity_type}.{field}' is not in the schema.")

    def search(self, entity_type: str, options: SearchOptions) -> SearchResult:
        """Rows of one type, filtered, sorted and paged."""
        size, number = _page_of(options.page, 50)
        rows = self._call(
            "find",
            entity_type,
            wire_to_api3(options.filters),
            list(options.fields) if options.fields else None,
            order=_order_of(options.sort),
            limit=size,
            page=number,
        )
        data = [_entity_row(row) for row in rows or []]
        return SearchResult(data=data, has_more=len(data) == size)

    def text_search(
        self,
        text: str,
        entity_types: dict[str, TextSearchFilter],
        page: Page | None = None,
    ) -> list[TextSearchRow]:
        """Free-text search across several types at once.

        The call takes a row cap and no offset, so a page past the first is cut
        from a longer read. 25 is the cap and the default (probe 053).
        """
        size, number = _page_of(page, 25)
        size = min(size, 25)
        answer = self._call(
            "text_search",
            text,
            {name: to_filter_array(f) for name, f in entity_types.items()},
            limit=size * number,
        )
        rows = (answer or {}).get("matches") or []
        return [_text_search_row(row) for row in rows[(number - 1) * size:]]

    def statuses(self) -> list[StatusRecord]:
        """Status entities with colour and icon."""
        rows = self._call("find", "Status", [], ["code", "name", "bg_color", "icon"], limit=500) or []
        icon_ids = sorted({row["icon"]["id"] for row in rows if isinstance(row.get("icon"), dict)})
        icons: dict[int, dict[str, Any]] = {}
        if icon_ids:
            # `url` is empty unless `image_data` is asked for beside it (010_status_icons).
            found = self._call(
                "find",
                "Icon",
                [["id", "in", icon_ids]],
                ["display_type", "image_map_key", "url", "html", "image_data"],
                limit=500,
            )
            icons = {row["id"]: row for row in found or []}
        out: list[StatusRecord] = []
        for row in rows:
            ref = row.get("icon")
            icon = icons.get(ref["id"]) if isinstance(ref, dict) else None
            out.append(
                StatusRecord(
                    id=int(row["id"]),
                    code=str(row.get("code") or ""),
                    name=str(row.get("name") or ""),
                    bg_color=row.get("bg_color"),
                    icon=_status_icon(icon) if icon else None,
                )
            )
        return out

    def update(self, entity_type: str, id: int, patch: dict[str, Any]) -> EntityRow:
        """Change the named fields of one row and answer the whole record.

        The answer of the write carries only what was written, so the row is read
        back on the same fields (024_read_after_write).
        """
        written = self._call("update", entity_type, id, to_api3_value(dict(patch)))
        row = self._call("find_one", entity_type, [["id", "is", id]], list(patch) + ["id"])
        return _entity_row(row if row else (written or {"type": entity_type, "id": id}))

    def hierarchy_expand(self, path: str) -> HierarchyNode:
        """One level of the site's navigation tree.

        `seed_entity_field` is documented and ignored, so it is not sent
        (post_hierarchy_expand).
        """
        answer = self._call("nav_expand", path, seed_entity_field=None, entity_fields=None)
        return normalize_hierarchy_node(_node_of(answer), path)

    def hierarchy_search(self, root_path: str, entity: EntityRef) -> list[HierarchyPath]:
        """Where a row sits in the navigation tree, under `root_path` (`/Project/<id>`)."""
        answer = self._call("nav_search_entity", root_path, {"type": entity.type, "id": entity.id})
        return [_hierarchy_path(row) for row in _rows_of(answer)]

    def summarize(self, entity_type: str, options: SummarizeOptions | None = None) -> SummarizeResult:
        """Aggregate rows without paging them."""
        options = options if options is not None else SummarizeOptions()
        summary_fields = [
            {"field": f.field, "type": f.type}
            for f in (options.summary_fields or [SummaryField(field="id", type="count")])
        ]
        grouping = (
            [
                {"field": g.field, "type": g.type or "exact", "direction": g.direction or "asc"}
                for g in options.grouping
            ]
            if options.grouping
            else None
        )
        answer = self._call(
            "summarize",
            entity_type,
            wire_to_api3(options.filters),
            summary_fields,
            grouping=grouping,
        )
        return _summarize_result(answer or {})

    def create(self, entity_type: str, body: dict[str, Any]) -> EntityRow:
        """Create one row and answer it."""
        row = self._call("create", entity_type, to_api3_value(dict(body)), return_fields=list(body))
        return _entity_row(row or {"type": entity_type, "id": 0})

    def upload(self, entity_type: str, id: int, file: UploadFile) -> UploadResult:
        """Put a file on a row.

        The call takes a path, so the bytes are written to a temporary file with
        the filename's suffix and removed after. A media field is not readable
        straight after: it returns a placeholder under
        `/images/status/transient/` until the transcode lands (recipes/001).
        """
        handle = tempfile.NamedTemporaryFile(prefix="sg_upload_", suffix=Path(file.filename).suffix, delete=False)
        try:
            handle.write(file.data)
            handle.close()
            if file.field == _THUMBNAIL_FIELD:
                upload_type = "Thumbnail"
                attachment_id = self._call("upload_thumbnail", entity_type, id, handle.name)
            else:
                upload_type = "Attachment"
                # `display_name` carries the caller's filename: the path is a temporary one.
                attachment_id = self._call(
                    "upload",
                    entity_type,
                    id,
                    handle.name,
                    field_name=file.field,
                    display_name=file.filename,
                )
        finally:
            handle.close()
            if os.path.exists(handle.name):
                os.unlink(handle.name)
        return UploadResult(
            upload_type=upload_type,
            # The call answers the Attachment it made and no ticket, so there is no ETag.
            upload_info={
                "id": attachment_id,
                "upload_type": upload_type,
                "original_filename": file.filename,
            },
            etag=None,
        )

    def thread_contents(self, note_id: int, entity_fields: dict[str, list[str]] | None = None) -> list[ThreadRow]:
        """A Note, its Attachments and its Replies as one list in time order."""
        rows = self._call(
            "note_thread_read",
            note_id,
            {name: list(f) for name, f in (entity_fields or {}).items()},
        )
        return [_thread_row(row) for row in rows or []]

    def event_log(self, options: EventLogOptions | None = None) -> EventLogResult:
        """What changed, newest first."""
        options = options if options is not None else EventLogOptions()
        size, number = _page_of(options.page, 50)
        rows = self._call(
            "find",
            "EventLogEntry",
            wire_to_api3(event_log_filters(options)),
            list(EVENT_LOG_FIELDS),
            # The only order the type answers: a sort on anything else falls back to
            # ascending `id` at 200 (025_event_log).
            order=[{"field_name": "id", "direction": "desc"}],
            limit=size,
            page=number,
        )
        data = [normalize_event_log_entry(_entity_row(row)) for row in rows or []]
        return EventLogResult(data=data, has_more=len(data) == size)

    def following(self, user_id: int, options: FollowingOptions | None = None) -> list[EntityRef]:
        """Everything one person follows, in one unpaged body."""
        options = options if options is not None else FollowingOptions()
        rows = self._call(
            "following",
            {"type": "HumanUser", "id": user_id},
            project=_project_ref(options.project_id),
            entity_type=options.entity,
        )
        return [EntityRef(type=str(row["type"]), id=int(row["id"])) for row in rows or []]


def _project_ref(project_id: int | None) -> dict[str, Any] | None:
    return {"type": "Project", "id": project_id} if project_id is not None else None
