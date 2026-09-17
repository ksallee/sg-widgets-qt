"""In-memory `SgClient`.

A fake site: rows, field schemas, statuses and icons shaped exactly as
`shotgun_api3` answers them, so demos and tests exercise the same code paths as the
live client. Every quirk it reproduces is cited against the sg-groundtruth corpus;
where the mock is deliberately simpler than the site, the comment says so.

Fixtures are generated from a seed, so two runs produce identical ids, codes,
statuses and dates. The PRNG is the upstream mulberry32, ported bit for bit, so the
fixtures match the web demos.

Mutable state is guarded by one `threading.RLock`, so the Qt layer may read it from
a worker thread while another writes.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime, timedelta, timezone
from typing import Any, Union

from .client import (
    EVENT_LOG_FIELDS,
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
    plural_path,
)
from .field_types import (
    NEGATING_OPERATORS,
    TIME_UNITS,
    Operator,
    TimeUnit,
    is_filterable,
    is_link_type,
    is_numeric_type,
    operators_for,
)
from .filter import EntityRef, TextSearchFilter, WireCondition, WireGroup, to_filter_array
from .schema import FieldSchema, display_name_of, field_schema_override
from .status import HtmlIcon, ImageIcon, ImageMapIcon, StatusIcon, StatusRecord

__all__ = [
    "MOCK_NOW",
    "MockClient",
    "MockClientOptions",
    "MockCounts",
    "MockFailure",
]


# -------------------------------------------------------------------------- #
# options                                                                     #
# -------------------------------------------------------------------------- #


@dataclass
class MockFailure:
    """What the next call should raise instead of answering."""

    #: HTTP status. Default 500.
    status: int = 500
    #: `errors[0].title`, which is what the live client puts in `SgApiError`'s message.
    message: str | None = None
    #: Parsed response body, for code that inspects `SgApiError.body`.
    body: Any = None


@dataclass
class MockCounts:
    """How many rows of the scaled types to generate."""

    versions: int | None = None


#: What `now` accepts: an ISO string, epoch milliseconds, or a callable read on every call.
Clock = Union[str, int, float, Callable[[], float]]


@dataclass
class MockClientOptions:
    #: Fixture seed. The same seed always produces the same site. Default 1.
    seed: int = 1
    #: Simulated round trip, in milliseconds, applied to every call. Default 0.
    latency_ms: int = 0
    #: Arm a failure for the very first call, for demoing an error state without extra wiring.
    fail_next: MockFailure | None = None
    #: How many rows of the scaled types to generate. Default 60 Versions.
    counts: MockCounts | None = None
    #: What `in_last`, `in_next` and `in_calendar_*` resolve against. Default: the current
    #: time. Fixture dates are offsets from `MOCK_NOW`, so pin it there to filter them.
    now: Clock | None = None


# -------------------------------------------------------------------------- #
# rows                                                                        #
# -------------------------------------------------------------------------- #


@dataclass
class _Row:
    type: str
    id: int
    #: Field values by programmatic name, including `id`. Entity links are `{type, id}` dicts.
    values: dict[str, Any] = dc_field(default_factory=dict)


# -------------------------------------------------------------------------- #
# field schemas                                                               #
# -------------------------------------------------------------------------- #


@dataclass
class _FieldSpec:
    display_name: str
    data_type: str
    editable: bool = True
    #: Flagged `editable: false` and still taken by a create: `created_at` and `updated_at`
    #: are stored as sent on a create and 400 on an update with `is editable on create
    #: only` (070_authored_timestamps), as `this_file` does (entity_types/Attachment).
    create_only: bool = False
    mandatory: bool = False
    unique: bool = False
    valid_types: list[str] | None = None
    valid_values: list[str] | None = None
    display_values: dict[str, str] | None = None
    default_value: Any = None
    description: str | None = None


# Status vocabularies. `valid_values` is the site's whole vocabulary and is
# byte-identical at every scope; only `hidden_values` varies per project
# (009_status_lists). Version's list is the one the probed site answered.
VERSION_STATUSES = [
    "na", "rev", "vwd", "apr", "custom", "fin", "ip", "clsd",
    "cmpt", "cfrm", "pndad", "pndl", "pndvs", "part", "pass", "pndng",
]
#: Task's list, also verbatim from 009_status_lists: it overlaps Version on five codes only.
TASK_STATUSES = ["wtg", "ip", "fin", "apr", "dis", "na", "hld", "rev", "omt", "ready"]
SHOT_STATUSES = ["wtg", "ip", "rev", "apr", "fin", "hld", "omt"]
#: Sequence's list, verbatim from entity_types/Sequence.
SEQUENCE_STATUSES = ["wtg", "ip", "fin"]
#: entity_types/HumanUser: two codes, `act` the default, and `act` is a condition on impersonation.
USER_STATUSES = ["act", "dis"]
#: A Note is created `opn`; the open set is what the `open_notes_count` rollups count (entity_types/Note).
NOTE_STATUSES = ["opn", "clsd"]
#: Attachment's own list on the probed site, `na` the default (entity_types/Attachment).
ATTACHMENT_STATUSES = ["fin", "na"]
NOTE_TYPES = ["Client", "Internal", "Direction"]

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

#: A 1x1 png, standing in for the one `display_type: image` icon the probed site had.
TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

ASSET_TYPES = ["Character", "Environment", "Prop", "Vehicle", "FX", "Matte Painting"]
SHOT_TYPES = ["VFX", "2D", "Full CG", "Trailer", "Marketing", "Look Dev"]
VERSION_TYPES = ["Type A", "Type B", "Type C"]
#: Decimal `r,g,b`, the only form a colour field stores (field_types/color).
BAR_COLORS = ["253,94,99", "110,180,200", "240,190,90", "90,200,160"]
#: Project's own status field is a plain `list` with no Status row behind it (entity_types/Project).
PROJECT_STATUSES = ["Active", "Bidding", "Complete", "On Hold"]


def _audit() -> dict[str, _FieldSpec]:
    return {
        "id": _FieldSpec("Id", "number", editable=False),
        "cached_display_name": _FieldSpec("Display Name", "text"),
        "created_at": _FieldSpec("Date Created", "date_time", editable=False, create_only=True),
        "updated_at": _FieldSpec("Date Updated", "date_time", editable=False, create_only=True),
        "created_by": _FieldSpec("Created by", "entity", editable=False, valid_types=["HumanUser", "ApiUser"]),
        "updated_by": _FieldSpec("Updated by", "entity", editable=False, valid_types=["HumanUser", "ApiUser"]),
    }


def _status_spec(valid_values: list[str], default_value: str, mandatory: bool = False) -> _FieldSpec:
    return _FieldSpec(
        display_name="Status",
        data_type="status_list",
        valid_values=valid_values,
        display_values={c: STATUS_DISPLAY.get(c, c) for c in valid_values},
        default_value=default_value,
        mandatory=mandatory,
    )


def _spec(*pairs: tuple[str, _FieldSpec], audit: bool = True) -> dict[str, _FieldSpec]:
    out = _audit() if audit else {}
    for name, field in pairs:
        out[name] = field
    return out


SPECS: dict[str, dict[str, _FieldSpec]] = {
    # Project is site-wide: it has no `project` field, so `project.Project.id` 400s on it.
    "Project": _spec(
        ("name", _FieldSpec("Project Name", "text", mandatory=True, unique=True)),
        ("code", _FieldSpec("Project Code", "text", unique=True)),
        ("tank_name", _FieldSpec("Tank Name", "text")),
        # Project's status field is `sg_status`, a `list`: no Status row, no icon, no bg_color.
        ("sg_status", _FieldSpec("Status", "list", valid_values=PROJECT_STATUSES, default_value="Active")),
        ("sg_type", _FieldSpec("Type", "list", valid_values=["Feature", "Episodic", "Commercial", "Short"])),
        ("sg_description", _FieldSpec("Description", "text")),
        ("sg_start_date", _FieldSpec("Start Date", "date")),
        ("sg_end_date", _FieldSpec("End Date", "date")),
        ("sg_frame_rate", _FieldSpec("Frame Rate", "float")),
        ("sg_progress", _FieldSpec("Progress", "percent")),
        ("archived", _FieldSpec("Archived", "checkbox")),
        ("is_demo", _FieldSpec("Is Demo", "checkbox", editable=False)),
        ("is_template", _FieldSpec("Is Template", "checkbox", editable=False)),
        ("image", _FieldSpec("Thumbnail", "image")),
        ("landing_page_url", _FieldSpec("Landing Page URL", "text", editable=False)),
        ("users", _FieldSpec("Users", "multi_entity", valid_types=["HumanUser"])),
    ),
    "Sequence": _spec(
        ("code", _FieldSpec("Sequence Name", "text", mandatory=True)),
        ("description", _FieldSpec("Description", "text")),
        ("sg_status_list", _status_spec(SEQUENCE_STATUSES, "ip")),
        ("sg_timecode", _FieldSpec("Timecode", "timecode")),
        ("sg_cut_duration", _FieldSpec("Cut Duration", "number")),
        ("image", _FieldSpec("Thumbnail", "image")),
        ("project", _FieldSpec("Project", "entity", mandatory=True, valid_types=["Project"])),
        ("shots", _FieldSpec("Shots", "multi_entity", valid_types=["Shot"])),
    ),
    "Shot": _spec(
        ("code", _FieldSpec("Shot Code", "text", mandatory=True)),
        ("description", _FieldSpec("Description", "text")),
        ("sg_status_list", _status_spec(SHOT_STATUSES, "wtg")),
        ("sg_shot_type", _FieldSpec("Shot Type", "list", valid_values=SHOT_TYPES)),
        ("sg_cut_in", _FieldSpec("Cut In", "number")),
        ("sg_cut_out", _FieldSpec("Cut Out", "number")),
        ("sg_cut_duration", _FieldSpec("Cut Duration", "number")),
        ("sg_working_duration", _FieldSpec("Working Duration", "duration")),
        ("sg_turnover_date", _FieldSpec("Turnover Date", "date")),
        ("sg_complexity", _FieldSpec("Complexity", "percent")),
        ("sg_lens", _FieldSpec("Lens (mm)", "float")),
        ("sg_omit", _FieldSpec("Omitted", "checkbox")),
        ("image", _FieldSpec("Thumbnail", "image")),
        ("sg_shot_notes_url", _FieldSpec("Notes URL", "url")),
        ("project", _FieldSpec("Project", "entity", mandatory=True, valid_types=["Project"])),
        ("sg_sequence", _FieldSpec("Sequence", "entity", valid_types=["Sequence"])),
        ("assets", _FieldSpec("Assets", "multi_entity", valid_types=["Asset"])),
        ("tasks", _FieldSpec("Tasks", "multi_entity", valid_types=["Task"])),
    ),
    "Asset": _spec(
        ("code", _FieldSpec("Asset Name", "text", mandatory=True)),
        ("description", _FieldSpec("Description", "text")),
        ("sg_status_list", _status_spec(SHOT_STATUSES, "wtg")),
        ("sg_asset_type", _FieldSpec("Asset Type", "list", valid_values=ASSET_TYPES)),
        ("sg_build_days", _FieldSpec("Build Days", "number")),
        ("sg_complexity", _FieldSpec("Complexity", "percent")),
        ("sg_due_date", _FieldSpec("Due Date", "date")),
        ("sg_published", _FieldSpec("Published", "checkbox")),
        ("image", _FieldSpec("Thumbnail", "image")),
        ("project", _FieldSpec("Project", "entity", mandatory=True, valid_types=["Project"])),
        ("shots", _FieldSpec("Shots", "multi_entity", valid_types=["Shot"])),
        ("sequences", _FieldSpec("Sequences", "multi_entity", valid_types=["Sequence"])),
        ("tasks", _FieldSpec("Tasks", "multi_entity", valid_types=["Task"])),
    ),
    "Version": _spec(
        ("code", _FieldSpec("Version Name", "text", mandatory=True)),
        ("description", _FieldSpec("Description", "text")),
        # The field field_types/text was probed on, and null on 100 of 100 rows there. Half the
        # fixtures leave it null so a caller can exercise "negation includes nulls".
        ("sg_department", _FieldSpec("Department", "text")),
        ("sg_status_list", _status_spec(VERSION_STATUSES, "rev")),
        ("sg_version_type", _FieldSpec("Version Type", "list", valid_values=VERSION_TYPES, default_value="Type A")),
        ("sg_first_frame", _FieldSpec("First Frame", "number")),
        ("sg_last_frame", _FieldSpec("Last Frame", "number")),
        ("frame_count", _FieldSpec("Frame Count", "number")),
        ("sg_uploaded_movie_frame_rate", _FieldSpec("Movie Frame Rate", "float")),
        ("sg_uploaded_movie_transcoding_status", _FieldSpec("Transcoding Status", "number")),
        ("sg_path_to_frames", _FieldSpec("Path to Frames", "text")),
        ("sg_path_to_movie", _FieldSpec("Path to Movie", "text")),
        ("client_approved", _FieldSpec("Client Approved", "checkbox")),
        ("client_approved_at", _FieldSpec("Client Approved at", "date_time")),
        ("image", _FieldSpec("Thumbnail", "image")),
        ("sg_uploaded_movie", _FieldSpec("Uploaded Movie", "url")),
        # A colour is the decimal `r,g,b` the field stores, never hex (field_types/color).
        ("sg_bar_color", _FieldSpec("Bar Colour", "color")),
        ("project", _FieldSpec("Project", "entity", mandatory=True, valid_types=["Project"])),
        # The probed site links 99% of Versions through `entity` to a Shot and 1% to an Asset (005_link_usage).
        ("entity", _FieldSpec("Link", "entity", valid_types=["Shot", "Asset", "Sequence"])),
        ("sg_task", _FieldSpec("Task", "entity", valid_types=["Task"])),
        ("user", _FieldSpec("Artist", "entity", valid_types=["HumanUser", "ApiUser"])),
        ("playlists", _FieldSpec("Playlists", "multi_entity", valid_types=["Playlist"])),
    ),
    "Task": _spec(
        # Task's identity field is `content`. It has no `code` and no `name`: both 400 in a filter.
        ("content", _FieldSpec("Task Name", "text", mandatory=True)),
        ("sg_description", _FieldSpec("Description", "text")),
        ("sg_status_list", _status_spec(TASK_STATUSES, "wtg")),
        ("start_date", _FieldSpec("Start Date", "date")),
        ("due_date", _FieldSpec("Due Date", "date")),
        # A duration is a bare integer of minutes; the working day is `hours_per_day` from /preferences.
        ("duration", _FieldSpec("Duration", "duration")),
        ("est_in_mins", _FieldSpec("Bid", "duration")),
        ("time_logs_sum", _FieldSpec("Time Logged", "duration", editable=False)),
        ("time_percent_of_est", _FieldSpec("Time Percent of Bid", "percent", editable=False)),
        # Task.color holds the token `pipeline_step`, not a colour: read `step.Step.color` (field_types/color).
        ("color", _FieldSpec("Task Color", "color")),
        ("milestone", _FieldSpec("Milestone", "checkbox")),
        ("project", _FieldSpec("Project", "entity", mandatory=True, valid_types=["Project"])),
        ("entity", _FieldSpec("Link", "entity", valid_types=["Shot", "Asset", "Sequence"])),
        ("step", _FieldSpec("Pipeline Step", "entity", valid_types=["Step"])),
        ("task_assignees", _FieldSpec("Assigned To", "multi_entity", valid_types=["Group", "HumanUser"])),
        ("task_reviewers", _FieldSpec("Reviewers", "multi_entity", valid_types=["Group", "HumanUser"])),
        ("upstream_tasks", _FieldSpec("Upstream Tasks", "multi_entity", valid_types=["Task"])),
    ),
    "Note": _spec(
        # `subject` is the title and `content` the body, and `cached_display_name` is
        # `"<subject> - <content>"` when both are set (entity_types/Note).
        ("subject", _FieldSpec("Subject", "text", mandatory=True)),
        ("content", _FieldSpec("Body", "text")),
        # A site is free to flag a status field mandatory, and Note's commonly is. The probed
        # site's Version status reads `mandatory: false` (probe 009); the flag is per site and
        # per field, so a widget reads it rather than assuming either way.
        ("sg_status_list", _status_spec(NOTE_STATUSES, "opn", True)),
        ("sg_note_type", _FieldSpec("Note Type", "list", valid_values=NOTE_TYPES)),
        # The codes `unread` and `read`, never a boolean (067_notes_in_the_stream).
        ("read_by_current_user", _FieldSpec("Read by Current User", "list", valid_values=["unread", "read"])),
        ("publish_status", _FieldSpec("Publish Status", "text")),
        ("project", _FieldSpec("Project", "entity", valid_types=["Project"])),
        ("user", _FieldSpec("Author", "entity", valid_types=["HumanUser", "ApiUser"])),
        # Site configuration on a real site, 36 types on the probed one, and not enforced.
        ("note_links", _FieldSpec(
            "Link", "multi_entity", valid_types=["Shot", "Asset", "Sequence", "Version", "Playlist"],
        )),
        # A Note about a Task goes here: `Task` is absent from `note_links` (entity_types/Note).
        ("tasks", _FieldSpec("Tasks", "multi_entity", valid_types=["Task"])),
        ("replies", _FieldSpec("Replies", "multi_entity", valid_types=["Reply"])),
        ("attachments", _FieldSpec("Attachments", "multi_entity", valid_types=["Attachment"])),
        ("addressings_to", _FieldSpec("To", "multi_entity", valid_types=["Group", "HumanUser"])),
        ("addressings_cc", _FieldSpec("Cc", "multi_entity", valid_types=["Group", "HumanUser"])),
    ),
    # Site-wide: seven fields and no `project`, so a filter on one is 400
    # `API read() Reply.project doesn't exist.` (entity_types/Reply). `updated_at` is
    # not among the seven: a create naming it is 400 `doesn't exist` (070_authored_timestamps).
    "Reply": _spec(
        ("id", _audit()["id"]),
        ("cached_display_name", _audit()["cached_display_name"]),
        ("created_at", _audit()["created_at"]),
        ("content", _FieldSpec("Reply Text", "text", mandatory=True)),
        # Nearly every type on the site, which makes it a generic link and not a Note link.
        ("entity", _FieldSpec("Link", "entity", valid_types=["Note", "Version", "Shot", "Asset", "Task"])),
        ("user", _FieldSpec("Author", "entity", valid_types=["HumanUser", "ApiUser", "ClientUser"])),
        ("publish_status", _FieldSpec("Publish Status", "text")),
        audit=False,
    ),
    "Attachment": _spec(
        # There is no `name` field on the type; `display_name` is what a person reads.
        ("display_name", _FieldSpec("File Display Name", "text")),
        ("description", _FieldSpec("Description", "text")),
        ("original_fname", _FieldSpec("Original Filename", "text")),
        # The three read-only ones are refused on create and on update alike (entity_types/Attachment).
        ("filename", _FieldSpec("File Name", "text", editable=False)),
        ("file_extension", _FieldSpec("File Type", "text", editable=False)),
        ("file_size", _FieldSpec("File Size", "number", editable=False)),
        # A `{url, name}` hash on the create is the one body that makes a usable row; a
        # second write is `is editable on create only` (entity_types/Attachment).
        ("this_file", _FieldSpec("Link", "url", editable=False, create_only=True)),
        ("processing_status", _FieldSpec(
            "Processing Status", "list", editable=False,
            valid_values=["thumbnail_pending", "unverified", "clean", "infected"],
        )),
        ("sg_status_list", _status_spec(ATTACHMENT_STATUSES, "na")),
        ("project", _FieldSpec("Project", "entity", valid_types=["Project"])),
        ("attachment_links", _FieldSpec(
            "Attachment Links", "multi_entity",
            valid_types=["Note", "Version", "Shot", "Asset", "Sequence", "Delivery"],
        )),
    ),
    # Every field is server-written, `meta` says what changed, and `audit_trail` is
    # never returned even when it is named (025_event_log).
    "EventLogEntry": _spec(
        ("id", _audit()["id"]),
        ("cached_display_name", _audit()["cached_display_name"]),
        ("created_at", _audit()["created_at"]),
        ("event_type", _FieldSpec("Event Type", "text", editable=False)),
        ("attribute_name", _FieldSpec("Attribute Name", "text", editable=False)),
        ("description", _FieldSpec("Description", "text", editable=False)),
        # `serializable`: readable, and 400 `cannot be used in a filter` on every operator.
        ("meta", _FieldSpec("Meta", "serializable", editable=False)),
        ("session_uuid", _FieldSpec("Session UUID", "uuid", editable=False)),
        ("entity", _FieldSpec(
            "Entity", "entity", editable=False,
            valid_types=["Shot", "Asset", "Sequence", "Version", "Task", "Note", "Reply", "Project"],
        )),
        ("project", _FieldSpec("Project", "entity", editable=False, valid_types=["Project"])),
        ("user", _FieldSpec("User", "entity", editable=False, valid_types=["HumanUser", "ApiUser"])),
        audit=False,
    ),
    "HumanUser": _spec(
        # `login` is the only unique field on the type, and it is what `sudo_as_login` matches.
        ("login", _FieldSpec("Login", "text", unique=True)),
        ("name", _FieldSpec("Name", "text", mandatory=True)),
        ("firstname", _FieldSpec("First Name", "text")),
        ("lastname", _FieldSpec("Last Name", "text")),
        ("email", _FieldSpec("Email", "text")),
        ("sg_status_list", _status_spec(USER_STATUSES, "act")),
        # The HumanUser card does not enumerate `image`; the shape is field_types/image, a presigned URL.
        ("image", _FieldSpec("Thumbnail", "image")),
        ("password_proxy", _FieldSpec("Password", "password", editable=False)),
        ("can_impersonate_this_user", _FieldSpec("Can Impersonate", "checkbox", editable=False)),
        ("sg_department_name", _FieldSpec("Department Name", "text")),
        ("projects", _FieldSpec("Projects", "multi_entity", valid_types=["Project"])),
        ("groups", _FieldSpec("Groups", "multi_entity", valid_types=["Group"])),
        ("permission_rule_set", _FieldSpec(
            "Permission Rule Set", "entity", editable=False, valid_types=["PermissionRuleSet"],
        )),
    ),
    # Lean schemas: enough for `search` and a picker, not a full transcription of the type.
    "ApiUser": _spec(
        ("firstname", _FieldSpec("Script Name", "text")),
        ("email", _FieldSpec("Email", "text")),
        ("description", _FieldSpec("Description", "text")),
        # 049_script_events: a script's writes reach the event log only while this is true,
        # and it defaults to false.
        ("generate_event_log_entries", _FieldSpec("Generate Events", "checkbox")),
        ("projects", _FieldSpec("Projects", "multi_entity", valid_types=["Project"])),
    ),
    "Step": _spec(
        ("code", _FieldSpec("Step Name", "text", mandatory=True)),
        ("short_name", _FieldSpec("Short Name", "text", mandatory=True)),
        # `entity_type` is a bare schema name (`Shot`), never the URL slug, and is case-sensitive on filter.
        ("entity_type", _FieldSpec("Entity Type", "entity_type", editable=False)),
        ("list_order", _FieldSpec("Sort Order", "number")),
        ("color", _FieldSpec("Color", "color")),
    ),
    "Status": _spec(
        ("code", _FieldSpec("Status Code", "text", unique=True)),
        ("name", _FieldSpec("Status Name", "text")),
        ("bg_color", _FieldSpec("Background Colour", "color")),
        ("icon", _FieldSpec("Icon", "entity", valid_types=["Icon"])),
    ),
    "Icon": _spec(
        ("name", _FieldSpec("Icon Name", "text")),
        ("display_type", _FieldSpec("Display Type", "list", valid_values=["image_map", "image", "html"])),
        ("icon_type", _FieldSpec("Icon Type", "list", valid_values=["permanent_status", "custom_status"])),
        ("image_map_key", _FieldSpec("Image Map Key", "text")),
        ("url", _FieldSpec("URL", "text")),
        ("image_data", _FieldSpec("Image Data", "text")),
        ("html", _FieldSpec("HTML", "text")),
    ),
}

#: The identity field per type. It is flagged `mandatory` and is optional on a create;
#: the server fills it with `New <display name> <id>` on the types below, and a Note is
#: left titleless (012_create_version, entity_types/Note).
IDENTITY_FIELD: dict[str, str] = {
    "Project": "name", "Sequence": "code", "Shot": "code", "Asset": "code", "Version": "code",
    "Task": "content", "Note": "subject", "Reply": "content", "Attachment": "display_name",
}

GENERATED_IDENTITY = frozenset(("Sequence", "Shot", "Asset", "Version", "Task"))

DISPLAY_NAMES: dict[str, str] = {
    "Project": "Project", "Sequence": "Sequence", "Shot": "Shot", "Asset": "Asset", "Version": "Version",
    "Task": "Task", "HumanUser": "Person", "ApiUser": "Script", "Step": "Pipeline Step",
    "Status": "Status", "Icon": "Icon", "Note": "Note", "Reply": "Reply", "Attachment": "Attachment",
    "EventLogEntry": "Event Log Entry",
}

#: Which codes each project hides, per type. `hidden_values` is the only thing
#: `project_id` changes (009_status_lists), and it is not a subset of `valid_values`:
#: the probed site hid `blk` and `rdy`, neither of them valid.
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


# -------------------------------------------------------------------------- #
# fixtures                                                                    #
# -------------------------------------------------------------------------- #

_U32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """`Math.imul`: the low 32 bits of a 32-bit multiply."""
    return (a * b) & _U32


def _mulberry32(seed: int) -> Callable[[], float]:
    """mulberry32: a small, fast, seedable PRNG so a seed reproduces a whole site.

    Ported bit for bit from the upstream generator, so the ids, names and statuses come
    out identical to the web demos.
    """
    state = seed & _U32

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & _U32
        t = _imul(state ^ (state >> 15), 1 | state)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & _U32) ^ t
        return ((t ^ (t >> 14)) & _U32) / 4294967296

    return rng


_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

#: The mock site's today. Every fixture date is an offset in days from it.
EPOCH_MS = int((datetime(2026, 1, 5, tzinfo=timezone.utc) - _UNIX_EPOCH).total_seconds() * 1000)

HOUR_MS = 3_600_000
DAY_MS = 86_400_000


def _at(ms: float) -> datetime:
    return _UNIX_EPOCH + timedelta(milliseconds=ms)


def _utc_ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, ms: int = 0) -> int:
    """`Date.UTC` with the month and day overflow it allows."""
    year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    base = datetime(year, month, 1, tzinfo=timezone.utc)
    delta = timedelta(days=day - 1, hours=hour, minutes=minute, seconds=second, milliseconds=ms)
    return int((base + delta - _UNIX_EPOCH).total_seconds() * 1000)


#: Midday on the mock site's today, for a caller pinning `now` so relative-date filters
#: land on the fixtures.
MOCK_NOW = _at(EPOCH_MS + 12 * HOUR_MS).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _iso_date(day_offset: int) -> str:
    return _at(EPOCH_MS + day_offset * DAY_MS).strftime("%Y-%m-%d")


def _iso_date_time(day_offset: int, seconds: int = 0) -> str:
    """`YYYY-MM-DDTHH:MM:SSZ`: second resolution, literal Z, never an offset (field_types/date_time)."""
    return _at(EPOCH_MS + day_offset * DAY_MS + seconds * 1000).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _thumb(slug: str, w: int = 96, h: int = 54) -> str:
    return f"https://picsum.photos/seed/{slug}/{w}/{h}"


#: The web root of the mock site, which is where a transcoding placeholder lives.
MOCK_SITE_URL = "https://mock.example.studio"

_UNRESERVED = "".join(chr(c) for c in range(128) if chr(c).isalnum()) + "-_.!~*'()"


def _portrait(login: str) -> str:
    """Illustrated portraits from DiceBear's CC0 "lorelei" set, one per login, so no real face appears."""
    from urllib.parse import quote

    seed = quote(login, safe=_UNRESERVED)
    return (
        f"https://api.dicebear.com/9.x/lorelei/svg?seed={seed}"
        "&backgroundType=gradientLinear&backgroundColor=d1d4f9,c0aede,ffdfbf,b6e3f4"
    )


def _ref(row: _Row) -> dict[str, Any]:
    return {"type": row.type, "id": row.id}


@dataclass
class _Fixtures:
    rows: dict[str, list[_Row]] = dc_field(default_factory=dict)
    #: Every row by `Type:id`, for resolving a link's display name and a dotted path.
    index: dict[str, _Row] = dc_field(default_factory=dict)
    #: What each HumanUser follows, by user id. A follow is a link and carries no date.
    follows: dict[int, list[dict[str, Any]]] = dc_field(default_factory=dict)


STEP_SEEDS = [
    {"code": "Layout", "short_name": "layout", "entity_type": "Shot", "color": "110,180,200"},
    {"code": "Animation", "short_name": "ANM", "entity_type": "Shot", "color": "253,94,99"},
    {"code": "Character FX", "short_name": "CFX", "entity_type": "Shot", "color": "190,120,220"},
    {"code": "Lighting", "short_name": "LGT", "entity_type": "Shot", "color": "240,190,90"},
    {"code": "FX", "short_name": "FX", "entity_type": "Shot", "color": "90,200,160"},
    {"code": "Comp", "short_name": "CMP", "entity_type": "Shot", "color": "70,140,230"},
    {"code": "Model", "short_name": "MDL", "entity_type": "Asset", "color": "200,140,90"},
    {"code": "Rig", "short_name": "RIG", "entity_type": "Asset", "color": "150,150,220"},
    {"code": "Texture", "short_name": "TXT", "entity_type": "Asset", "color": "220,150,110"},
]

USER_SEEDS = [
    {"first": "Ada", "last": "Lovelace", "dept": "Animation", "status": "act"},
    {"first": "Bo", "last": "Chen", "dept": "Lighting", "status": "dis"},
    {"first": "Cleo", "last": "Dias", "dept": "Comp", "status": "act"},
    {"first": "Dmitri", "last": "Ivanov", "dept": "FX", "status": "act"},
    {"first": "Eve", "last": "Kim", "dept": "Layout", "status": "dis"},
    {"first": "Farid", "last": "Nasser", "dept": "Modelling", "status": "act"},
    {"first": "Grace", "last": "Ono", "dept": "Rigging", "status": "act"},
    {"first": "Hiro", "last": "Tanaka", "dept": "Production", "status": "act"},
]

#: The threads. `day` and the minute offsets place every row of a thread on one
#: timeline, so the Note, its Attachments and its Replies interleave in time order the
#: way `thread_contents` returns them.
NOTE_SEEDS: list[dict[str, Any]] = [
    {
        "subject": "Key light reads flat",
        "content": "The key reads flat against the plate. Warmer, and a stop down.",
        "day": -6,
        "author": 0,
        "status": "opn",
        "read": "unread",
        "note_type": "Internal",
        "attachments": [
            {"filename": "key_light_ref.png", "minutes": 2},
            {"filename": "plate_compare.png", "minutes": 60},
        ],
        "replies": [
            {"author": 2, "minutes": 45, "content": "Warmed it by 300K and dropped the key."},
            {"author": 0, "minutes": 90, "content": "Better. Leave the rim where it is."},
        ],
    },
    {
        "subject": "Comp edges on the rotoscope",
        "content": "The left edge tears on frame 1042.",
        "day": -4,
        "author": 2,
        "status": "opn",
        "read": "unread",
        "note_type": "Client",
        "attachments": [{"filename": "frame_1042.png", "minutes": 5}],
        "replies": [{"author": 5, "minutes": 200, "content": "Repainted the edge and pushed a new version."}],
    },
    {
        "subject": "Approved for the reel",
        "content": "Nothing else from me.",
        "day": -3,
        "author": 7,
        "status": "clsd",
        "read": "read",
        "note_type": "Internal",
        "attachments": [],
        "replies": [],
    },
    {
        "subject": "Dust pass is too heavy",
        "content": "Half the density and keep the drift.",
        "day": -2,
        "author": 3,
        "status": "opn",
        "read": "read",
        "note_type": "Direction",
        "attachments": [],
        "replies": [
            {"author": 5, "minutes": 30, "content": "Halved it."},
            {"author": 3, "minutes": 120, "content": "That reads."},
        ],
    },
]

ASSET_SEEDS = [
    {"code": "charAda", "type": "Character", "project": 0},
    {"code": "charBruno", "type": "Character", "project": 0},
    {"code": "propLantern", "type": "Prop", "project": 0},
    {"code": "propCrate", "type": "Prop", "project": 0},
    {"code": "envForest", "type": "Environment", "project": 0},
    {"code": "envStation", "type": "Environment", "project": 0},
    {"code": "vehRover", "type": "Vehicle", "project": 0},
    {"code": "charLuna", "type": "Character", "project": 1},
    {"code": "envHarbour", "type": "Environment", "project": 1},
    {"code": "fxDust", "type": "FX", "project": 1},
]


def _pick(rng: Callable[[], float], items: Sequence[Any]) -> Any:
    return items[int(rng() * len(items))]


def _js_round(value: float) -> int:
    """`Math.round`: halves go up, never to even."""
    return math.floor(value + 0.5)


def _build_fixtures(seed: int, counts: MockCounts | None = None) -> _Fixtures:
    counts = counts or MockCounts()
    rng = _mulberry32(seed)
    fixtures = _Fixtures()

    def add(entity_type: str, id: int, values: dict[str, Any]) -> _Row:
        row = _Row(type=entity_type, id=id, values={**values, "id": id})
        fixtures.rows.setdefault(entity_type, []).append(row)
        fixtures.index[f"{entity_type}:{id}"] = row
        return row

    # people ---------------------------------------------------------------- #
    users: list[_Row] = []
    for i, u in enumerate(USER_SEEDS):
        login = f"{u['first'].lower()}.{u['last'].lower()}"
        name = f"{u['first']} {u['last']}"
        users.append(add("HumanUser", 20 + i, {
            "login": login,
            "name": name,
            "cached_display_name": name,
            "firstname": u["first"],
            "lastname": u["last"],
            "email": f"{login}@example.studio",
            "sg_status_list": u["status"],
            "image": _portrait(login),
            "password_proxy": "*******",
            "can_impersonate_this_user": True,
            "sg_department_name": u["dept"],
            "projects": [],
            "groups": [],
            "permission_rule_set": {"type": "PermissionRuleSet", "id": 8},
            "created_at": _iso_date_time(-200 + i),
            "updated_at": _iso_date_time(-10 + i),
            "created_by": None,
            "updated_by": None,
        }))
    active_users = [u for u in users if u.values["sg_status_list"] == "act"]

    api_users: list[_Row] = []
    for i, n in enumerate(["sg_widgets_demo", "pipeline_bot"]):
        api_users.append(add("ApiUser", 90 + i, {
            "firstname": n,
            "cached_display_name": n,
            "email": f"{n}@example.studio",
            "description": "Widget demos" if i == 0 else "Nightly publishes",
            # Defaults to false on a real site, and nothing errors when it is off (049_script_events).
            "generate_event_log_entries": i == 0,
            "projects": [],
            "created_at": _iso_date_time(-300 + i),
            "updated_at": _iso_date_time(-300 + i),
            "created_by": None,
            "updated_by": None,
        }))
    bot = api_users[0]

    steps = [
        add("Step", 1 + i, {
            "code": s["code"],
            "short_name": s["short_name"],
            # null on every Step on the probed site; display `code` instead.
            "cached_display_name": None,
            "entity_type": s["entity_type"],
            "list_order": i + 1,
            "color": s["color"],
            "created_at": _iso_date_time(-400),
            "updated_at": _iso_date_time(-400),
            "created_by": None,
            "updated_by": None,
        })
        for i, s in enumerate(STEP_SEEDS)
    ]

    # statuses and icons ----------------------------------------------------- #
    all_codes: list[str] = []
    for code in (
        *VERSION_STATUSES, *TASK_STATUSES, *SHOT_STATUSES, *SEQUENCE_STATUSES,
        *USER_STATUSES, *NOTE_STATUSES, *ATTACHMENT_STATUSES,
    ):
        if code not in all_codes:
            all_codes.append(code)
    for i, code in enumerate(all_codes):
        icon_id = 400 + i
        # Three renderings, exactly as 010_status_icons groups them: 94 image_map, 1 image, 3 html.
        if code == "custom":
            icon_values: dict[str, Any] = {
                "name": "CustomIcon", "display_type": "image", "icon_type": "custom_status",
                "image_map_key": None, "url": TINY_PNG_DATA_URL,
                "image_data": TINY_PNG_DATA_URL.split(",")[1], "html": None,
            }
        elif code == "act":
            icon_values = {
                "name": "ActiveBadge", "display_type": "html", "icon_type": "custom_status",
                "image_map_key": None, "url": "", "image_data": None, "html": "Active",
            }
        else:
            icon_values = {
                "name": f"icon_{code}", "display_type": "image_map", "icon_type": "permanent_status",
                "image_map_key": f"icon_{code}", "url": "", "image_data": None, "html": None,
            }
        icon = add("Icon", icon_id, {
            **icon_values,
            "cached_display_name": icon_values["name"],
            "created_at": _iso_date_time(-500),
            "updated_at": _iso_date_time(-500),
            "created_by": None,
            "updated_by": None,
        })
        name = STATUS_DISPLAY.get(code, code)
        add("Status", 300 + i, {
            "code": code,
            "name": name,
            "cached_display_name": name,
            "bg_color": STATUS_BG.get(code, "150,150,150"),
            "icon": _ref(icon),
            "created_at": _iso_date_time(-500),
            "updated_at": _iso_date_time(-500),
            "created_by": None,
            "updated_by": None,
        })

    # projects --------------------------------------------------------------- #
    project_seeds = [
        {"id": 70, "name": "Blue Moon Rising", "code": "bmr", "status": "Active", "type": "Feature"},
        {"id": 71, "name": "Harbour Lights", "code": "hbl", "status": "Bidding", "type": "Episodic"},
        # A project whose Shots are grouped by a field no row of it fills, which the
        # navigation tree answers as an empty level (064_hierarchy_expand_buckets).
        {"id": 72, "name": "Night Ferry", "code": "nfr", "status": "Active", "type": "Short"},
    ]
    projects = [
        add("Project", p["id"], {
            "name": p["name"],
            "code": p["code"],
            "cached_display_name": p["name"],
            "tank_name": p["code"],
            "sg_status": p["status"],
            "sg_type": p["type"],
            "sg_description": f"{p['name']}, the {p['type'].lower()}.",
            "sg_start_date": _iso_date(-120 + i * 30),
            "sg_end_date": _iso_date(240 + i * 30),
            "sg_frame_rate": 24.0,
            "sg_progress": 40 + i * 15,
            "archived": False,
            "is_demo": False,
            "is_template": False,
            "image": _thumb(p["code"], 128, 72),
            "landing_page_url": f"/detail/Project/{p['id']}?legacy=true",
            "users": [_ref(u) for u in active_users],
            "created_at": _iso_date_time(-150 + i),
            "updated_at": _iso_date_time(-5 + i),
            "created_by": _ref(bot),
            "updated_by": _ref(bot),
        })
        for i, p in enumerate(project_seeds)
    ]
    p0, p1, p2 = projects
    for u in users:
        u.values["projects"] = [_ref(p0), _ref(p1), _ref(p2)]
    for a in api_users:
        a.values["projects"] = [_ref(p0), _ref(p1), _ref(p2)]

    # sequences -------------------------------------------------------------- #
    seq_seeds = [
        {"code": "sh010", "project": p0}, {"code": "sh020", "project": p0},
        {"code": "sh030", "project": p0}, {"code": "sh040", "project": p0},
        {"code": "hb010", "project": p1}, {"code": "hb020", "project": p1},
    ]
    sequences: list[_Row] = []
    for i, s in enumerate(seq_seeds):
        status = _pick(rng, SEQUENCE_STATUSES)
        cut_duration = 200 + int(rng() * 400)
        sequences.append(add("Sequence", 100 + i, {
            "code": s["code"],
            "cached_display_name": s["code"],
            "description": f"Sequence {s['code']}",
            "sg_status_list": status,
            "sg_timecode": 3_600_000 + i * 60_000,
            "sg_cut_duration": cut_duration,
            "image": _thumb(s["code"]),
            "project": _ref(s["project"]),
            "shots": [],
            "created_at": _iso_date_time(-140 + i),
            "updated_at": _iso_date_time(-20 + i),
            "created_by": _ref(bot),
            "updated_by": _ref(bot),
        }))

    # shots ------------------------------------------------------------------ #
    shots: list[_Row] = []
    shots_per_sequence = [7, 6, 5, 4, 5, 3]  # 30 in total
    shot_id = 862
    for si, seq in enumerate(sequences):
        count = shots_per_sequence[si] if si < len(shots_per_sequence) else 5
        for n in range(count):
            code = f"{seq.values['code']}_{str((n + 1) * 10).zfill(4)}"
            cut_in = 1001
            duration = 40 + int(rng() * 160)
            status = _pick(rng, SHOT_STATUSES)
            shot_type = _pick(rng, SHOT_TYPES)
            turnover = _iso_date(int(rng() * 120))
            complexity = int(rng() * 101)
            lens = 24 + _js_round(rng() * 800) / 10
            shot = add("Shot", shot_id, {
                "code": code,
                "cached_display_name": code,
                "description": f"Shot {code}",
                "sg_status_list": status,
                "sg_shot_type": shot_type,
                "sg_cut_in": cut_in,
                "sg_cut_out": cut_in + duration,
                "sg_cut_duration": duration,
                "sg_working_duration": duration * 5,
                "sg_turnover_date": turnover,
                "sg_complexity": complexity,
                "sg_lens": lens,
                "sg_omit": False,
                # One Shot with no picture, so a list of them reaches the type glyph.
                "image": None if shot_id == 865 else _thumb(code),
                "sg_shot_notes_url": None,
                "project": seq.values["project"],
                "sg_sequence": _ref(seq),
                "assets": [],
                "tasks": [],
                "created_at": _iso_date_time(-130 + shot_id % 40),
                "updated_at": _iso_date_time(-15 + shot_id % 10),
                "created_by": _ref(bot),
                "updated_by": _ref(bot),
            })
            shots.append(shot)
            seq.values["shots"].append(_ref(shot))
            shot_id += 1

    # shots with no sequence -------------------------------------------------- #
    # They stay out of `shots`, so they carry no task and no asset and the levels above
    # them hold nothing but the tree's ungrouped bucket.
    for i, code in enumerate(["nf_0010", "nf_0020", "nf_0030"]):
        duration = 60 + i * 20
        status = _pick(rng, SHOT_STATUSES)
        shot_type = _pick(rng, SHOT_TYPES)
        turnover = _iso_date(int(rng() * 120))
        complexity = int(rng() * 101)
        lens = 24 + _js_round(rng() * 800) / 10
        add("Shot", shot_id + i, {
            "code": code,
            "cached_display_name": code,
            "description": f"Shot {code}",
            "sg_status_list": status,
            "sg_shot_type": shot_type,
            "sg_cut_in": 1001,
            "sg_cut_out": 1001 + duration,
            "sg_cut_duration": duration,
            "sg_working_duration": duration * 5,
            "sg_turnover_date": turnover,
            "sg_complexity": complexity,
            "sg_lens": lens,
            "sg_omit": False,
            "image": _thumb(code),
            "sg_shot_notes_url": None,
            "project": _ref(p2),
            "sg_sequence": None,
            "assets": [],
            "tasks": [],
            "created_at": _iso_date_time(-100 + i),
            "updated_at": _iso_date_time(-10 + i),
            "created_by": _ref(bot),
            "updated_by": _ref(bot),
        })

    # assets ----------------------------------------------------------------- #
    assets: list[_Row] = []
    for i, a in enumerate(ASSET_SEEDS):
        project = p0 if a["project"] == 0 else p1
        status = _pick(rng, SHOT_STATUSES)
        build_days = 1 + int(rng() * 20)
        complexity = int(rng() * 101)
        due = _iso_date(int(rng() * 150))
        published = rng() > 0.5
        assets.append(add("Asset", 1226 + i, {
            "code": a["code"],
            "cached_display_name": a["code"],
            "description": f"{a['type']} asset {a['code']}",
            "sg_status_list": status,
            "sg_asset_type": a["type"],
            "sg_build_days": build_days,
            "sg_complexity": complexity,
            "sg_due_date": due,
            "sg_published": published,
            "image": _thumb(a["code"]),
            "project": _ref(project),
            "shots": [],
            "sequences": [],
            "tasks": [],
            "created_at": _iso_date_time(-135 + i),
            "updated_at": _iso_date_time(-12 + i),
            "created_by": _ref(bot),
            "updated_by": _ref(bot),
        }))
    # Link a few assets into shots of the same project, both ends.
    for shot in shots:
        project_id = shot.values["project"]["id"]
        candidates = [a for a in assets if a.values["project"]["id"] == project_id]
        chosen = [a for a in candidates if rng() < 0.3]
        shot.values["assets"] = [_ref(a) for a in chosen]
        for asset in chosen:
            asset.values["shots"].append(_ref(shot))

    # tasks ------------------------------------------------------------------ #
    tasks: list[_Row] = []
    task_id = 5700
    task_targets = [*shots, *assets]  # 40 tasks, one per shot and asset
    for target in task_targets:
        applicable = [s for s in steps if s.values["entity_type"] == target.type]
        step = _pick(rng, applicable if len(applicable) > 0 else steps)
        content = str(step.values["code"])
        start = int(rng() * 90)
        assignee = _pick(rng, active_users)
        status = _pick(rng, TASK_STATUSES)
        due = _iso_date(start + 3 + int(rng() * 12))
        # Minutes. 2400 is a Monday-to-Friday week at the probed site's hours_per_day of 8.
        duration = 480 * (1 + int(rng() * 5))
        est = 480 * (1 + int(rng() * 5))
        logged = 60 * int(rng() * 40)
        percent = int(rng() * 130)
        task = add("Task", task_id, {
            "content": content,
            "cached_display_name": content,
            "sg_description": f"{content} on {target.values['code']}",
            "sg_status_list": status,
            "start_date": _iso_date(start),
            "due_date": due,
            "duration": duration,
            "est_in_mins": est,
            "time_logs_sum": logged,
            "time_percent_of_est": percent,
            "color": "pipeline_step",
            "milestone": False,
            "project": target.values["project"],
            "entity": _ref(target),
            "step": _ref(step),
            "task_assignees": [_ref(assignee)],
            "task_reviewers": [],
            "upstream_tasks": [],
            "created_at": _iso_date_time(-120 + (task_id % 50)),
            "updated_at": _iso_date_time(-8 + (task_id % 6)),
            "created_by": _ref(bot),
            "updated_by": _ref(bot),
        })
        target.values["tasks"].append(_ref(task))
        tasks.append(task)
        task_id += 1

    # versions --------------------------------------------------------------- #
    versions: list[_Row] = []
    version_id = 17055
    version_count = counts.versions if counts.versions is not None else 60
    for i in range(version_count):
        # 005_link_usage: on the sample project every Version links through `entity`,
        # almost all to a Shot.
        target = assets[i % len(assets)] if i % 7 == 6 else shots[i % len(shots)]
        target_tasks = target.values.get("tasks") or []
        task_ref = target_tasks[0] if target_tasks else None
        step_name = (
            str(fixtures.index[f"Task:{task_ref['id']}"].values.get("content") or "comp")
            if task_ref
            else "comp"
        )
        revision = 1 + (i // len(shots)) * 3 + (i % 3)
        flat = re.sub(r"\s+", "", step_name.lower())
        code = f"{target.values['code']}_{flat}_v{str(revision).zfill(3)}"
        first = 1001
        last = first + 40 + int(rng() * 120)
        status = _pick(rng, VERSION_STATUSES)
        version_type = _pick(rng, VERSION_TYPES)
        approved = rng() > 0.85
        bar_color = _pick(rng, BAR_COLORS)
        artist = _pick(rng, active_users)
        tank = fixtures.index[f"Project:{target.values['project']['id']}"].values["tank_name"]
        version = add("Version", version_id, {
            "code": code,
            "cached_display_name": code,
            "description": f"Review submission for {target.values['code']}",
            "sg_department": step_name if i % 2 == 0 else None,
            "sg_status_list": status,
            "sg_version_type": version_type,
            "sg_first_frame": first,
            "sg_last_frame": last,
            "frame_count": last - first + 1,
            "sg_uploaded_movie_frame_rate": 24.0,
            "sg_uploaded_movie_transcoding_status": 1,
            "sg_path_to_frames": f"/mnt/prod/{tank}/{target.values['code']}/{code}.%04d.exr",
            "sg_path_to_movie": f"/mnt/prod/mov/{code}.mov",
            "client_approved": approved,
            "client_approved_at": None,
            # Every seventh Version has no picture: 99 of 100 read null on the sample
            # project (field_types/image).
            "image": None if i % 7 == 3 else _thumb(code),
            "sg_uploaded_movie": None,
            "sg_bar_color": bar_color,
            "project": target.values["project"],
            "entity": _ref(target),
            "sg_task": task_ref,
            "user": _ref(artist),
            "playlists": [],
            "created_at": _iso_date_time(-100 + (i % 90), i),
            "updated_at": _iso_date_time(-3 + (i % 3), i),
            "created_by": _ref(bot),
            "updated_by": _ref(bot),
        })
        versions.append(version)
        version_id += 1

    # notes, replies and attachments ------------------------------------------ #
    # The link to a Note lives on the Reply, in `Reply.entity`; `Note.replies` is the
    # reverse view of it (entity_types/Reply). An Attachment links back through
    # `attachment_links` (entity_types/Attachment).
    notes: list[_Row] = []
    #: Each Reply with the day and minute it was written, for the event log below.
    replies: list[tuple[_Row, int, int]] = []
    note_id = 11030
    reply_id = 610
    attachment_id = 2626
    for i, seed_note in enumerate(NOTE_SEEDS):
        # One thread in the second project, so a per-project read has something to cut.
        wanted = 23 if i == 3 else i * 5
        target = versions[wanted] if wanted < len(versions) else shots[i]
        project = target.values["project"]
        author = users[seed_note["author"]]
        addressed = users[(seed_note["author"] + 1) % len(users)]
        note = add("Note", note_id, {
            "subject": seed_note["subject"],
            "content": seed_note["content"],
            # `cached_display_name` is `"<subject> - <content>"` when both are set (entity_types/Note).
            "cached_display_name": f"{seed_note['subject']} - {seed_note['content']}",
            "sg_status_list": seed_note["status"],
            "sg_note_type": seed_note["note_type"],
            # The codes `unread` and `read`, never a boolean (067_notes_in_the_stream).
            "read_by_current_user": seed_note["read"],
            "publish_status": "published",
            "project": project,
            "user": _ref(author),
            "note_links": [_ref(target)],
            "tasks": [],
            "replies": [],
            "attachments": [],
            "addressings_to": [_ref(addressed)],
            "addressings_cc": [],
            "created_at": _iso_date_time(seed_note["day"]),
            "updated_at": _iso_date_time(seed_note["day"]),
            "created_by": _ref(author),
            "updated_by": _ref(author),
        })
        for file in seed_note["attachments"]:
            attachment = add("Attachment", attachment_id, {
                "display_name": file["filename"],
                "cached_display_name": file["filename"],
                "description": None,
                "original_fname": file["filename"],
                "filename": file["filename"],
                # Neither fills in on an uploaded row; take the size from the bytes you sent
                # and the extension from the filename (entity_types/Attachment).
                "file_extension": None,
                "file_size": None,
                "this_file": {
                    "url": f"https://media.example.studio/{file['filename']}",
                    "name": file["filename"],
                    "content_type": "image/png",
                    "link_type": "upload",
                },
                "processing_status": None,
                "sg_status_list": "na",
                "project": project,
                "attachment_links": [_ref(note)],
                "created_at": _iso_date_time(seed_note["day"], file["minutes"] * 60),
                "updated_at": _iso_date_time(seed_note["day"], file["minutes"] * 60),
                "created_by": _ref(author),
                "updated_by": _ref(author),
            })
            note.values["attachments"].append(_ref(attachment))
            attachment_id += 1
        for seeded in seed_note["replies"]:
            reply_author = users[seeded["author"]]
            reply = add("Reply", reply_id, {
                "content": seeded["content"],
                # Filled from `content` at create time, and it is what `Note.replies`
                # returns as a name.
                "cached_display_name": seeded["content"],
                "entity": _ref(note),
                "user": _ref(reply_author),
                "publish_status": "published",
                "created_at": _iso_date_time(seed_note["day"], seeded["minutes"] * 60),
                "updated_at": _iso_date_time(seed_note["day"], seeded["minutes"] * 60),
            })
            note.values["replies"].append(_ref(reply))
            replies.append((reply, seed_note["day"], seeded["minutes"]))
            reply_id += 1
        notes.append(note)
        note_id += 1

    # the event log ----------------------------------------------------------- #
    pending: list[tuple[int, int, dict[str, Any]]] = []

    def event(day: int, seconds: int, values: dict[str, Any]) -> None:
        pending.append((day, seconds, values))

    def changed(row: _Row, old_value: str, day: int, seconds: int, user: _Row) -> None:
        new_value = row.values["sg_status_list"]
        event(day, seconds, {
            "event_type": f"Shotgun_{row.type}_Change",
            "attribute_name": "sg_status_list",
            "description": (
                f'{display_name_of(user.values, "")} changed "Status" from "{old_value}" '
                f'to "{new_value}" on {row.type} {display_name_of(row.values, "")}'
            ),
            # `old_value` and `new_value` exist where `meta.type` is `attribute_change`
            # and nowhere else (025_event_log).
            "meta": {
                "type": "attribute_change",
                "attribute_name": "sg_status_list",
                "entity_type": row.type,
                "entity_id": row.id,
                "in_create": False,
                "field_data_type": "status_list",
                "old_value": old_value,
                "new_value": new_value,
                "platform_id": None,
            },
            "entity": _ref(row),
            "project": row.values["project"],
            "user": _ref(user),
        })

    def created(row: _Row, day: int, seconds: int, user: _Row, extra: dict[str, Any] | None = None) -> None:
        event(day, seconds, {
            "event_type": f"Shotgun_{row.type}_New",
            "attribute_name": None,
            "description": (
                f'{display_name_of(user.values, "")} created {row.type} {display_name_of(row.values, "")}'
            ),
            "meta": {"type": "new_entity", "entity_type": row.type, "entity_id": row.id, **(extra or {})},
            "entity": _ref(row),
            "project": row.values.get("project"),
            "user": _ref(user),
        })

    for i, shot in enumerate(shots[:6]):
        changed(shot, "wtg", -9 + i, 3600 + i * 137, users[i % len(users)])
    for i, version in enumerate(versions[:4]):
        changed(version, "rev", -5 + i, 7200 + i * 211, active_users[i % len(active_users)])
    for i, task in enumerate(tasks[:3]):
        changed(task, "wtg", -7 + i, 5400 + i * 97, active_users[(i + 1) % len(active_users)])
    for i, note in enumerate(notes):
        author = fixtures.index[f"HumanUser:{note.values['user']['id']}"]
        created(note, NOTE_SEEDS[i]["day"] if i < len(NOTE_SEEDS) else 0, 30, author)
    for reply, day, minutes in replies:
        author = fixtures.index[f"HumanUser:{reply.values['user']['id']}"]
        note = fixtures.index[f"Note:{reply.values['entity']['id']}"]
        event(day, minutes * 60, {
            "event_type": "Shotgun_Reply_New",
            "attribute_name": None,
            "description": (
                f'{display_name_of(author.values, "")} replied to Note {display_name_of(note.values, "")}'
            ),
            # A `new_entity` meta carries the row's id and its content, and no values.
            "meta": {
                "type": "new_entity", "entity_type": "Reply", "entity_id": reply.id,
                "content": reply.values["content"],
            },
            "entity": _ref(reply),
            "project": note.values["project"],
            "user": _ref(author),
        })
    # `entity` goes null when its target is deleted and `meta` remembers, so a deleted
    # row's history is reachable by `event_type` and `created_at` alone (025_event_log).
    event(-30, 0, {
        "event_type": "Shotgun_Shot_Change",
        "attribute_name": "sg_status_list",
        "description": 'A shot that no longer exists changed "Status" from "ip" to "omt"',
        "meta": {
            "type": "attribute_change",
            "attribute_name": "sg_status_list",
            "entity_type": "Shot",
            "entity_id": 9001,
            "in_create": False,
            "field_data_type": "status_list",
            "old_value": "ip",
            "new_value": "omt",
            "platform_id": None,
        },
        "entity": None,
        "project": _ref(p0),
        "user": _ref(bot),
    })
    pending.sort(key=lambda entry: entry[0] * 86_400 + entry[1])
    # Ids ascend with time, and the head is sparse: blocks are reserved ahead of use and
    # fill in later, so a cursor on `max(id)` loses what lands in a gap (025_event_log).
    event_id = 1_240_000
    for _day, _seconds, values in pending:
        created_at = _iso_date_time(_day, _seconds)
        add("EventLogEntry", event_id, {
            "cached_display_name": None,
            "session_uuid": f"7a1b2c3d-0000-4000-8000-{str(event_id).zfill(12)}",
            "created_at": created_at,
            **values,
        })
        event_id += 3 if event_id % 7 == 0 else 1

    # what each person follows ------------------------------------------------- #
    # A follow is a type and an id and nothing else: no name, and no date the follow
    # started (get_entity_human_users_id_following).
    def follow(user_ref: dict[str, Any] | None, row: _Row) -> None:
        if not user_ref or user_ref.get("type") != "HumanUser":
            return
        listed = fixtures.follows.setdefault(user_ref["id"], [])
        if not any(r["type"] == row.type and r["id"] == row.id for r in listed):
            listed.append(_ref(row))

    for note in notes:
        follow(note.values["user"], note)
        for to in note.values["addressings_to"]:
            follow(to, note)
    for reply, _day, _minutes in replies:
        note = fixtures.index.get(f"Note:{reply.values['entity']['id']}")
        if note:
            follow(reply.values["user"], note)
    for task in tasks:
        for assignee in task.values["task_assignees"]:
            follow(assignee, task)

    return fixtures


# -------------------------------------------------------------------------- #
# the client                                                                  #
# -------------------------------------------------------------------------- #

_ARM = object()


class MockClient:
    """An `SgClient` over generated fixtures."""

    def __init__(self, options: MockClientOptions | None = None, **overrides: Any) -> None:
        if options is None:
            options = MockClientOptions(**overrides)
        elif overrides:
            raise TypeError("MockClient takes an options object or keywords, not both.")
        self._lock = threading.RLock()
        self._fixtures = _build_fixtures(options.seed, options.counts)
        self._latency_ms = options.latency_ms
        self._clock = _to_clock(options.now)
        self._pending_failure = options.fail_next

    def fail_next(self, failure: Any = _ARM) -> None:
        """Make the next call raise an `SgApiError`, for demoing an error state.

        Pass None to disarm one that was already set.
        """
        with self._lock:
            self._pending_failure = MockFailure() if failure is _ARM else failure

    def rows_of(self, entity_type: str) -> list[dict[str, Any]]:
        """Rows of a type, in id order. Handy for writing assertions against the fixtures."""
        with self._lock:
            return [row.values for row in self._fixtures.rows.get(entity_type, [])]

    @property
    def now(self) -> float:
        """Epoch milliseconds the date operators resolve against."""
        return self._clock()

    # ------------------------------------------------------------------ #

    def _gate(self) -> None:
        with self._lock:
            failure = self._pending_failure
            self._pending_failure = None
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000)
        if failure:
            raise SgApiError(
                failure.status,
                failure.body,
                failure.message if failure.message is not None else f"Flow PT API error {failure.status}",
            )

    def _schema_of(self, entity_type: str) -> dict[str, _FieldSpec]:
        spec = SPECS.get(entity_type)
        # 404 `Entity type 'X' does not exist.` is what a schema read answers.
        if not spec:
            raise SgApiError(404, None, f"Entity type '{entity_type}' does not exist.")
        return spec

    def entity_types(self) -> list[EntityTypeInfo]:
        self._gate()
        return [EntityTypeInfo(name=name, display_name=DISPLAY_NAMES.get(name, name)) for name in SPECS]

    def fields(self, entity_type: str, project_id: int | None = None) -> dict[str, FieldSchema]:
        self._gate()
        spec = self._schema_of(entity_type)
        hidden = None if project_id is None else HIDDEN_VALUES.get(project_id, {})
        out: dict[str, FieldSchema] = {}
        for name, s in spec.items():
            field = FieldSchema(
                name=name,
                display_name=s.display_name,
                entity_type=entity_type,
                data_type=s.data_type,
                editable=s.editable,
                mandatory=s.mandatory,
                unique=s.unique,
            )
            if s.valid_types:
                field.valid_types = list(s.valid_types)
            if s.valid_values:
                field.valid_values = list(s.valid_values)
            if s.display_values:
                field.display_values = dict(s.display_values)
            if s.default_value is not None:
                field.default_value = s.default_value
            if s.description:
                field.description = s.description
            # `hidden_values` appears only when the schema is read with `project_id` (009_status_lists).
            if hidden is not None and s.data_type in ("status_list", "list"):
                field.hidden_values = list(hidden.get(f"{entity_type}.{name}", []))
            # The same correction a schema read gets, so the mock answers the schema a client sees.
            for key, value in (field_schema_override(entity_type, name) or {}).items():
                setattr(field, key, value)
            out[name] = field
        return out

    def field_with_project(self, entity_type: str, field: str, project_id: int) -> FieldSchema:
        all_fields = self.fields(entity_type, project_id)
        one = all_fields.get(field)
        # The 404 names the type and the field together, the only schema error that says
        # which half is wrong.
        if not one:
            raise SgApiError(404, None, f"Field '{entity_type}.{field}' does not exist.")
        return one

    def search(self, entity_type: str, options: SearchOptions | None = None) -> SearchResult:
        self._gate()
        options = options if options is not None else SearchOptions()
        with self._lock:
            spec = self._schema_of(entity_type)
            all_rows = self._fixtures.rows.get(entity_type, [])
            matched = [row for row in all_rows if self._match_group(row, entity_type, options.filters)]
            ordered = self._apply_sort(matched, entity_type, options.sort)

            page = options.page or {}
            size = page.get("size", 50)
            number = page.get("number", 1)
            start = (number - 1) * size
            rows = ordered[start:start + size]
            return SearchResult(
                data=[self._project_row(row, spec, options.fields) for row in rows],
                # `links.next` is emitted forever, so a full page is the only signal (006_pagination).
                has_more=len(rows) == size,
            )

    def text_search(
        self,
        text: str,
        entity_types: dict[str, TextSearchFilter],
        page: Page | None = None,
    ) -> list[TextSearchRow]:
        self._gate()
        words = [w for w in re.split(r"\s+", text.strip()) if w]
        if len(words) == 0:
            raise SgApiError(400, {"page": None}, "text must be filled")
        page = page or {}
        size = page.get("size", 25)
        # The cap is 25 and so is the default, and the message is off by one (053_text_search_matching).
        if size > 25:
            raise SgApiError(400, None, "size must be less than 25")
        if size < 1:
            raise SgApiError(400, None, "size must be greater than 0")
        number = page.get("number", 1)
        if number < 1:
            raise SgApiError(400, None, "number must be greater than 0")

        needles = [w.lower() for w in words]
        hits: list[tuple[str, TextSearchRow]] = []
        with self._lock:
            for entity_type, filter in entity_types.items():
                # The map's value is a filter array, `[]` for none, and the array form is `and` only.
                group: WireGroup = {"logical_operator": "and", "conditions": to_filter_array(filter)}
                for row in self._fixtures.rows.get(entity_type, []):
                    if not self._match_group(row, entity_type, group):
                        continue
                    name = display_name_of(row.values, f"#{row.id}")
                    # A row also matches on the name of the row it links to.
                    links = self._linked_pair(row)
                    haystack = f"{name} {links[1]}".lower()
                    if not all(w in haystack for w in needles):
                        continue
                    hits.append((name, TextSearchRow(
                        type=entity_type,
                        id=row.id,
                        name=name,
                        links=links,
                        status=_status_code(row.values),
                    )))
        # Rows come back shortest name first, across types, not by id and not grouped by type.
        hits.sort(key=lambda hit: (len(hit[0]), hit[0], hit[1].id))
        start = (number - 1) * size
        return [row for _name, row in hits[start:start + size]]

    def update(self, entity_type: str, id: int, patch: dict[str, Any]) -> EntityRow:
        self._gate()
        with self._lock:
            spec = self._schema_of(entity_type)
            row = self._fixtures.index.get(f"{entity_type}:{id}")
            # The 404 names the type and the id (put_entity_type_id).
            if not row:
                raise SgApiError(404, None, f"Entity of type [{entity_type}] with id={id} does not exist.")
            for name, value in patch.items():
                field = spec.get(name)
                # `API create() Reply.project doesn't exist.` is the create spelling of this
                # 400 (entity_types/Reply); a write to a read-only field is `is read only.`
                # (entity_types/Sequence).
                if not field:
                    raise SgApiError(400, None, f"API update() {entity_type}.{name} doesn't exist.")
                if field.create_only:
                    raise SgApiError(
                        400, None, f"API update() {entity_type}.{name} is editable on create only."
                    )
                if not field.editable:
                    raise SgApiError(400, None, f"API update() {entity_type}.{name} is read only.")
                self._check_link("update", entity_type, name, field, value)
                # Writing "" to a text field stores null: the two are one value (field_types/text).
                row.values[name] = None if field.data_type == "text" and value == "" else value
            if "updated_at" in spec and len(patch) > 0:
                row.values["updated_at"] = _iso_date_time(0)
            # A write answers the whole record, changed fields and untouched ones alike
            # (024_read_after_write).
            return self._project_row(row, spec)

    def summarize(self, entity_type: str, options: SummarizeOptions | None = None) -> SummarizeResult:
        """Counts without paging rows.

        `count` and the numeric aggregates are modelled; the rest of the vocabulary the
        endpoint prints is not. A grouping returns one group per distinct value with the
        empties under a `''` group, `group_value` is what the grouping was computed on
        and `group_name` the server's render of it, and one type per field per call wins
        (020_summarize).
        """
        self._gate()
        options = options if options is not None else SummarizeOptions()
        with self._lock:
            self._schema_of(entity_type)
            all_rows = self._fixtures.rows.get(entity_type, [])
            matched = [row for row in all_rows if self._match_group(row, entity_type, options.filters)]
            fields = options.summary_fields or [SummaryField(field="id", type="count")]

            def summarize(rows: list[_Row]) -> dict[str, float]:
                out: dict[str, float] = {}
                for f in fields:
                    values = [v for v in (self._first(r, f.field) for r in rows) if v is not None]
                    numbers = [n for n in (_to_number(v) for v in values) if n is not None]
                    if f.type in ("count", "record_count"):
                        out[f.field] = len(rows) if f.field == "id" or f.type == "record_count" else len(values)
                    elif f.type == "sum":
                        out[f.field] = sum(numbers)
                    elif f.type == "maximum":
                        out[f.field] = max(numbers) if numbers else 0
                    elif f.type == "minimum":
                        out[f.field] = min(numbers) if numbers else 0
                    elif f.type == "average":
                        out[f.field] = sum(numbers) / len(numbers) if numbers else 0
                    # An unmodelled type is left out, the way an unsummarizable field
                    # answers 200 with the key absent (020_summarize).
                return out

            grouping = options.grouping[0] if options.grouping else None
            if grouping is None:
                return SummarizeResult(summaries=summarize(matched), groups=[])
            self._refuse_grouping(entity_type, grouping.field)

            buckets: dict[str, tuple[Any, list[_Row]]] = {}
            for row in matched:
                raw = self._first(row, grouping.field)
                # A multi_entity row is grouped on its whole set of links, as an array of
                # references; the corpus has not measured that grouping.
                if isinstance(raw, list):
                    value = None if len(raw) == 0 else [self._group_value_of(one) for one in raw]
                else:
                    value = self._group_value_of(raw)
                key = "" if value is None else json.dumps(value, sort_keys=True, default=str)
                if key in buckets:
                    buckets[key][1].append(row)
                else:
                    buckets[key] = (value, [row])

            groups = [
                SummaryGroup(
                    group_name=(
                        ""
                        if value is None
                        else ", ".join(_group_label(v) for v in value)
                        if isinstance(value, list)
                        else _group_label(value)
                    ),
                    group_value=value,
                    summaries=summarize(rows),
                )
                for value, rows in buckets.values()
            ]
            groups.sort(key=lambda g: g.group_name)
            if grouping.direction == "desc":
                groups.reverse()
            return SummarizeResult(summaries=summarize(matched), groups=groups)

    def _group_value_of(self, value: Any) -> Any:
        """An entity group's value is the reference with its name and `valid` (020_summarize); a code is itself."""
        if not isinstance(value, dict) or "type" not in value:
            return value
        return {**self._decorate(value), "valid": "valid"}

    def _refuse_grouping(self, entity_type: str, field: str) -> None:
        """A field the server cannot group.

        400 `Grouping is not allowed for field <Type>.<field>.` on `image` and `summary`
        (field_types/image, field_types/summary), and a `pivot_column` is 500
        (field_types/pivot_column). `Note.read_by_current_user`, the per-person read
        state, is refused the same way; the corpus has not measured it.
        """
        spec = SPECS.get(entity_type, {}).get(field)
        data_type = spec.data_type if spec else None
        if data_type == "pivot_column":
            raise SgApiError(500, None, "Shotgun Server Error")
        refused = (
            data_type in ("image", "summary")
            or (entity_type == "Note" and field == "read_by_current_user")
        )
        if refused:
            raise SgApiError(400, None, f"Grouping is not allowed for field {entity_type}.{field}.")

    def hierarchy_expand(self, path: str) -> HierarchyNode:
        """One level of the navigation tree.

        Which levels a project has is the site's own navigation configuration and not a
        fixed hierarchy, the probed site's Shot path runs through the field name
        `sg_sequence` (post_hierarchy_search), so this fixture offers the two branches
        that configuration draws for a stock project: Shots under their Sequence, and
        Assets flat.
        """
        self._gate()
        with self._lock:
            parts = [p for p in path.split("/") if p]
            if len(parts) < 2 or parts[0] != "Project":
                # Code 107 appears on this endpoint and nowhere else: a lookup that found
                # the wrong number of rows, not a malformed request (post_hierarchy_expand).
                named = parts[1] if len(parts) > 1 else path
                raise SgApiError(400, None, f"Unexpected result looking for project: {named}: 0 found.")
            project_id = int(parts[1])
            project = self._fixtures.index.get(f"Project:{project_id}")
            if not project:
                raise SgApiError(400, None, f"Unexpected result looking for project: {parts[1]}: 0 found.")
            rest = parts[2:]
            above = "/".join(parts[:-1])
            parent_path = "/" if above == "Project" else f"/{above}"

            def node(
                label: str,
                ref: HierarchyRef,
                own: str,
                children: list[HierarchyNode],
                has_children: bool | None = None,
            ) -> HierarchyNode:
                return HierarchyNode(
                    label=label,
                    ref=ref,
                    path=own,
                    parent_path=parent_path if own == path else None,
                    has_children=has_children if has_children is not None else len(children) > 0,
                    children=children,
                )

            def entity_ref(entity_type: str, id: int) -> HierarchyRef:
                return HierarchyRef(kind="entity", value=EntityRef(type=entity_type, id=id))

            def type_ref(entity_type: str) -> HierarchyRef:
                return HierarchyRef(kind="entity_type", value=entity_type)

            def tasks_of(row: _Row) -> list[_Row]:
                out = []
                for t in row.values.get("tasks") or []:
                    found = self._fixtures.index.get(f"Task:{t['id']}")
                    if found is not None:
                        out.append(found)
                return out

            # A Shot or an Asset carries its Tasks, so it is a level rather than a leaf.
            def leaf(row: _Row, own: str) -> HierarchyNode:
                return node(
                    display_name_of(row.values, f"#{row.id}"),
                    entity_ref(row.type, row.id),
                    own,
                    [],
                    len(tasks_of(row)) > 0,
                )

            def rows_of(entity_type: str) -> list[_Row]:
                out = []
                for r in self._fixtures.rows.get(entity_type, []):
                    project_link = r.values.get("project")
                    if project_link and project_link.get("id") == project_id:
                        out.append(r)
                return out

            if len(rest) == 0:
                return node(
                    str(project.values["name"]),
                    entity_ref("Project", project_id),
                    path,
                    [
                        node("Assets", type_ref("Asset"), f"{path}/Asset", [], len(rows_of("Asset")) > 0),
                        node("Shots", type_ref("Shot"), f"{path}/Shot", [], len(rows_of("Shot")) > 0),
                    ],
                )
            if len(rest) == 1 and rest[0] == "Asset":
                return node(
                    "Assets",
                    type_ref("Asset"),
                    path,
                    [leaf(r, f"{path}/id/{r.id}") for r in rows_of("Asset")],
                )

            def no_rows(label: str) -> HierarchyNode:
                """A child standing for a level with nothing in it. It carries no path of its own."""
                return node(label, HierarchyRef(kind="empty", value=None), path, [], False)

            def loose_shots() -> list[_Row]:
                return [r for r in rows_of("Shot") if r.values.get("sg_sequence") is None]

            if len(rest) == 1 and rest[0] == "Shot":
                groups = [
                    node(
                        str(seq.values["code"]),
                        entity_ref("Sequence", seq.id),
                        f"{path}/sg_sequence/Sequence/{seq.id}",
                        [],
                        len(seq.values["shots"]) > 0,
                    )
                    for seq in rows_of("Sequence")
                ]
                # A grouping field with no rows hides every row under it: the level answers
                # one `empty` child and no bucket, although the `__none__` path under it
                # answers them all. The site emits the bucket once after every group and the
                # client dedupes the repeats; this fixture emits it once, and only where it
                # holds rows (064_hierarchy_expand_buckets).
                if len(groups) == 0:
                    return node("Shots", type_ref("Shot"), path, [no_rows("No Shots")])
                if len(loose_shots()) > 0:
                    groups.append(node(
                        "Shots with no Sequence",
                        type_ref("Shot"),
                        f"{path}/sg_sequence/Sequence/__none__",
                        [],
                        True,
                    ))
                return node("Shots", type_ref("Shot"), path, groups)
            # The bucket at both its spellings: an expand writes `<field>/<GroupType>/__none__`
            # and a search writes `<field>/__none__` (064_hierarchy_expand_buckets).
            if len(rest) > 1 and rest[0] == "Shot" and rest[1] == "sg_sequence" and rest[-1] == "__none__":
                loose = loose_shots()
                return node(
                    "Shots with no Sequence",
                    type_ref("Shot"),
                    path,
                    [leaf(r, f"{path}/id/{r.id}") for r in loose] if loose else [no_rows("No Shots")],
                )
            # The 400 names the grouping field the level takes, and it is the only way to
            # learn it (post_hierarchy_expand).
            if rest[0] == "Shot" and len(rest) > 1 and rest[1] not in ("sg_sequence", "id"):
                raise SgApiError(400, None, f"Unexpected field name in path: {rest[1]} (expecting sg_sequence)")
            if len(rest) == 4 and rest[0] == "Shot" and rest[1] == "sg_sequence" and rest[2] == "Sequence":
                seq = self._fixtures.index.get(f"Sequence:{int(rest[3])}")
                if not seq:
                    raise SgApiError(400, None, f"Unexpected result looking for project: {rest[3]}: 0 found.")
                shots = [
                    found
                    for found in (self._fixtures.index.get(f"Shot:{r['id']}") for r in seq.values["shots"])
                    if found is not None
                ]
                return node(
                    str(seq.values["code"]),
                    entity_ref("Sequence", seq.id),
                    path,
                    [leaf(r, f"{path}/id/{r.id}") for r in shots],
                )
            # A Shot or an Asset, which holds a Tasks folder, and the folder itself.
            owner = self._row_at_path(rest) if len(rest) > 1 and rest[-2] == "id" else None
            if owner:
                found = tasks_of(owner)
                return node(
                    display_name_of(owner.values, f"#{owner.id}"),
                    entity_ref(owner.type, owner.id),
                    path,
                    [node("Tasks", type_ref("Task"), f"{path}/Task", [], True)] if found else [],
                )
            if rest[-1] == "Task":
                holder = self._row_at_path(rest[:-1])
                found = tasks_of(holder) if holder else []
                return node(
                    "Tasks",
                    type_ref("Task"),
                    path,
                    [leaf(t, f"{path}/id/{t.id}") for t in found],
                )
            # A path this fixture does not model: a node with nothing under it.
            last = path.split("/")[-1]
            return node(last, HierarchyRef(kind="empty", value=None), path, [], False)

    def hierarchy_search(self, root_path: str, entity: EntityRef) -> list[HierarchyPath]:
        """Where a row sits in the tree.

        The endpoint takes an entity and answers its breadcrumb; it does not match words
        (post_hierarchy_search).
        """
        self._gate()
        with self._lock:
            incremental = self._path_to(entity.type, entity.id)
            if len(incremental) == 0 or not incremental[-1].startswith(root_path):
                return []
            labels = [self._label_at_path(p) for p in incremental[1:-1]]
            row = self._fixtures.index.get(f"{entity.type}:{entity.id}")
            project_link = row.values.get("project") if row else None
            return [
                HierarchyPath(
                    label=(
                        display_name_of(row.values, f"#{entity.id}")
                        if row
                        else f"{entity.type} #{entity.id}"
                    ),
                    # The project is not in `path_label`, and the row itself is not either.
                    path_label=" > ".join(labels),
                    incremental_path=incremental,
                    ref=EntityRef(type=entity.type, id=entity.id),
                    project_id=(project_link["id"] if project_link else row.id) if row else None,
                )
            ]

    def _label_at_path(self, path: str) -> str:
        """What a level of the tree is called, without opening it."""
        rest = [p for p in path.split("/") if p][2:]
        last = rest[-1] if rest else None
        if last == "Asset":
            return "Assets"
        if last == "Shot":
            return "Shots"
        if last == "Task":
            return "Tasks"
        if last == "__none__":
            return "Shots with no Sequence"
        if len(rest) > 1 and rest[-2] == "Sequence":
            sequence = self._fixtures.index.get(f"Sequence:{int(last)}") if last else None
            return display_name_of(sequence.values, f"#{sequence.id}") if sequence else ""
        row = self._row_at_path(rest)
        return display_name_of(row.values, f"#{row.id}") if row else ""

    def _row_at_path(self, rest: list[str]) -> _Row | None:
        """The row a `.../id/<n>` path segment names, from the type the path last named."""
        if not rest or not rest[-1].isdigit():
            return None
        id = int(rest[-1])
        entity_type = "Task" if "Task" in rest else "Asset" if rest[0] == "Asset" else "Shot"
        return self._fixtures.index.get(f"{entity_type}:{id}")

    def _path_to(self, entity_type: str, id: int) -> list[str]:
        """The breadcrumb to a row, root first, the row itself last. Empty when it is not in the tree."""
        row = self._fixtures.index.get(f"{entity_type}:{id}")
        if not row:
            return []
        if entity_type == "Project":
            return [f"/Project/{id}"]
        project_link = row.values.get("project")
        if not project_link:
            return []
        root = f"/Project/{project_link['id']}"
        if entity_type == "Sequence":
            return [root, f"{root}/Shot", f"{root}/Shot/sg_sequence/Sequence/{id}"]
        if entity_type == "Asset":
            return [root, f"{root}/Asset", f"{root}/Asset/id/{id}"]
        if entity_type == "Shot":
            sequence = row.values.get("sg_sequence")
            # A search spells the ungrouped bucket without the group type
            # (064_hierarchy_expand_buckets).
            above = (
                self._path_to("Sequence", sequence["id"])
                if sequence
                else [root, f"{root}/Shot", f"{root}/Shot/sg_sequence/__none__"]
            )
            if len(above) == 0:
                return []
            return [*above, f"{above[-1]}/id/{id}"]
        if entity_type == "Task":
            owner = row.values.get("entity")
            if not owner:
                return []
            above = self._path_to(owner["type"], owner["id"])
            if len(above) == 0:
                return []
            owner_path = above[-1]
            return [*above, f"{owner_path}/Task", f"{owner_path}/Task/id/{id}"]
        return []

    def statuses(self) -> list[StatusRecord]:
        self._gate()
        with self._lock:
            out: list[StatusRecord] = []
            for row in self._fixtures.rows.get("Status", []):
                icon_ref = row.values.get("icon")
                icon = self._fixtures.index.get(f"Icon:{icon_ref['id']}") if icon_ref else None
                out.append(StatusRecord(
                    id=row.id,
                    code=str(row.values.get("code") or ""),
                    name=str(row.values.get("name") or ""),
                    bg_color=row.values.get("bg_color"),
                    icon=_to_status_icon(icon.values) if icon else None,
                ))
            return out

    def create(self, entity_type: str, body: dict[str, Any]) -> EntityRow:
        """Create one row and answer it.

        `project` is the whole contract on a project-scoped type, and the schema's
        `mandatory` flags are not it: the identity field is optional and the server fills
        it, except on a Note, which stays titleless (012_create_version,
        entity_types/Note). Nothing is unique, so two identical creates make two rows.
        """
        self._gate()
        with self._lock:
            spec = self._schema_of(entity_type)
            # `{}` and the identity field alone both answer this, with the body echoed.
            if "project" in spec and "project" not in body:
                raise SgApiError(
                    400, None, f"API create() missing 'project' attribute: {_json(body)}"
                )
            identity = IDENTITY_FIELD.get(entity_type)
            for name, value in body.items():
                field = spec.get(name)
                if not field:
                    raise SgApiError(400, None, f"API create() {entity_type}.{name} doesn't exist.")
                if not field.editable and not field.create_only:
                    raise SgApiError(400, None, f"API create() {entity_type}.{name} is read only.")
                self._check_link("create", entity_type, name, field, value)
                # Omitting the identity field and sending an empty one are different
                # (entity_types/Shot).
                if name == identity and value == "":
                    raise SgApiError(
                        400,
                        None,
                        f"Create failed for [{entity_type}]: Cannot set identifier field to empty. "
                        f"({entity_type})",
                    )
            id = self._next_id(entity_type)
            values: dict[str, Any] = {}
            for name, field in spec.items():
                # `default_value` applies when the key is omitted, so a status is never unset.
                values[name] = [] if field.data_type == "multi_entity" else field.default_value
            # `user` and `created_by` hold the authenticating user (entity_types/Note).
            authors = self._fixtures.rows.get("ApiUser") or []
            authored = _ref(authors[0]) if authors else None
            if "created_by" in spec:
                values["created_by"] = authored
            if "updated_by" in spec:
                values["updated_by"] = authored
            if "user" in spec:
                values["user"] = authored
            # The answer echoes the server's defaults: a fresh Note is `unread` and
            # `published` (entity_types/Note), and so is a Reply (entity_types/Reply).
            if "read_by_current_user" in spec:
                values["read_by_current_user"] = "unread"
            if "publish_status" in spec:
                values["publish_status"] = "published"
            values["created_at"] = _iso_date_time(0)
            if "updated_at" in spec:
                values["updated_at"] = _iso_date_time(0)
            # An authored `created_at` or `updated_at` in the body is stored as sent
            # (070_authored_timestamps).
            values.update(body)
            values["id"] = id
            if identity and values.get(identity) is None and entity_type in GENERATED_IDENTITY:
                values[identity] = f"New {DISPLAY_NAMES.get(entity_type, entity_type)} {id}"
            if entity_type == "Note":
                values["cached_display_name"] = " - ".join(
                    str(v) for v in (values.get("subject"), values.get("content")) if v
                )
            else:
                values["cached_display_name"] = display_name_of({**values, "cached_display_name": None}, "")
            row = _Row(type=entity_type, id=id, values=values)
            self._fixtures.rows.setdefault(entity_type, []).append(row)
            self._fixtures.index[f"{entity_type}:{id}"] = row
            self._link_back(row)
            return self._project_row(row, spec)

    def upload(self, entity_type: str, id: int, file: UploadFile) -> UploadResult:
        """Put a file on a row, as the three-call handshake leaves the site.

        The field in the path picks the kind: `image` a Thumbnail, another field an
        Attachment on it, no field a generic Attachment on `attachment_links`
        (recipes/001). The mock moves no bytes, so there is no `ETag` to give back.
        """
        self._gate()
        with self._lock:
            spec = self._schema_of(entity_type)
            target = self._fixtures.index.get(f"{entity_type}:{id}")
            if not target:
                raise SgApiError(404, None, f"Entity of type [{entity_type}] with id={id} does not exist.")
            # `filename` is a required query parameter on the ticket call.
            if not file.filename:
                raise SgApiError(400, {"filename": ["filename is missing"]}, "Request Parameters invalid.")
            # The 404 for a field the type does not have is worded as a missing field.
            if file.field is not None and file.field not in spec:
                raise SgApiError(404, None, f"Field '{entity_type}.{file.field}' does not exist.")
            attachment_id = self._next_id("Attachment")
            authors = self._fixtures.rows.get("ApiUser") or []
            author = _ref(authors[0]) if authors else None
            attachment = _Row(type="Attachment", id=attachment_id, values={
                "id": attachment_id,
                "display_name": file.filename,
                "cached_display_name": file.filename,
                "description": None,
                "original_fname": file.filename,
                "filename": file.filename,
                # Neither fills in, then or later (entity_types/Attachment).
                "file_extension": None,
                "file_size": None,
                "this_file": {
                    "url": f"https://media.example.studio/{file.filename}",
                    "name": file.filename,
                    "content_type": "application/octet-stream",
                    "link_type": "upload",
                },
                # The token the field answers straight after an upload, which is not one of
                # the four its own `valid_values` declares (entity_types/Attachment).
                "processing_status": "thumbnail_pending_us",
                "sg_status_list": "na",
                "project": target.values.get("project"),
                "attachment_links": [{"type": entity_type, "id": id}],
                "created_at": _iso_date_time(0),
                "updated_at": _iso_date_time(0),
                "created_by": author,
                "updated_by": author,
            })
            self._fixtures.rows.setdefault("Attachment", []).append(attachment)
            self._fixtures.index[f"Attachment:{attachment_id}"] = attachment

            link_field = file.field if file.field is not None else ("attachments" if "attachments" in spec else None)
            field = spec.get(link_field) if link_field is not None else None
            if link_field is not None and field is not None:
                if field.data_type == "multi_entity":
                    target.values[link_field].append(_ref(attachment))
                elif link_field == "image":
                    # A media field is not readable yet: it answers an absolute placeholder
                    # on the site root under `/images/status/transient/` until the transcode
                    # lands (013_upload_media, field_types/image).
                    target.values[link_field] = f"{MOCK_SITE_URL}/images/status/transient/thumbnail_pending.png"
                else:
                    target.values[link_field] = str(attachment.values["this_file"]["url"])
            upload_type = "Thumbnail" if file.field == "image" else "Attachment"
            return UploadResult(
                upload_type=upload_type,
                upload_info={
                    "timestamp": _iso_date_time(0),
                    "upload_type": upload_type,
                    "upload_id": None,
                    "storage_service": "s3",
                    "original_filename": file.filename,
                    "multipart_upload": False,
                },
                # No bytes were moved, so there is no md5 receipt.
                etag=None,
            )

    def _check_link(self, verb: str, entity_type: str, name: str, field: _FieldSpec, value: Any) -> None:
        """An entity link is a `{type, id}` hash.

        A bare id is refused naming the class it got (entity_types/Reply,
        field_types/entity) and a hash with no `type` naming the missing key
        (field_types/entity).
        """
        if field.data_type != "entity" or value is None:
            return
        if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)):
            got = f"String: {_json(value)}" if isinstance(value, str) else f"Integer: {value}"
            raise SgApiError(
                400,
                None,
                f"API {verb}() {entity_type}.{name} expected [Hash, "
                "ActiveSupport::HashWithIndifferentAccess, ActionDispatch::Http::Parameters, "
                "ActionDispatch::Http::ParamsHashWithIndifferentAccess, NilClass] data type(s) "
                f"but got {got}",
            )
        if isinstance(value, EntityRef):
            return
        if isinstance(value, dict) and not isinstance(value.get("type"), str):
            raise SgApiError(
                400, None, f"API {verb}() invalid/missing entity hash string 'type': {_json(value)}"
            )

    def _next_id(self, entity_type: str) -> int:
        """The next free id of a type, which is what a create takes."""
        rows = self._fixtures.rows.get(entity_type, [])
        return max([row.id for row in rows], default=0) + 1

    def _link_back(self, row: _Row) -> None:
        """The reverse view of a link the server fills in: a Reply lands in `Note.replies`."""

        def push(owner: dict[str, Any] | None, field: str) -> None:
            if not owner:
                return
            target = self._fixtures.index.get(f"{owner['type']}:{owner['id']}")
            listed = target.values.get(field) if target else None
            if isinstance(listed, list):
                listed.append(_ref(row))

        if row.type == "Reply":
            push(row.values.get("entity"), "replies")
        if row.type == "Attachment":
            for link in row.values.get("attachment_links") or []:
                push(link, "attachments")

    def thread_contents(
        self,
        note_id: int,
        entity_fields: dict[str, list[str]] | None = None,
    ) -> list[ThreadRow]:
        """A Note, its Attachments and its Replies as one list in time order.

        The author key follows the row type, `created_by` on a Note and an Attachment and
        `user` on a Reply, whose hash carries an avatar the other two do not, and so does
        what `entity_fields` can widen: the Reply entry is accepted and changes nothing
        (get_entity_notes_id_thread_contents).
        """
        self._gate()
        with self._lock:
            note = self._fixtures.index.get(f"Note:{note_id}")
            # The 404 names the Note. On any other type it is worded as a missing field,
            # `Field 'Version.thread_contents' does not exist.`
            if not note:
                raise SgApiError(404, None, f"Note: {note_id} not found")

            def linked(field: str, entity_type: str) -> list[_Row]:
                out = []
                for r in note.values.get(field) or []:
                    found = self._fixtures.index.get(f"{entity_type}:{r['id']}")
                    if found is not None:
                        out.append(found)
                return out

            rows = [note, *linked("attachments", "Attachment"), *linked("replies", "Reply")]
            rows.sort(key=lambda r: (str(r.values.get("created_at") or ""), r.id))
            return [self._thread_row(row, (entity_fields or {}).get(row.type, [])) for row in rows]

    def _thread_row(self, row: _Row, widen: list[str]) -> ThreadRow:
        """One thread row, in the flat shape the endpoint answers."""
        is_reply = row.type == "Reply"
        author = self._thread_author(row.values.get("user" if is_reply else "created_by"), is_reply)
        fields: dict[str, Any] = {
            "type": row.type,
            "id": row.id,
            "created_at": row.values.get("created_at"),
        }
        # `content` is absent from an Attachment row: only its id, type, timestamp and
        # author come back.
        if row.type != "Attachment":
            fields["content"] = row.values.get("content")
        fields["user" if is_reply else "created_by"] = author
        # `entity_fields[Reply]` is accepted and widens nothing.
        if not is_reply:
            for name in widen:
                if name in SPECS.get(row.type, {}):
                    fields[name] = row.values.get(name)
        return ThreadRow(
            type=row.type,
            id=row.id,
            created_at=row.values.get("created_at"),
            content=None if row.type == "Attachment" else row.values.get("content"),
            author=author,
            fields=fields,
        )

    def _thread_author(self, value: dict[str, Any] | None, with_image: bool) -> ThreadAuthor | None:
        """`{id, name, type}`, plus a presigned `image` when the row is a Reply."""
        if not value:
            return None
        row = self._fixtures.index.get(f"{value['type']}:{value['id']}")
        author = ThreadAuthor(
            type=value["type"],
            id=value["id"],
            name=display_name_of(row.values, f"#{value['id']}") if row else f"#{value['id']}",
        )
        if with_image:
            author.image = row.values.get("image") if row else None
        return author

    def event_log(self, options: EventLogOptions | None = None) -> EventLogResult:
        """What changed, newest first.

        `meta` is read off the row because it takes no filter and no sort, and the cut is
        made on `project`, `entity`, `event_type`, `attribute_name` and `created_at`
        (025_event_log).
        """
        options = options if options is not None else EventLogOptions()
        page = options.page or {}
        size = page.get("size", 50)
        result = self.search("EventLogEntry", SearchOptions(
            filters=event_log_filters(options),
            fields=list(EVENT_LOG_FIELDS),
            sort="-id",
            page={"size": size, "number": page.get("number", 1)},
        ))
        return EventLogResult(
            data=[normalize_event_log_entry(row) for row in result.data],
            has_more=result.has_more,
        )

    def following(self, user_id: int, options: FollowingOptions | None = None) -> list[EntityRef]:
        """Everything one person follows, unpaged.

        `entity` takes the schema name or the snake_case plural, and both cuts are made
        server-side (get_entity_human_users_id_following).
        """
        self._gate()
        options = options if options is not None else FollowingOptions()
        with self._lock:
            # An ApiUser id under this path answers the same 404: a script cannot ask what
            # it follows.
            if not self._fixtures.index.get(f"HumanUser:{user_id}"):
                raise SgApiError(404, None, f'Couldn\'t find HumanUser with id="{user_id}"')
            if options.project_id is not None and not self._fixtures.index.get(f"Project:{options.project_id}"):
                raise SgApiError(404, None, f'Couldn\'t find Project with id="{options.project_id}"')
            wanted: str | None = None
            if options.entity is not None:
                wanted = _entity_type_named(options.entity)
                if wanted is None:
                    raise SgApiError(400, {"entity": ["entity is not valid"]}, "entity is not valid")
            out: list[EntityRef] = []
            for r in self._fixtures.follows.get(user_id, []):
                if wanted is not None and r["type"] != wanted:
                    continue
                if options.project_id is not None:
                    row = self._fixtures.index.get(f"{r['type']}:{r['id']}")
                    project_link = row.values.get("project") if row else None
                    if not project_link or project_link.get("id") != options.project_id:
                        continue
                out.append(EntityRef(type=r["type"], id=r["id"]))
            return out

    # ------------------------------------------------------------------ #
    # projection                                                          #
    # ------------------------------------------------------------------ #

    def _display_name_of_ref(self, entity_ref: dict[str, Any]) -> str | None:
        target = self._fixtures.index.get(f"{entity_ref['type']}:{entity_ref['id']}")
        if not target:
            return None
        # The `name` in an entity dict is the target's `cached_display_name` (060_entity_dict_name).
        return display_name_of(target.values, f"#{entity_ref['id']}")

    def _decorate(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, list):
            return [self._decorate(v) for v in value]
        name = self._display_name_of_ref(value)
        if name is None:
            return {"type": value["type"], "id": value["id"]}
        return {"type": value["type"], "id": value["id"], "name": name}

    def _project_row(
        self,
        row: _Row,
        spec: dict[str, _FieldSpec],
        fields: list[str] | None = None,
    ) -> EntityRow:
        """One row as `find` answers it: one flat map, links decorated with their name."""
        names = fields if fields is not None else list(spec)
        values: dict[str, Any] = {}
        for name in names:
            if "." in name:
                # A dotted path comes back flat under its literal key (003_query); a middle
                # segment outside the field's valid_types drops the key at 200
                # (059_dotted_path_type_check), and a path through a multi_entity field
                # reads back nothing at all (016_dotted_multi_entity).
                present, value = self._resolve_projection(row, spec, name)
                if present:
                    values[name] = value
                continue
            field = spec.get(name)
            # An unknown name in `fields` is dropped at 200; only a filter 400s (003_query).
            if not field:
                continue
            if is_link_type(field.data_type):
                values[name] = self._decorate(row.values.get(name))
            else:
                values[name] = row.values.get(name)
        return EntityRow(type=row.type, id=row.id, values=values)

    def _resolve_projection(
        self,
        row: _Row,
        spec: dict[str, _FieldSpec],
        path: str,
    ) -> tuple[bool, Any]:
        segments = path.split(".")
        head = segments[0]
        field = spec.get(head)
        if not field or not is_link_type(field.data_type):
            return False, None
        if field.data_type == "multi_entity":
            return False, None
        target_type = segments[1] if len(segments) > 1 else None
        if not target_type or (field.valid_types and target_type not in field.valid_types):
            return False, None
        values = self._walk(row, path, False)
        return True, (values[0] if values else None)

    # ------------------------------------------------------------------ #
    # paths                                                               #
    # ------------------------------------------------------------------ #

    def _walk(self, row: _Row, path: str, strict: bool) -> list[Any]:
        """Resolve a plain or dotted path to the values it reaches.

        `strict` makes an unknown field or an unknown middle type raise the 400 the API
        answers in a filter; the projection side wants a silent miss instead.
        """
        segments = path.split(".")
        current = [row]
        index = 0
        while len(segments) - index > 1:
            field_name = segments[index]
            target_type = segments[index + 1]
            next_rows: list[_Row] = []
            for node in current:
                spec = SPECS.get(node.type, {})
                field = spec.get(field_name)
                if not field or not is_link_type(field.data_type):
                    if strict:
                        raise SgApiError(400, None, f"API read() {node.type}.{field_name} doesn't exist.")
                    return []
                # The middle segment is checked against the schema alone in a filter
                # (059_dotted_path_type_check).
                if strict and target_type not in SPECS:
                    raise SgApiError(400, None, f"API read() {target_type} is not a valid entity type.")
                raw = node.values.get(field_name)
                refs = [] if raw is None else (raw if isinstance(raw, list) else [raw])
                for entity_ref in refs:
                    if entity_ref["type"] != target_type:
                        continue
                    target = self._fixtures.index.get(f"{entity_ref['type']}:{entity_ref['id']}")
                    if target:
                        next_rows.append(target)
            current = next_rows
            index += 2
        leaf = segments[index]
        out: list[Any] = []
        for node in current:
            spec = SPECS.get(node.type, {})
            if leaf not in spec:
                if strict:
                    raise SgApiError(400, None, f"API read() {node.type}.{leaf} doesn't exist.")
                continue
            out.append(node.values.get(leaf))
        return out

    def _first(self, row: _Row, path: str) -> Any:
        values = self._walk(row, path, False)
        return values[0] if values else None

    def _data_type_at(self, entity_type: str, path: str) -> str:
        """The data type a filter path lands on, for choosing the comparison and validating the operator."""
        segments = path.split(".")
        current_type = entity_type
        index = 0
        while len(segments) - index > 1:
            field_name = segments[index]
            field = SPECS.get(current_type, {}).get(field_name)
            if not field:
                raise SgApiError(400, None, f"API read() {current_type}.{field_name} doesn't exist.")
            current_type = segments[index + 1]
            if current_type not in SPECS:
                raise SgApiError(400, None, f"API read() {current_type} is not a valid entity type.")
            index += 2
        leaf = segments[index]
        field = SPECS.get(current_type, {}).get(leaf)
        if not field:
            raise SgApiError(400, None, f"API read() {current_type}.{leaf} doesn't exist.")
        return field.data_type

    def _linked_pair(self, row: _Row) -> tuple[str, str]:
        # The linked row's type and name, `('', '')` when it links to nothing.
        for field_name in ("entity", "sg_sequence", "project"):
            value = row.values.get(field_name)
            if value and not isinstance(value, list):
                name = self._display_name_of_ref(value)
                if name is not None:
                    return value["type"], name
        return "", ""

    # ------------------------------------------------------------------ #
    # filters                                                             #
    # ------------------------------------------------------------------ #

    def _match_group(self, row: _Row, entity_type: str, group: WireGroup | None) -> bool:
        if not group:
            return True
        results = [
            self._match_condition(row, entity_type, c)
            if isinstance(c, list)
            else self._match_group(row, entity_type, c)
            for c in group["conditions"]
        ]
        # `"conditions": []` is 200 and matches every row: an empty group is no filter,
        # not a no-match.
        if len(results) == 0:
            return True
        return any(results) if group["logical_operator"] == "or" else all(results)

    def _match_condition(self, row: _Row, entity_type: str, condition: WireCondition) -> bool:
        path, operator, expected = condition
        data_type = self._data_type_at(entity_type, path)
        if not is_filterable(data_type):
            raise SgApiError(
                400,
                None,
                f"API read() {entity_type}.{path}'s '{data_type}' data type cannot be used in a filter.",
            )
        if operator not in operators_for(data_type):
            raise SgApiError(
                400,
                None,
                f"API read() {entity_type}.{path}'s '{data_type}' data type doesn't support "
                f"'{operator}' 'relation'",
            )
        raw = self._walk(row, path, True)
        # `name_is`, `name_contains` and `name_not_contains` read the target's
        # cached_display_name, which a stored `{type, id}` link does not carry, so
        # decorate before comparing.
        values = [self._decorate(v) for v in raw] if operator.startswith("name_") else raw
        now = self._clock()
        # A dotted path that reaches several rows matches if any of them does.
        if len(values) > 1:
            return any(_evaluate(data_type, operator, v, expected, now) for v in values)
        return _evaluate(data_type, operator, values[0] if values else None, expected, now)

    # ------------------------------------------------------------------ #
    # sort                                                                #
    # ------------------------------------------------------------------ #

    def _apply_sort(self, rows: list[_Row], entity_type: str, sort: str | None) -> list[_Row]:
        # With no sort the order is id ascending, and id ascending is the implicit
        # tiebreak (026_result_order).
        out = sorted(rows, key=lambda r: r.id)
        if not sort:
            return out
        keys: list[tuple[str, bool]] = []
        for raw in sort.split(","):
            key = raw.strip()
            if not key:
                continue
            field, descending = (key[1:], True) if key.startswith("-") else (key, False)
            # A sort on a field that does not exist, or one that cannot be sorted, is a
            # silent 200 no-op.
            if field in SPECS.get(entity_type, {}) or "." in field:
                keys.append((field, descending))
        if len(keys) == 0:
            return out
        for field, descending in reversed(keys):
            out.sort(key=lambda r, f=field: _SortKey(self._first(r, f)), reverse=descending)
        return out


class _SortKey:
    """Sort order, with nulls last in both directions (entity_types/Step, on `list_order`)."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: _SortKey) -> bool:
        return _sort_compare(self.value, other.value) < 0

    def __gt__(self, other: _SortKey) -> bool:
        return _sort_compare(self.value, other.value) > 0

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _SortKey) and _sort_compare(self.value, other.value) == 0

    def __hash__(self) -> int:
        return 0


# -------------------------------------------------------------------------- #
# operator evaluation                                                         #
# -------------------------------------------------------------------------- #


def _json(value: Any) -> str:
    """A value the way the API prints one back in an error, which is JSON with no spaces."""
    return json.dumps(value, separators=(",", ":"), default=str)


def _entity_type_named(name: str) -> str | None:
    """A type named as a schema name or as its snake_case plural, or None for neither."""
    if name in SPECS:
        return name
    wanted = name.lower()
    for entity_type in SPECS:
        if entity_type.lower() == wanted or plural_path(entity_type) == wanted:
            return entity_type
    return None


def _status_code(values: dict[str, Any]) -> Any:
    """A row's status code: `sg_status_list`, or Project's own `sg_status`."""
    code = values.get("sg_status_list")
    return values.get("sg_status") if code is None else code


def _is_nullish(v: Any) -> bool:
    # A text field has no empty string: writing "" stores null, so the two are one value
    # (field_types/text).
    return v is None or (isinstance(v, str) and v == "")


def _refs_of(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _ref_pair(value: Any) -> tuple[Any, Any] | None:
    if isinstance(value, EntityRef):
        return value.type, value.id
    if isinstance(value, dict):
        return value.get("type"), value.get("id")
    return None


def _to_number(value: Any) -> float | None:
    """`Number(x)`, with NaN as None."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip() or 0)
        except ValueError:
            return None
    if value is None:
        return 0.0
    return None


def _same_scalar(data_type: str, actual: Any, expected: Any) -> bool:
    if _is_nullish(expected):
        return _is_nullish(actual)
    if _is_nullish(actual):
        return False
    if is_link_type(data_type):
        wanted = _ref_pair(expected)
        if wanted is None:
            return False
        return any(_ref_pair(r) == wanted for r in _refs_of(actual))
    if is_numeric_type(data_type):
        # `is '1001'` matches the integer 1001: the API coerces a numeric string
        # (field_types/number).
        a = _to_number(actual)
        b = _to_number(expected)
        return a is not None and b is not None and a == b
    if isinstance(actual, str) and isinstance(expected, str):
        # text, list and status_list all match case-insensitively, where a write is
        # case-sensitive.
        return actual.lower() == expected.lower()
    return actual == expected


def _substring(actual: Any, expected: Any, mode: str) -> bool:
    if _is_nullish(actual) or expected is None:
        return False
    a = _js_string(actual).lower()
    b = _js_string(expected).lower()
    if mode == "contains":
        return b in a
    if mode == "starts":
        return a.startswith(b)
    return a.endswith(b)


def _js_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _compare(a: Any, b: Any) -> float | None:
    """Order two filter values. None when either is unset, which is what excludes null rows."""
    if _is_nullish(a) or _is_nullish(b):
        return None
    if _is_number(a) or _is_number(b):
        x = _to_number(a)
        y = _to_number(b)
        return None if x is None or y is None else x - y
    # ISO dates and date-times order lexicographically.
    x_s = _js_string(a)
    y_s = _js_string(b)
    return -1 if x_s < y_s else 1 if x_s > y_s else 0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _sort_compare(a: Any, b: Any) -> float:
    a_null = _is_nullish(a)
    b_null = _is_nullish(b)
    if a_null and b_null:
        return 0
    if a_null:
        return 1
    if b_null:
        return -1
    c = _compare(a, b)
    return c if c is not None else 0


# -------------------------------------------------------------------------- #
# the clock, and the date operators read off it                               #
# -------------------------------------------------------------------------- #


def _parse_ms(value: str) -> float | None:
    """`Date.parse` over the two forms the API stores: a date and a second-resolution moment."""
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # A date-only form is UTC; a date-time with no zone is local on a site and UTC here.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed - _UNIX_EPOCH).total_seconds() * 1000


def _to_clock(now: Clock | None) -> Callable[[], float]:
    if callable(now):
        return now
    if isinstance(now, bool):
        raise TypeError(f"MockClient: 'now' is not a date: {now}")
    if isinstance(now, (int, float)):
        fixed = float(now)
        return lambda: fixed
    if isinstance(now, str):
        parsed = _parse_ms(now)
        if parsed is None:
            raise TypeError(f"MockClient: 'now' is not a date: {now}")
        return lambda: parsed
    return lambda: time.time() * 1000


RELATIVE_OPERATORS = frozenset(("in_last", "not_in_last", "in_next", "not_in_next"))
CALENDAR_OPERATORS = frozenset((
    "in_calendar_day", "in_calendar_week", "in_calendar_month", "in_calendar_year",
))


def _print_list(values: Sequence[Any]) -> str:
    """A value list the way the API prints one back in an error."""
    return "[" + ", ".join(json.dumps(v, default=str) for v in values) + "]"


def _relative_value(operator: Operator, expected: Any) -> tuple[int, TimeUnit]:
    """`[count, UNIT]`, with the three 400s the API answers for a malformed one (field_types/date)."""
    parts = list(expected) if isinstance(expected, (list, tuple)) else [expected]
    if len(parts) != 2:
        raise SgApiError(
            400, None, f"API read() '{operator}' 'relation' expects a 2-element array: {_print_list(parts)}"
        )
    count, unit = parts
    if unit not in TIME_UNITS:
        raise SgApiError(
            400,
            None,
            f"API read() '{operator}' 'relation' doesn't support the '{unit}' time unit: "
            f"{_print_list(parts)}  Valid time units: {_print_list(TIME_UNITS)}",
        )
    if not _is_js_integer(count) or count <= 0:
        # The API's own wording, missing word included.
        raise SgApiError(
            400, None, f"API read() '{operator}' 'relation' expects at a positive Integer time unit"
        )
    return int(count), unit


def _is_js_integer(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return float(value).is_integer()


def _shift_months(t: float, months: int) -> float:
    """Shift a UTC instant by whole months, clamping a day the target month does not have."""
    d = _at(t)
    total = d.year * 12 + (d.month - 1) + months
    year, month = total // 12, total % 12 + 1
    last = _days_in_month(year, month)
    return _utc_ms(year, month, min(d.day, last), d.hour, d.minute, d.second, d.microsecond // 1000)


def _days_in_month(year: int, month: int) -> int:
    nxt = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)
    return (nxt - timedelta(days=1)).day


def _relative_window(now: float, count: int, unit: TimeUnit, forward: bool) -> tuple[float, float]:
    """The window `[count, UNIT]` names: back to `now`, or forward from it."""
    sign = 1 if forward else -1
    if unit == "HOUR":
        edge = now + sign * count * HOUR_MS
    elif unit == "DAY":
        edge = now + sign * count * DAY_MS
    elif unit == "WEEK":
        edge = now + sign * count * 7 * DAY_MS
    elif unit == "MONTH":
        edge = _shift_months(now, sign * count)
    else:
        edge = _shift_months(now, sign * count * 12)
    return (now, edge) if forward else (edge, now)


def _calendar_window(now: float, operator: Operator, offset: int) -> tuple[float, float]:
    """The UTC calendar bucket `offset` from the one holding `now`, inclusive at both ends.

    A week runs Monday to Sunday: the corpus pins the buckets to UTC but not the first day.
    """
    d = _at(now)
    if operator == "in_calendar_year":
        return _utc_ms(d.year + offset, 1, 1), _utc_ms(d.year + offset + 1, 1, 1) - 1
    if operator == "in_calendar_month":
        return _utc_ms(d.year, d.month + offset, 1), _utc_ms(d.year, d.month + offset + 1, 1) - 1
    midnight = _utc_ms(d.year, d.month, d.day)
    if operator == "in_calendar_day":
        start = midnight + offset * DAY_MS
        return start, start + DAY_MS - 1
    start = midnight - d.weekday() * DAY_MS + offset * 7 * DAY_MS
    return start, start + 7 * DAY_MS - 1


def _span(data_type: str, value: Any) -> tuple[float, float] | None:
    """The inclusive span a stored value covers.

    A `date` has no time of day and stands for its whole UTC day, which is why a window
    shorter than a day still matches today (field_types/date).
    """
    if not isinstance(value, str):
        return None
    t = _parse_ms(value)
    if t is None:
        return None
    return (t, t + DAY_MS - 1) if data_type == "date" else (t, t)


def _within(data_type: str, actual: Any, window: tuple[float, float]) -> bool:
    covered = _span(data_type, actual)
    return covered is not None and covered[0] <= window[1] and covered[1] >= window[0]


def _match_temporal(data_type: str, operator: Operator, actual: Any, expected: Any, now: float) -> bool:
    """A relative or calendar date operator, resolved against the clock."""
    if operator in RELATIVE_OPERATORS:
        # Validated before the row is read: a malformed value 400s whatever the rows hold.
        count, unit = _relative_value(operator, expected)
        negating = operator in NEGATING_OPERATORS
        # `not_in_last` and `not_in_next` match a row with no date at all (field_types/date).
        if _is_nullish(actual):
            return negating
        forward = operator in ("in_next", "not_in_next")
        hit = _within(data_type, actual, _relative_window(now, count, unit, forward))
        return not hit if negating else hit
    # A signed offset from the current bucket, 0 being this one, taken bare or as a
    # one-element array.
    raw = expected[0] if isinstance(expected, (list, tuple)) and expected else expected
    offset = _to_number(raw)
    # A non-integer offset is not measured: nothing matches, rather than a 400 the API may
    # not answer.
    if offset is None or not float(offset).is_integer():
        return False
    return _within(data_type, actual, _calendar_window(now, operator, int(offset)))


def _names_of(actual: Any) -> list[str]:
    out = []
    for r in _refs_of(actual):
        name = r.name if isinstance(r, EntityRef) else r.get("name") if isinstance(r, dict) else None
        if isinstance(name, str) and name:
            out.append(name)
    return out


def _as_list(value: Any) -> list[Any]:
    # `in` and `not_in` take a list, but a bare scalar also works on a date (field_types/date).
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _evaluate(data_type: str, operator: Operator, actual: Any, expected: Any, now: float) -> bool:
    if operator in RELATIVE_OPERATORS or operator in CALENDAR_OPERATORS:
        return _match_temporal(data_type, operator, actual, expected, now)
    # Every negating operator also matches rows where the field is null: `is_not X` is not
    # the complement of `is X` on this API (field_types/date, field_types/number,
    # field_types/entity).
    if operator in NEGATING_OPERATORS and _is_nullish(actual):
        return True

    if operator == "is":
        return _same_scalar(data_type, actual, expected)
    if operator == "is_not":
        return not _same_scalar(data_type, actual, expected)
    if operator == "in":
        return any(_same_scalar(data_type, actual, e) for e in _as_list(expected))
    if operator == "not_in":
        return not any(_same_scalar(data_type, actual, e) for e in _as_list(expected))
    if operator == "contains":
        return _substring(actual, expected, "contains")
    if operator == "not_contains":
        return not _substring(actual, expected, "contains")
    if operator == "starts_with":
        return _substring(actual, expected, "starts")
    if operator == "ends_with":
        return _substring(actual, expected, "ends")
    if operator == "greater_than":
        c = _compare(actual, expected)
        return c is not None and c > 0
    if operator == "less_than":
        c = _compare(actual, expected)
        return c is not None and c < 0
    if operator == "between":
        listed = _as_list(expected)
        lo = listed[0] if len(listed) > 0 else None
        hi = listed[1] if len(listed) > 1 else None
        # Inclusive at both ends and order-insensitive; a null bound matches nothing
        # (field_types/date).
        a = _compare(actual, lo)
        b = _compare(actual, hi)
        if a is None or b is None:
            return False
        return (a >= 0 and b <= 0) or (a <= 0 and b >= 0)
    if operator == "type_is":
        return any(_type_of(r) == expected for r in _refs_of(actual))
    if operator == "type_is_not":
        return not any(_type_of(r) == expected for r in _refs_of(actual))
    if operator == "name_is":
        return any(n.lower() == _js_string(expected).lower() for n in _names_of(actual))
    if operator == "name_contains":
        return any(_js_string(expected).lower() in n.lower() for n in _names_of(actual))
    if operator == "name_not_contains":
        return not any(_js_string(expected).lower() in n.lower() for n in _names_of(actual))
    # The date operators are handled above; every other operator in the vocabulary has a branch.
    return False


def _type_of(value: Any) -> Any:
    pair = _ref_pair(value)
    return pair[0] if pair else None


def _group_label(value: Any) -> str:
    """On an entity grouping the label is the target's display name, not the whole hash (020_summarize)."""
    if isinstance(value, dict) and "type" in value:
        name = value.get("name")
        return name if name is not None else f"{value['type']} #{value['id']}"
    return _js_string(value)


def _to_status_icon(values: dict[str, Any]) -> StatusIcon | None:
    display_type = values.get("display_type")
    if display_type == "image_map":
        return ImageMapIcon(image_map_key=str(values.get("image_map_key") or ""))
    if display_type == "image":
        return ImageIcon(data_url=re.sub(r"\s+", "", str(values.get("url") or "")))
    if display_type == "html":
        return HtmlIcon(html=str(values.get("html") or ""))
    return None
